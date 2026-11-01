# file: model_capability_eval.py
# description: 统一 API 模型多维能力终极评测——八维度×程序化判分（零 LLM 评审）
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-11-02
# status: active
# tags: [eval],[benchmark],[multidim],[api]
# stdlib-only；SSRF 守卫同 ops_vkey.py；代码判分子进程 -I + 超时（受控本机评测语义）

"""
@file: scripts/model_capability_eval.py
@description: 对统一网关任一模型做八维度实弹评测：
  D1 数学推理(12, 含思考 A/B) D2 代码生成(6, exec 判分) D3 中文阅读(4)
  D4 逻辑推理(6) D5 指令遵循(5) D6 长上下文检索(2) D7 多轮状态(3) D8 视觉(2)
@usage:
  export YYC3_ADMIN_KEY=<管理key>
  python3 scripts/ops_vkey.py issue --name eval --owner eval --whitelist <model>
  python3 scripts/model_capability_eval.py --key <vk> --model nemotron-3.5-super-vl
@判分: 全程序化（数值归一/精确匹配/子进程执行/JSON 解析/约束检查），无 LLM 评审。
"""

import argparse
import base64
import ipaddress
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import zlib
from urllib.parse import urlparse

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from svl2_json_rescue import json_rescue  # noqa: E402

DEFAULT_BASE = os.environ.get("YYC3_GATEWAY_BASE", "http://100.65.172.88:8000")
DEFAULT_MODEL = "nemotron-3.5-super-vl"
_ALLOWED_SCHEMES = ("http", "https")
ALLOW_PRIVATE_TARGETS = True
_HARD_BLOCK_NETS = [ipaddress.ip_network(n) for n in ("169.254.0.0/16", "0.0.0.0/8", "224.0.0.0/4", "240.0.0.0/4")]

# ── 网络与调用 ──────────────────────────────────────────────────────────────

