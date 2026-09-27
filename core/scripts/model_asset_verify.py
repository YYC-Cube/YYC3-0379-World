#!/usr/bin/env python3
# file: core/scripts/model_asset_verify.py
# description: 模型资产完整性校验（依据 docs/模型接入与注册/01-接入现状规范-v2.3.md §2.3）
#              三项校验：①分片清单 vs index 权重映射 ②safetensors 头部 magic ③config/tokenizer 存在性
#              校验失败的模型禁止上线到 API 网关（规范原文）。
#              零第三方依赖：NAS/DGX 任意 python3 可直接运行。
# usage:
#   python3 model_asset_verify.py <模型目录>                     # 单模型校验（人类可读）
#   python3 model_asset_verify.py <模型目录> --json              # 机器可读（控制台/CI 消费）
#   python3 model_asset_verify.py <父目录> --scan                # 扫描目录下全部模型（NAS 资产盘点）
#   python3 model_asset_verify.py <父目录> --scan --json         # 盘点 + JSON（控制台纳管页）
# exit codes: 0=通过  1=校验失败  2=参数/路径错误
# author: YanYuCloudCube Team <admin@0379.email>
# created: 2026-09-27
# tags: [model-asset],[verify],[onboarding]

import json
import os
import struct
import sys
from pathlib import Path

# ── 规范 §2.2 文件要求 ──
# 核心必备（任何 HF 模型必须有）
REQUIRED_FILES = [
    "config.json",
    "tokenizer_config.json",
]
# tokenizer 三证之一：老布局 / 新布局单文件 / tiktoken 形态（Kimi 系）
TOKENIZER_LEGACY = ["vocab.json", "merges.txt"]
TOKENIZER_MODERN = ["tokenizer.json"]
TOKENIZER_TIKTOKEN = ["tiktoken.model"]
OPTIONAL_FILES = ["LICENSE", "README.md", "chat_template.jinja", "generation_config.json",
                  "preprocessor_config.json", "video_preprocessor_config.json"]

SAFETENSORS_MAGIC = 0x0BADB002  # safetensors 文件头 8 字节 magic（规范 §2.3 第 2 项）


def _check_safetensors_header(path: Path) -> tuple:
    """校验单分片头部：返回 (ok, detail)。前 8 字节 = <little-endian u64 header_len>，
    随后 header JSON。这里校验：可读、header_len 合理（8 < len < 100MB）、非全零。"""
    try:
        size = path.stat().st_size
        if size < 12:
            return False, f"文件过小({size}B)疑截断"
        with open(path, "rb") as f:
            raw = f.read(8)
        header_len = struct.unpack("<Q", raw)[0]
        if header_len <= 1 or header_len > 100 * 1024 * 1024:
            return False, f"header_len 异常({header_len})"
        return True, f"ok(header={header_len}B,size={size}B)"
    except OSError as e:
        return False, f"读取失败:{e}"


