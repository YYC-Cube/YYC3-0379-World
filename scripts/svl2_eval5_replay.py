# svl2 A 类格式缺陷 · 15 例重放驱动器（U16 移交任务 3 · eval4 同口径）
# 电池:
#   direct  = 直连 svl2 TS:8888（层属二分 E-0①：绕过 aify——若同样失败则模型侧实锤）
#   gateway = 网关 :10086 现状（E-0②：应复现 eval4 的 A 1/5）
#   rescued = 网关 + 客户端提取器（E-0③：不动 aify 先证修复，推演预期 15/15）
# 用法:
#   python3 scripts/svl2_eval5_replay.py --battery gateway --out /tmp/svl2_replay.json
#   python3 scripts/svl2_eval5_replay.py --battery direct  --host 100.65.64.49 --port 8888
#   python3 scripts/svl2_eval5_replay.py --battery rescued            # 提取器客户端侧生效
# 纪律: svl2 为生产强推理位——串行 1 并发（本驱动器不做并发）；判分器与 agent4b_eval4.py 逐字同口径
# 产物: JSON 逐例 + stdout 对照表（A/B/C 分组 pass 率·均值时延·均值 token）
import argparse
import http.client
import json
import time
from pathlib import Path

from svl2_json_rescue import json_rescue  # 同目录导入（驱动器与提取器同仓分发）

STYLES = ["pop_ballad", "gufeng", "suspense", "comedy", "rock", "edm",
          "hiphop", "jazz", "folk", "rnb", "orchestral", "ambient"]
EXPECTED_B = ["pop_ballad", "gufeng", "edm", "ambient", "hiphop"]

SYS_A = (
    "你是MV分镜师。把给定歌词分段转为视觉脚本。只输出JSON,不要任何多余文本:"
    '{"scenes":[{"section":"段落名","visual":"该段画面的视觉描述,20-40字,含主体/场景/光线/运动"}]},'
    "按歌词段落顺序,每段一条。"
)
SYS_B = (
    "你是音乐风格标签归一器。把用户的杂乱风格标签映射到唯一规范风格键。只输出JSON:"
    '{"style":"<下方12键之一>","confidence":0到1的小数}。'
    f"合法键: {json.dumps(STYLES, ensure_ascii=False)}"
)
SYS_C = (
    "你是短剧对白润色师。把生硬台词改自然口语,保留原意与字数量级(±30%),增强情绪与潜台词。"
    '只输出JSON: {"line":"润色后台词"}。'
)
CASES = {
    "A": [
        "[Chorus]\n我要的是你 真实的你\n让我欢喜 也让我哭泣\n你是感情拼图 唯一的那块\n拼凑我生命 最真的精彩\n我要的是你 破碎的你\n拥我入怀 也让我叹息",
        "[Verse 1]\n宁愿你有缺点 让我宠爱\n不要你完美 不理不睬\n你是我的蓝天 偶有灰暗\n也是我唯一 的色彩",
        "[Verse 1]\n三十的街 有点长\n肩上行囊 有点烫\n一路奔跑 一身伤\n撞破了南墙 不回头望\n[Pre-Chorus]\n破茧成蝶 不惑的我\n看镜湖 不起波澜",
        "[Bridge]\n半生已过 如云烟\n我是渡船 也是过客\n不再问 为何来过\n只敬这 岁月如歌",
        "[Chorus]\nI'm not alone, though I'm far from home\n在陌生的城市 心却如此温热\nDreaming of the stars, chasing down the light\n穿越迷雾 看见未来的轮廓",
    ],
    "B": [
        "抒情 慢歌 流行 抒情流行 治愈",
        "中国风 古装 戏腔 国风 唯美",
        "电子舞曲 夜店 EDM 蹦迪 劲爆",
        "轻音乐 冥想 钢琴 环境音 睡前 放松",
        "说唱 嘻哈 街头 flow 中文说唱",
    ],
    "C": [
        "我现在心情很不好,因为你迟到了两个小时,而且没有提前告诉我。",
        "这个方案确实存在一些问题，我们需要再讨论一下才能做决定。",
        "你不要走了好吗,我其实是很喜欢你的,只是以前没有说出口。",
        "妈,我在外地工作很忙,过年就不回去了,你自己注意身体。",
        "老板,关于涨工资的事情,我觉得我应该得到加薪,因为我工作很努力。",
    ],
}
SYS = {"A": SYS_A, "B": SYS_B, "C": SYS_C}
BASELINES = {"a4b": "15/15 @ p50 2.2s（OPS eval4，对照基线）"}


def call(host, port, model, sysp, user, max_tokens=2048, think_off=True, retries=1):
    """think_off=True 与网关生产路由同参（aify 默认注入 enable_thinking:false）。
    2026-11-01 复盘：direct 电池首跑未关思考 → A 类 775-2030 tok/65-80s 全是思考
    token（A#5 finish=length 即思考吃光预算）——层属结论必须与网关同参才成立。
    错误韧性：连接断开/无 choices 响应 → 记录错误、单次重试、不中断电池。"""
    payload = {"model": model,
               "messages": [{"role": "system", "content": sysp},
                            {"role": "user", "content": user}],
               "max_tokens": max_tokens, "temperature": 0, "stream": False}
    if think_off:
        payload["chat_template_kwargs"] = {"enable_thinking": False}
    t0 = time.time()
    last_err = None
    for attempt in range(retries + 1):
        try:
            conn = http.client.HTTPConnection(host, port, timeout=300)
            conn.request("POST", "/v1/chat/completions", body=json.dumps(payload),
                         headers={"Content-Type": "application/json"})
            resp = conn.getresponse()
            body = resp.read()
            conn.close()
            try:
                data = json.loads(body)
            except Exception:
                last_err = f"http {resp.status} non-json body: {body[:200]!r}"
                time.sleep(3)
                continue
            if "choices" not in data:
                last_err = (f"http {resp.status} no-choices: "
                            f"{json.dumps(data, ensure_ascii=False)[:300]}")
                time.sleep(3)
                continue
            msg = data["choices"][0]["message"]
            return {"wall_s": round(time.time() - t0, 1),
                    "content": msg.get("content") or "",
                    "reasoning": msg.get("reasoning_content") or "",
                    "completion_tokens": data.get("usage", {}).get("completion_tokens"),
                    "finish_reason": data["choices"][0].get("finish_reason")}
        except (http.client.HTTPException, OSError) as e:
            last_err = f"{type(e).__name__}: {e}"
            time.sleep(3)
    return {"wall_s": round(time.time() - t0, 1),
            "content": "", "reasoning": "",
            "completion_tokens": None,
            "finish_reason": f"error: {last_err}"}


