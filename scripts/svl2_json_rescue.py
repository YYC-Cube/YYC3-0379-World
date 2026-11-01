# svl2 A 类格式缺陷 · JSON 提取器参考实现（U16 移交修复③）
# 算法: 剥围栏 → raw_decode 逐个提完整顶层对象（天然忽略 ]}} 尾巴）
#       → 多文档且键集一致时合并数组+内容去重（重复副本去重 / 碎片合并）→ 单文档零扰动
# 自测: 内嵌 eval4 归档的 svl2 A 类 5 条原始输出（含 4 败 1 过），直接运行即复核 §3.2 推演表:
#       python3 scripts/svl2_json_rescue.py     → 期望 5/5 pass、B/C 零扰动断言
# 权威依据: docs/架构与部署/svl2-A类格式缺陷-定位与修复-20261101.md
import json
import sys


def json_rescue(s, merge_arrays=True, dedupe=True):
    """从模型原始输出稳健提取首个/合并后的顶层 JSON 对象。

    返回 (obj, mode)：mode ∈ single / merged / garbage_tail（诊断用）；
    无法提取返回 (None, "fail")。
    """
    if not isinstance(s, str):
        return None, "fail"
    t = s.strip()
    if t.startswith("```"):
        parts = t.split("\n", 1)
        t = parts[1].rsplit("```", 1)[0] if len(parts) > 1 else t
    dec = json.JSONDecoder()
    docs, i, tail_garbage = [], 0, False
    while i < len(t):
        while i < len(t) and t[i] in " \t\r\n":
            i += 1
        if i >= len(t):
            break
        if t[i] != "{":  # 剩余非对象起点：若已提过文档则为垃圾尾，否则整体失败
            tail_garbage = bool(docs)
            break
        try:
            obj, end = dec.raw_decode(t, i)
        except ValueError:
            tail_garbage = bool(docs)  # 半截对象同垃圾尾处理（保已有文档）
            break
        docs.append(obj)
        i = end
    if not docs:
        return None, "fail"
    if len(docs) == 1:
        return docs[0], "garbage_tail" if tail_garbage else "single"
    if not (merge_arrays and all(isinstance(d, dict) for d in docs)):
        return docs[0], "multi_first"
    keys = sorted(docs[0])
    if not all(sorted(d) == keys for d in docs):
        return docs[0], "multi_first"
    out = {}
    for k in keys:
        vals = [d[k] for d in docs]
        if all(isinstance(v, list) for v in vals):
            merged, seen = [], set()
            for v in vals:
                for item in v:
                    h = json.dumps(item, ensure_ascii=False, sort_keys=True)
                    if not dedupe or h not in seen:
                        seen.add(h)
                        merged.append(item)
            out[k] = merged
        else:
            out[k] = vals[0]
    return out, "merged"


# ── eval4 同口径判分（A 类；B/C 供回归复用见 replay 驱动器）────────────────
def _extract_json_eval4(s):  # noqa: ANN001 — 判分器原样拷贝（对照组）
    s = s.strip()
    if s.startswith("```"):
        s = s.split("\n", 1)[1].rsplit("```", 1)[0]
    a, b = s.find("{"), s.rfind("}")
    return json.loads(s[a : b + 1]) if a >= 0 < b else None


def judge_a_eval4(idx, content):  # noqa: ANN001
    try:
        j = _extract_json_eval4(content)
    except Exception:
        return False, None
    if j is None:
        return False, None
    ok = bool(
        j.get("scenes")
        and all(
            s.get("section") and s.get("visual") and 8 <= len(s.get("visual", "")) <= 80
            for s in j["scenes"]
        )
        and len(j["scenes"]) >= (2 if idx == 3 else 1)
    )
    return ok, len(j["scenes"])


def judge_a_rescued(idx, content):  # noqa: ANN001
    obj, mode = json_rescue(content)
    if obj is None:
        return False, None, mode
    ok = bool(
        obj.get("scenes")
        and all(
            s.get("section") and s.get("visual") and 8 <= len(s.get("visual", "")) <= 80
            for s in obj["scenes"]
        )
        and len(obj["scenes"]) >= (2 if idx == 3 else 1)
    )
    return ok, len(obj["scenes"]), mode


# ── 自测夹具: eval4_results.json svl2 A 电池 5 条原始 content（归档复刻）────
SAMPLES = {
    1: '{"scenes":[{"section":"Chorus","visual":"特写两人紧握的手，昏暗房间中暖光勾勒轮廓，镜头缓慢推进，捕捉欢喜与悲伤交织的表情。"}]}\n\n{\n  "scenes": [\n    {\n      "section": "Chorus",\n      "visual": "特写两人紧握的手，昏暗房间中暖光勾勒轮廓，镜头缓慢推进，捕捉欢喜与悲伤交织的表情。"\n    }\n  ]\n}',
    2: '{"scenes":[{"section":"Verse 1","visual":"特写镜头，主角温柔宠溺地凝视爱人，柔和自然光，背景为蔚蓝天空偶有灰暗云层，缓慢推镜。"}]}\n\n{"scenes":[{"section":"Verse 1","visual":"主角在蓝天下与爱人并肩漫步，光影交错，画面色彩饱和，唯一的色彩聚焦于爱人身上，慢动作拍摄。"}]}\n\n{"scenes":[{"section":"Verse 1","visual":"特写爱人侧脸，灰暗光线笼罩，主角手轻抚其发，表情坚定，背景虚化，强调宠爱与接纳。"}]}\n\n{"scenes":[{"section":"Verse 1","visual":"主角与爱人对望，蓝天背景下色彩渐变，唯有爱人衣物色彩鲜明，镜头缓慢环绕，氛围温馨。"}]}',
    3: '{"scenes":[{"section":"Verse 1","visual":"孤独青年背着沉重行囊在漫长街道奔跑，昏暗路灯下身影拉长，衣衫破损，镜头跟拍前行。"},{"section":"Pre-Chorus","visual":"青年站在镜湖边，平静面容映在水面，柔和晨光洒在身上，水面无波，镜头缓缓推近。"}]}}',
    4: '{"scenes":[{"section":"Bridge","visual":"模糊的云烟背景，一艘破旧渡船在雾气中缓缓前行，主体孤独伫立，暖黄柔和光线，镜头缓慢推进。"}]}',
    5: '{"scenes":[{"section":"Chorus","visual":"孤独旅人在陌生城市夜景中行走，霓虹灯光映照温暖面容，镜头缓慢跟随前移，远方星光与迷雾交织，勾勒未来轮廓。"}]}}',
}
CLEAN_SINGLE_LINE = '{"style":"edm","confidence":0.99}'  # B/C 回归: 单行短 JSON 零扰动


def _selftest():
    print("== svl2_json_rescue 自测（归档 5 例 + 回归 1 例）==")
    all_pass = True
    for idx, raw in SAMPLES.items():
        old_ok, old_got = judge_a_eval4(idx, raw)
        new_ok, new_got, mode = judge_a_rescued(idx, raw)
        all_pass &= new_ok
        print(
            f"A#{idx}: eval4={old_ok},{old_got}  rescued={new_ok},{new_got}  mode={mode}"
        )
    obj, mode = json_rescue(CLEAN_SINGLE_LINE)
    clean_ok = obj == json.loads(CLEAN_SINGLE_LINE) and mode == "single"
    all_pass &= clean_ok
    print(f"回归(单行短 JSON): {'零扰动 ✓' if clean_ok else '被改动 ✗'} mode={mode}")
    print(f"结论: {'5/5 + 零回归 — 提取器推演成立' if all_pass else '存在未达预期样本，检查算法'}")
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(_selftest())