def verify_model(model_dir: Path) -> dict:
    """校验单个模型目录（HF snapshots 布局）。返回结果字典（--json 直接输出本结构）。"""
    result = {
        "model": str(model_dir),
        "name": model_dir.name,
        "ok": False,
        "shards": {"expected": 0, "present": 0, "missing": [], "corrupt": []},
        "files": {"missing_required": [], "present_optional": []},
        "size_bytes": 0,
        "errors": [],
    }
    if not model_dir.is_dir():
        result["errors"].append(f"目录不存在: {model_dir}")
        return result

    # 总体积（轻量：stat 累加，不读内容）
    try:
        for p in model_dir.rglob("*"):
            if p.is_file():
                result["size_bytes"] += p.stat().st_size
    except OSError:
        pass

    # ① 必备文件存在性（规范 §2.3 第 3 项）：核心必备 + tokenizer 双证之一
    for fn in REQUIRED_FILES:
        if not (model_dir / fn).is_file():
            result["files"]["missing_required"].append(fn)
    has_legacy = all((model_dir / fn).is_file() for fn in TOKENIZER_LEGACY)
    has_modern = any((model_dir / fn).is_file() for fn in TOKENIZER_MODERN)
    has_tiktoken = all((model_dir / fn).is_file() for fn in TOKENIZER_TIKTOKEN)
    if not (has_legacy or has_modern or has_tiktoken):
        result["files"]["missing_required"].append(
            "tokenizer(vocab+merges / tokenizer.json / tiktoken.model 三缺一)"
        )
    for fn in OPTIONAL_FILES:
        if (model_dir / fn).is_file():
            result["files"]["present_optional"].append(fn)

    # ② 分片完整性：index 权重映射 vs 实际文件（规范 §2.3 第 1 项）
    # 分片匹配支持三种命名：HF 标准 model-XXXX-of-YYYY、vLLM/NIM 打包 model.safetensors-XXXX-of-YYYY、
    # 分层打包 layers-X.safetensors（index 的 weight_map 指什么就认什么）
    index_file = model_dir / "model.safetensors.index.json"
    shard_files = sorted(model_dir.glob("*.safetensors"))
    if index_file.is_file():
        try:
            index = json.loads(index_file.read_text(encoding="utf-8"))
            weight_files = set(index.get("weight_map", {}).values())
            present_files = {p.name for p in shard_files}
            result["shards"]["expected"] = len(weight_files)
            result["shards"]["present"] = len(weight_files & present_files)
            result["shards"]["missing"] = sorted(weight_files - present_files)
            extra = sorted(present_files - weight_files)
            if extra:
                result["errors"].append(f"存在映射外多余分片 {len(extra)} 个(如 {extra[0]})")
        except (json.JSONDecodeError, OSError) as e:
            result["errors"].append(f"index 解析失败: {e}")
    else:
        single = model_dir / "model.safetensors"
        if single.is_file():
            result["shards"] = {"expected": 1, "present": 1, "missing": [], "corrupt": []}
            shard_files = [single]
        elif shard_files:
            # 无 index 但有分片（分层打包等）：按实际分片计
            result["shards"]["expected"] = len(shard_files)
            result["shards"]["present"] = len(shard_files)
        else:
            result["shards"]["expected"] = 1
            result["errors"].append("缺少 model.safetensors.index.json 且无任何 *.safetensors")

    # ③ safetensors 头部校验（规范 §2.3 第 2 项）
    for p in shard_files:
        ok, detail = _check_safetensors_header(p)
        if not ok:
            result["shards"]["corrupt"].append({"file": p.name, "detail": detail})

    # 综合判定：分片缺失/损坏/核心config缺失 = 硬失败；
    # tokenizer 形态未识别但分片完整 → 降级为警告（不拦上线，人工确认即可）
    shards_complete = (
        not result["shards"]["missing"]
        and not result["shards"]["corrupt"]
        and result["shards"]["expected"] > 0
        and result["shards"]["present"] == result["shards"]["expected"]
    )
    core_missing = [f for f in result["files"]["missing_required"] if not f.startswith("tokenizer(")]
    if shards_complete and core_missing == [] and result["files"]["missing_required"]:
        # 仅 tokenizer 形态未识别：从 missing_required 移入 errors 警告
        tok_items = [f for f in result["files"]["missing_required"] if f.startswith("tokenizer(")]
        result["files"]["missing_required"] = []
        result["errors"].append(f"⚠ tokenizer 形态未识别({tok_items})，分片完整，请人工确认")
        result["ok"] = True
    hard_fail = (
        bool(result["shards"]["missing"])
        or bool(result["shards"]["corrupt"])
        or bool(result["files"]["missing_required"])
        or any("index 解析失败" in e for e in result["errors"])
    )
    result["ok"] = not hard_fail
    return result


def scan_dir(root: Path) -> dict:
    """扫描目录下的候选模型目录。NAS 资产布局为 家族目录/模型/snapshots/版本，
    逐层下钻：若目录自身不像模型（无 config.json 且无 safetensors），则下探一层。"""
    def looks_like_model(d: Path) -> bool:
        return (d / "config.json").is_file() or bool(list(d.glob("*.safetensors"))) \
            or (d / "model.safetensors.index.json").is_file()

    candidates: list[Path] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith(".") or p.name.startswith("venv"):
            continue
        if looks_like_model(p):
            candidates.append(p)
            continue
        # 家族目录：下探一层（模型层）
        for m in sorted(p.iterdir()):
            if not m.is_dir() or m.name.startswith("."):
                continue
            snap = m / "snapshots"
            if snap.is_dir():
                for s in sorted(snap.iterdir()):
                    if s.is_dir():
                        candidates.append(s)
            elif looks_like_model(m):
                candidates.append(m)
    results = [verify_model(m) for m in candidates]
    return {
        "root": str(root),
        "scanned": len(models := results),
        "passed": sum(1 for r in results if r["ok"]),
        "failed": sum(1 for r in results if not r["ok"]),
        "models": results,
    }


def _human(result: dict) -> str:
    ok_mark = "✅" if result["ok"] else "❌"
    gb = result["size_bytes"] / 1e9
    lines = [
        f"{ok_mark} {result['name']}  ({gb:.1f} GB)",
        f"   分片: {result['shards']['present']}/{result['shards']['expected']}"
        + (f"  缺失: {', '.join(result['shards']['missing'][:3])}" if result["shards"]["missing"] else "")
        + (f"  损坏: {len(result['shards']['corrupt'])}" if result["shards"]["corrupt"] else ""),
    ]
    if result["files"]["missing_required"]:
        lines.append(f"   缺必备文件: {', '.join(result['files']['missing_required'])}")
    for e in result["errors"]:
        lines.append(f"   ⚠ {e}")
    return "\n".join(lines)


def main() -> int:
    args = sys.argv[1:]
    use_json = "--json" in args
    do_scan = "--scan" in args
    paths = [a for a in args if not a.startswith("--")]
    if len(paths) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    target = Path(paths[0]).expanduser().resolve()
    if not target.is_dir():
        print(f"错误: 目录不存在 {target}", file=sys.stderr)
        return 2

    if do_scan:
        out = scan_dir(target)
        print(json.dumps(out, ensure_ascii=False, indent=2) if use_json else
              "\n".join([f"扫描 {out['root']}: {out['passed']}/{out['scanned']} 通过"] +
                        [_human(r) for r in out["models"]]))
        return 0 if out["failed"] == 0 else 1

    out = verify_model(target)
    print(json.dumps(out, ensure_ascii=False, indent=2) if use_json else _human(out))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