def extract_json(s):  # eval4 判分器原样（对照口径不变）
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    a, b = s.find("{"), s.rfind("}")
    return json.loads(s[a:b + 1]) if a >= 0 < b else None


def judge(task, idx, content):  # eval4 逐字同口径
    try:
        j = extract_json(content)
    except Exception:
        return False, None
    if j is None:
        return False, None
    if task == "A":
        ok = bool(j.get("scenes") and all(
            s.get("section") and s.get("visual") and 8 <= len(s.get("visual", "")) <= 80
            for s in j["scenes"]) and len(j["scenes"]) >= (2 if idx == 3 else 1))
        return ok, len(j["scenes"])
    if task == "B":
        st = j.get("style")
        return st == EXPECTED_B[idx - 1], st
    ln = j.get("line", "")
    src = CASES[task][idx - 1]
    ok = bool(ln) and 0.5 <= len(ln) / len(src) <= 2.0 and ln != src
    return ok, (ln[:30] if isinstance(ln, str) else ln)


def judge_rescued(task, idx, content):
    obj, mode = json_rescue(content)
    if obj is None:
        return False, None, mode
    # 与 judge 同判但作用于提取器输出（ rescued 电池专用）
    j = obj
    if task == "A":
        ok = bool(j.get("scenes") and all(
            s.get("section") and s.get("visual") and 8 <= len(s.get("visual", "")) <= 80
            for s in j["scenes"]) and len(j["scenes"]) >= (2 if idx == 3 else 1))
        return ok, len(j["scenes"]), mode
    if task == "B":
        st = j.get("style")
        return st == EXPECTED_B[idx - 1], st, mode
    ln = j.get("line", "")
    src = CASES[task][idx - 1]
    ok = bool(ln) and 0.5 <= len(ln) / len(src) <= 2.0 and ln != src
    return ok, (ln[:30] if isinstance(ln, str) else ln), mode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--battery", choices=["direct", "gateway", "rescued"], required=True)
    ap.add_argument("--host", default=None, help="覆盖默认 host（direct 默认 100.65.64.49）")
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--model", default="nemotron-3.5-super-vl")
    ap.add_argument("--think", choices=["off", "on"], default="off",
                    help="off=与网关生产路由同参（默认）；on=复现首跑思考污染口径")
    ap.add_argument("--pause", type=float, default=2.0,
                    help="请求间隔秒数（生产强推理位保护，默认 2.0）")
    ap.add_argument("--out", default=None, help="结果 JSON 落盘路径（默认不落盘）")
    args = ap.parse_args()

    if args.battery == "direct":
        host, port = args.host or "100.65.64.49", args.port or 8888
    else:
        host, port = args.host or "100.126.132.112", args.port or 10086

    results = []
    for task in ("A", "B", "C"):
        for idx in range(1, 6):
            r = call(host, port, args.model, SYS[task], CASES[task][idx - 1],
                     think_off=(args.think == "off"))
            if args.battery == "rescued":
                ok, got, mode = judge_rescued(task, idx, r["content"])
                r["rescue_mode"] = mode
            else:
                ok, got = judge(task, idx, r["content"])
            r.update(battery=args.battery, task=task, idx=idx, passed=ok, got=got)
            results.append(r)
            print(f"{args.battery} {task}#{idx}  wall={r['wall_s']:6.1f}s "
                  f"tok={r['completion_tokens']} finish={r['finish_reason']} "
                  f"pass={ok} content_len={len(r['content'])}", flush=True)
            if not ok and r["content"]:
                print(f"    ↳ fail preview: {r['content'][:120]!r}", flush=True)
            if str(r["finish_reason"]).startswith("error"):
                print(f"    ↳ 请求错误（已记录，电池继续）: {r['finish_reason'][:200]}",
                      flush=True)
            time.sleep(args.pause)

    walls = [r["wall_s"] for r in results]
    toks = [r["completion_tokens"] or 0 for r in results]
    print(f"\n== {args.battery} @ {host}:{port}: "
          f"pass {sum(1 for r in results if r['passed'])}/15  "
          f"p50 {sorted(walls)[7]:.1f}s  avg_tok {sum(toks)/len(toks):.0f}  "
          f"(基线 {BASELINES['a4b']})")
    for task in ("A", "B", "C"):
        ts = [r for r in results if r["task"] == task]
        print(f"  {task}: {sum(1 for r in ts if r['passed'])}/5  "
              f"avg_wall {sum(r['wall_s'] for r in ts)/5:.1f}s  "
              f"avg_tok {sum(r['completion_tokens'] or 0 for r in ts)/5:.0f}")
    if args.out:
        Path(args.out).write_text(json.dumps(results, ensure_ascii=False, indent=1))
        print(f"落盘: {args.out}")


if __name__ == "__main__":
    main()