def _validate_base(base: str) -> str:
    u = urlparse(base)
    if u.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"仅允许 http/https: {u.scheme!r}")
    if u.username or u.password:
        raise ValueError("URL 不允许内嵌凭据")
    host = u.hostname or ""
    if not host:
        raise ValueError("URL 缺主机名")
    port = u.port or (443 if u.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(host, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise ValueError(f"域名解析失败: {host}: {e}") from e
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if any(ip in net for net in _HARD_BLOCK_NETS):
            raise ValueError(f"禁止的目标地址段: {ip}")
        if not ALLOW_PRIVATE_TARGETS and (ip.is_private or ip.is_loopback):
            raise ValueError(f"私网目标未放行: {ip}")
    return base.rstrip("/")


def _chat(base, key, model, messages, max_tokens=512, think=None, timeout=120):
    """think: None=网关默认(关) / True=显式开思考(加大预算) / False=显式关。"""
    body = {"model": model, "messages": messages, "max_tokens": max_tokens, "temperature": 0, "stream": False}
    if think is not None:
        body["chat_template_kwargs"] = {"enable_thinking": bool(think)}
    req = urllib.request.Request(
        _validate_base(base) + "/v1/chat/completions",
        method="POST",
        data=json.dumps(body).encode(),
        headers={"X-API-Key": key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            d = json.loads(resp.read().decode())
            wall = time.time() - t0
            msg = (d.get("choices") or [{}])[0].get("message", {})
            return wall, msg.get("content") or "", d.get("usage", {})
    except urllib.error.HTTPError as e:
        return time.time() - t0, "", {"http_error": e.code}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return time.time() - t0, "", {"conn_error": str(e)[:80]}

# ── 判分工具 ────────────────────────────────────────────────────────────────

def _norm(s):
    s = (s or "").strip().lower()
    s = s.replace("，", ",").replace("。", "").replace("：", ":").replace(" ", "")
    s = re.sub(r"^[^:]*答案[::]", "", s)  # 取「答案:」之后
    return s


def _ans_of(text):
    """提取「答案」标记后内容；无标记取末行。"""
    m = re.findall(r"答[案題][:：]\s*(.+)", text or "")
    if m:
        return m[-1].strip()
    lines = [l.strip() for l in (text or "").strip().splitlines() if l.strip()]
    return lines[-1] if lines else ""


def _num_match(ans, expect):
    nums = re.findall(r"-?\d+(?:\.\d+)?", _norm(ans).replace(",", ""))
    if not nums:
        return False
    last = nums[-1]
    try:
        return abs(float(last) - float(expect)) < 1e-6
    except ValueError:
        return False


def _code_exec(code, tests_code, timeout=8):
    """子进程执行模型代码+测试断言（-I 隔离 + 超时；受控本机评测语义）。"""
    with tempfile.TemporaryDirectory() as td:
        f = os.path.join(td, "t.py")
        with open(f, "w", encoding="utf-8") as fh:
            fh.write(code + "\n" + tests_code + "\n")
        try:
            r = subprocess.run([sys.executable, "-I", f], capture_output=True, text=True, timeout=timeout, cwd=td)
            return r.returncode == 0, (r.stderr or "").strip()[-120:]
        except subprocess.TimeoutExpired:
            return False, "timeout"

def _extract_code(text):
    m = re.search(r"```(?:python)?\s*\n(.*?)```", text or "", re.DOTALL)
    return m.group(1) if m else (text or "")

# ── D1 数学（12 题，含思考 A/B）────────────────────────────────────────────

MATH = [
    ("一个班级45名学生，60%参加运动队，运动队里三分之一参加篮球队。篮球队多少人？", 9),
    ("商品原价240元，先涨价25%，再打八折，最终价格多少元？", 240),
    ("小明每天读18页，读了12天后还剩全书的40%没读。全书多少页？", 360),
    ("3台机器4小时生产96个零件，5台机器6小时生产多少个零件？", 240),
    ("兔龟赛跑全程1500米。兔子速度10米/秒，乌龟1.5米/秒。兔子跑完200米后睡觉，醒来时乌龟距终点还有300米。兔子睡了多少秒？", 780),
    ("水池甲管单独6小时注满，乙管单独12小时注满。两管同开几小时注满？", 4),
    ("父亲今年43岁，儿子13岁。几年前父亲年龄是儿子的6倍？", 7),
    ("计算：3/4 + 5/6 - 7/12 = ?", 1),
    ("汽车以60公里/小时行驶1.5小时后，剩余路程是已走路程的2倍。全程多少公里？", 270),
    ("一项工程甲单独10天完成，乙单独15天完成。合作3天后乙离开，甲还需几天完成？", 5),
    ("同时掷两枚骰子，点数之和为8的概率是多少？（写成分数）", None),  # 5/36 特判
    ("数列 2, 6, 12, 20, 30, … 第8项是多少？", 72),
]


def _grade_math(ans, expect):
    n = _norm(ans).replace(" ", "")
    if expect is None:  # 5/36
        return bool(re.search(r"5\s*/\s*36", n))
    return _num_match(n, expect)

# ── D2 代码（6 题，exec 判分）───────────────────────────────────────────────

CODE = [
    ("写 Python 函数 two_sum(nums, target)，返回 nums 中和为 target 的两个数的下标列表（顺序任意）。只输出代码块。",
     "assert sorted(two_sum([2,7,11,15], 9)) == [0,1]\nassert sorted(two_sum([3,2,4], 6)) == [1,2]\nassert sorted(two_sum([3,3], 6)) == [0,1]\nprint('OK')"),
    ("写 Python 函数 is_palindrome(s)，忽略大小写与非字母数字字符判断回文。只输出代码块。",
     "assert is_palindrome('A man, a plan, a canal: Panama') is True\nassert is_palindrome('race a car') is False\nassert is_palindrome('') is True\nprint('OK')"),
    ("写 Python 函数 fib(n)，返回斐波那契第 n 项（fib(0)=0, fib(1)=1），n 可到 1000。只输出代码块。",
     "assert fib(0)==0 and fib(1)==1 and fib(10)==55\nassert fib(50)==12586269025\nprint('OK')"),
    ("写 Python 函数 flatten(nested)，把任意深度嵌套列表展平为一维列表。只输出代码块。",
     "assert flatten([1,[2,[3,[4]],5]]) == [1,2,3,4,5]\nassert flatten([]) == []\nassert flatten([1,[2],3]) == [1,2,3]\nprint('OK')"),
    ("写 Python 函数 word_count(text)，返回每个单词出现次数的字典（按空格分词，忽略大小写）。只输出代码块。",
     "d = word_count('a b a A c')\nassert d['a'] == 3 and d['b'] == 1 and d['c'] == 1\nprint('OK')"),
    ("写 Python 函数 roman_to_int(s)，把罗马数字转为整数（s 为 1-3999）。只输出代码块。",
     "assert roman_to_int('III')==3\nassert roman_to_int('IV')==4\nassert roman_to_int('IX')==9\nassert roman_to_int('LVIII')==58\nassert roman_to_int('MCMXCIV')==1994\nprint('OK')"),
]

# ── D3 中文阅读（4 题，事实抽取/文中计算）──────────────────────────────────

READING = [
    ("某公司年报摘要：本公司2025年营业收入为3.2亿元，同比增长25%，其中海外收入占比20%。问：该公司2024年营业收入是多少亿元？", "2.56"),
    ("会议通知：产品评审会原定11月3日（星期一）召开，因故推迟两天。问：推迟后的会议是星期几？（答案如：星期三）", "星期三"),
    ("办公室有五人：老张、小李、小王、小赵、小周。周五团建时小李和小王出差，小赵请了假。问：参加团建的有哪些人？（答案格式：用顿号列出全部姓名）", None),  # 特判包含
    ("桥牌俱乐部会员统计：男会员36人，女会员数量是男会员的三分之二。问：女会员多少人？", "24"),
]


def _grade_reading(ans, expect):
    n = _norm(ans)
    if expect is None:  # 老张、小周（或小周、老张）
        return ("老张" in n and "小周" in n and "小李" not in n and "小王" not in n and "小赵" not in n)
    return expect.replace(".", "") in n.replace(".", "")

# ── D4 逻辑（6 题）──────────────────────────────────────────────────────────

LOGIC = [
    ("甲、乙、丙三人，一位是医生、一位是教师、一位是工程师。已知：甲比教师年龄大；丙和工程师不同岁；工程师比乙年轻。问三人职业各是什么？（答案格式：甲-职业,乙-职业,丙-职业）", "医生,工程师,教师"),
    ("五个人排队买票：小 A 不在两端；小 B 紧挨着小 A 右侧；小 C 在正中间第3位；小 D 在小 E 左侧。已知小 A 在第2位，问第4位是谁？", None),  # 特判 E
    ("甲乙丙三人中只有一人说了真话。甲说：是我打碎了花瓶。乙说：不是我。丙说：乙在说谎。问花瓶是谁打碎的？", None),  # 特判 甲/乙
    ("四支队伍比赛（无平局）：红队胜蓝队，蓝队胜绿队，绿队胜黄队，黄队胜红队，且红队胜绿队。问四队中胜场最多的是哪队（都只赛了这三场）？", None),  # 特判 红队(2胜)
    ("类比推理：鸟之于天空，犹如鱼之于什么？用一个字回答。", None),  # 特判 水
    ("数列 1, 1, 2, 3, 5, 8, ? 的下一项是多少？", 13),
]


def _grade_logic(ans, expect):
    n = _norm(ans)
    if expect == "医生,工程师,教师":
        ok = ("甲" in n and "医生" in n.split(",")[0]) and ("乙" in n and "教师" in n.split(",")[1] if "," in n else False) and ("丙" in n and "工程师" in (n.split(",")+[""])[2])
        return bool(ok)
    if expect is None:  # 逐题特判（与 idx 对应，见调用处）
        return None  # 由调用方传入特判函数
    if isinstance(expect, int):
        return _num_match(n, expect)
    return expect in n

# ── D5 指令遵循（5 题，约束判分）───────────────────────────────────────────

def _grade_instruction(idx, text):
    t = (text or "").strip()
    if idx == 1:  # JSON 三字段
        obj, _ = json_rescue(t)
        return bool(obj == {"name": "张三", "age": 30, "city": "北京"}), ""
    if idx == 2:  # JSON 数组 3 商品
        obj, _ = json_rescue(t)
        ok = isinstance(obj, list) and len(obj) == 3 and all(
            isinstance(x, dict) and isinstance(x.get("price"), (int, float)) and x.get("name") for x in obj)
        return bool(ok), ""
    if idx == 3:  # ≤20字且含100
        ok = len(t) <= 20 and "100" in t
        return ok, f"len={len(t)}"
    if idx == 4:  # 恰好4行无序号
        lines = [l for l in t.splitlines() if l.strip()]
        ok = len(lines) == 4 and all(not re.search(r"\d|[.、)）(（]", l) for l in lines)
        return ok, f"lines={len(lines)}"
    if idx == 5:  # 纯英文翻译
        has_cjk = any("\u4e00" <= ch <= "\u9fff" for ch in t)
        ok = (not has_cjk) and bool(re.search(r"weather|today|nice|good|fine", t, re.I))
        return ok, ""
    return False, ""

INSTRUCTION = [
    ('把以下信息输出为 JSON（只输出JSON）：姓名张三，年龄30岁，居住北京。', None),
    ('输出一个 JSON 数组：恰好 3 个水果商品，每个对象含 name(字符串) 和 price(数字)。只输出JSON。', None),
    ('用不超过 20 个字回答：水的沸点是多少摄氏度？', None),
    ('列出恰好 4 种水果，每行一个，不加序号、不加标点。', None),
    ('把这句话翻译成英文，只输出英文：今天天气很好。', None),
]

# ── D6 长上下文检索（needle）───────────────────────────────────────────────

_NEEDLE_TMPL = "第{i}条库存记录：货品编号 G-{i:04d}，数量 {q}，仓位 {w}。"

def _build_needle(total_lines, needle_line_at, needle_sentence):
    lines = []
    for i in range(1, total_lines + 1):
        lines.append(_NEEDLE_TMPL.format(i=i, q=(i * 7) % 500 + 10, w=["东", "西", "南", "北"][i % 4]))
        if i == needle_line_at:
            lines.append(needle_sentence)
    return "以下是仓库流水记录：\n" + "\n".join(lines) + "\n\n问题：文中那条以【机密】开头的记录里，密码是什么？只回答密码本身。"

# ── D7 多轮状态（3 轮链）───────────────────────────────────────────────────

MULTITURN = [
    ([("我有一篮子苹果，共 5 个。", None),
      ("我吃掉 2 个，又买了 4 个苹果放进去。现在篮子里有几个苹果？", 7),
      ("从中拿出 3 个给邻居。现在篮子里有几个苹果？", 4),
      ("邻居又还回来 1 个坏的，我扔掉了。现在篮子里有几个苹果？", 2)]),
    ([("会议室原有 12 把椅子。", None),
      ("搬走 5 把，又搬来 8 把，现在有几把？", 15),
      ("摆成每排 5 把，可以摆满几排还剩几把？回答格式：x排剩y把", None),
      ("剩下的椅子全部修好后总共有多少把可用的？（假设都可用）", 15)]),
    ([("小明有 100 元。", None),
      ("买了一支 23 元的笔，还剩多少元？", 77),
      ("又买两本各 15 元的书，还剩多少元？", 47),
      ("妈妈给了他 53 元，现在有多少元？", 100)]),
]

# ── D8 视觉（2 题，纯 Python 生成 PNG）─────────────────────────────────────

def _make_png(shapes, size=224):
    """shapes: list of (kind, color, cx, cy, r)。纯像素缓冲生成 PNG（无第三方依赖）。"""
    buf = bytearray(size * size * 3)
    px = 255

    def setpix(x, y, rgb):
        if 0 <= x < size and 0 <= y < size:
            o = (y * size + x) * 3
            buf[o:o+3] = bytes(rgb)

    def fill_rect(x0, y0, w, h, rgb):
        for yy in range(max(0, y0), min(size, y0+h)):
            for xx in range(max(0, x0), min(size, x0+w)):
                setpix(xx, yy, rgb)

    def fill_circle(cx, cy, r, rgb):
        for yy in range(max(0, cy-r), min(size, cy+r+1)):
            for xx in range(max(0, cx-r), min(size, cx+r+1)):
                if (xx-cx)**2 + (yy-cy)**2 <= r*r:
                    setpix(xx, yy, rgb)

    fill_rect(0, 0, size, size, (255, 255, 255))
    for sh in shapes:
        kind, color, a, b, c = sh[0], sh[1], sh[2], sh[3], sh[4]
        rgb = {"red": (220, 40, 40), "blue": (40, 70, 220), "green": (30, 170, 60)}[color]
        if kind == "circle":
            fill_circle(a, b, c, rgb)
        else:
            d = sh[5] if len(sh) > 5 else c
            fill_rect(a, b, c, d, rgb)

    def chunk(typ, data):
        c = struct_pack(len(data)) + typ + data
        return c + struct_pack(zlib.crc32(typ + data) & 0xFFFFFFFF)

    def struct_pack(n):
        import struct
        return struct.pack(">I", n)

    import struct
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(buf[y*size*3:(y+1)*size*3]) for y in range(size))
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))


def _vision_cases():
    png1 = _make_png([("circle", "red", 60, 60, 30), ("circle", "red", 150, 80, 25),
                      ("circle", "red", 100, 170, 35), ("rect", "blue", 180, 160, 28, 28),
                      ("rect", "blue", 30, 140, 24, 24)])
    png2 = _make_png([("rect", "green", 50, 50, 40, 40), ("rect", "green", 140, 120, 35, 35),
                      ("rect", "red", 100, 40, 26, 26), ("circle", "green", 170, 170, 30),
                      ("circle", "blue", 40, 160, 28)])
    return [
        ("数一数：图中有几个红色的圆形？只回答数字。", png1, "3"),
        ("数一数：图中有几个绿色的正方形？只回答数字。", png2, "2"),
    ]

# ── 主流程 ─────────────────────────────────────────────────────────────────

def _p50(vals):
    s = sorted(vals)
    return s[len(s)//2] if s else 0.0


def _p95(vals):
    s = sorted(vals)
    return s[int(len(s)*0.95)] if s else 0.0


def main():
    ap = argparse.ArgumentParser(description="YYC³ 模型多维能力终极评测（八维度·程序化判分）")
    ap.add_argument("--base", default=DEFAULT_BASE)
    ap.add_argument("--key", default=os.environ.get("YYC3_API_KEY", ""))
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--dims", default="D1,D2,D3,D4,D5,D6,D7,D8")
    ap.add_argument("--pause", type=float, default=1.0)
    ap.add_argument("--json", dest="json_out", action="store_true")
    args = ap.parse_args()
    if not args.key:
        sys.exit("❌ 缺 Key：--key 或 YYC3_API_KEY")
    try:
        base = _validate_base(args.base)
    except ValueError as e:
        sys.exit(f"❌ {e}")
    dims = [d.strip().upper() for d in args.dims.split(",") if d.strip()]
    results = []

    def record(dim, name, ok, wall, detail):
        results.append({"dim": dim, "case": name, "pass": ok, "wall_s": round(wall, 1), "detail": detail})
        print(f"{'✅' if ok else '❌'} [{dim}] {name[:34]:34} {wall:5.1f}s  {detail}", flush=True)

    # D1 数学（关思考 + 思考 A/B）
    if "D1" in dims:
        for i, (q, exp) in enumerate(MATH, 1):
            wall, out, _ = _chat(base, args.key, args.model,
                                 [{"role": "user", "content": q + "\n（最后单独一行写：答案: 数字）"}], 512)
            record("D1-off", f"数学#{i}", _grade_math(_ans_of(out), exp), wall, _norm(_ans_of(out))[:24])
            time.sleep(args.pause)
        for i, (q, exp) in enumerate(MATH[:6], 1):  # 思考 A/B：仅前 6 题
            wall, out, _ = _chat(base, args.key, args.model,
                                 [{"role": "user", "content": q + "\n（最后单独一行写：答案: 数字）"}],
                                 max_tokens=3072, think=True, timeout=240)
            record("D1-on", f"数学思考#{i}", _grade_math(_ans_of(out), exp), wall, _norm(_ans_of(out))[:24])
            time.sleep(args.pause)

    # D2 代码
    if "D2" in dims:
        for i, (q, tests) in enumerate(CODE, 1):
            wall, out, _ = _chat(base, args.key, args.model, [{"role": "user", "content": q}], 1024)
            ok, detail = _code_exec(_extract_code(out), tests)
            record("D2", f"代码#{i}", ok, wall, detail or "exec ok")
            time.sleep(args.pause)

    # D3 阅读
    if "D3" in dims:
        for i, (q, exp) in enumerate(READING, 1):
            wall, out, _ = _chat(base, args.key, args.model, [{"role": "user", "content": q + "\n（最后单独一行写：答案: …）"}], 512)
            a = _ans_of(out)
            ok = _grade_reading(a, exp)
            if exp is None and ok is False and i == 3:
                ok = ("老张" in _norm(a) and "小周" in _norm(a))
            record("D3", f"阅读#{i}", ok, wall, _norm(a)[:24])
            time.sleep(args.pause)

    # D4 逻辑（第 2/3/4/5 题特判）
    SPECIAL_LOGIC = {
        2: lambda a: _norm(a).startswith("小e") or "e" == _norm(a)[-1:],
        3: lambda a: "甲" in _norm(a) and "打碎" in (a or ""),
        4: lambda a: "红队" in a,
        5: lambda a: _norm(a) in ("水", "水里", "水中", "水中的", "水。"),
    }
    if "D4" in dims:
        for i, (q, exp) in enumerate(LOGIC, 1):
            wall, out, _ = _chat(base, args.key, args.model, [{"role": "user", "content": q + "\n（最后单独一行写：答案: …）"}], 640)
            a = _ans_of(out)
            if i in SPECIAL_LOGIC:
                ok = bool(SPECIAL_LOGIC[i](a))
            else:
                ok = _grade_logic(a, exp)
            record("D4", f"逻辑#{i}", ok, wall, _norm(a)[:24])
            time.sleep(args.pause)

    # D5 指令遵循
    if "D5" in dims:
        for i, (q, _) in enumerate(INSTRUCTION, 1):
            wall, out, _ = _chat(base, args.key, args.model, [{"role": "user", "content": q}], 512)
            ok, detail = _grade_instruction(i, out)
            record("D5", f"指令#{i}", ok, wall, detail)
            time.sleep(args.pause)

    # D6 长上下文
    if "D6" in dims:
        for j, (total, at, secret) in enumerate([("600", 180, "X7K9-Q2"), ("1200", 860, "M-88-D")], 1):
            prompt = _build_needle(int(total), at, f"【机密】系统管理员备注：本月临时访问密码是 {secret}，泄露必究。")
            wall, out, _ = _chat(base, args.key, args.model, [{"role": "user", "content": prompt}], 128, timeout=180)
            ok = secret.lower() in _norm(out)
            record("D6", f"检索#{j}({total}行)", ok, wall, _norm(out)[:24])
            time.sleep(args.pause)

    # D7 多轮
    if "D7" in dims:
        for c, chain in enumerate(MULTITURN, 1):
            msgs, all_ok, walls = [], True, []
            for turn, (q, exp) in enumerate(chain):
                msgs.append({"role": "user", "content": q})
                wall, out, _ = _chat(base, args.key, args.model, msgs, 512)
                walls.append(wall)
                msgs.append({"role": "assistant", "content": out.strip() or "…"})
                if exp is not None:
                    if not _num_match(out, exp):
                        all_ok = False
                        record("D7", f"多轮#{c}·轮{turn}", False, wall, _norm(_ans_of(out))[:20])
                time.sleep(args.pause)
            record("D7", f"多轮#{c}全链", all_ok, sum(walls), f"{len(chain)}轮")

    # D8 视觉
    if "D8" in dims:
        for i, (q, png, exp) in enumerate(_vision_cases(), 1):
            b64 = base64.b64encode(png).decode()
            content = [{"type": "text", "text": q},
                       {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]
            wall, out, usage = _chat(base, args.key, args.model,
                                     [{"role": "user", "content": content}], 256, timeout=120)
            if usage.get("http_error") or usage.get("conn_error"):
                record("D8", f"视觉#{i}", False, wall, f"infra {str(usage)[:60]}")
                continue
            ok = _num_match(out, exp)
            record("D8", f"视觉#{i}", ok, wall, _norm(_ans_of(out))[:20])
            time.sleep(args.pause)

    # 汇总
    print("\n===== 维度小结 =====")
    dims_order = []
    for r in results:
        if r["dim"] not in dims_order:
            dims_order.append(r["dim"])
    for d in dims_order:
        rs = [r for r in results if r["dim"] == d]
        ok = sum(1 for r in rs if r["pass"])
        walls = [r["wall_s"] for r in rs]
        print(f"{d:7} {ok}/{len(rs):2}  wall p50={_p50(walls):5.1f}s p95={_p95(walls):5.1f}s")
    total_ok = sum(1 for r in results if r["pass"])
    print(f"TOTAL  {total_ok}/{len(results)}")
    if args.json_out:
        print(json.dumps({"model": args.model, "base": base,
                          "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "results": results},
                         ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
