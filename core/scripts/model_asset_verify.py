# file: model_asset_verify.py
# description: NAS 模型资产完整性校验脚本 - 分片对账/safetensors 头部/配置存在性 + 报告落盘
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-27
# status: active
# tags: [model-asset],[verify],[nas],[onboarding-gate]
# spec: docs/模型接入与注册/01-接入现状规范-v2.3.md §2.3

"""
@file: core/scripts/model_asset_verify.py
@description: HF 模型资产完整性校验（入库门禁，规划脚本 P1 落地）。
    三项校验（对齐规范 01 §2.3）：
      ① 分片对账：model.safetensors.index.json 权重映射清单 vs 实际 *.safetensors 文件
      ② safetensors 头部校验：文件前 8 字节 magic（0x5A4B53CD 小端）识别截断/损坏
      ③ 配置存在性：config/tokenizer 必需文件清单
    输出：控制台报告 + 模型目录 model_checksum.report（JSON）
    退出码：0=通过（可上线）；1=校验失败（禁止上线）；2=目录不存在/非模型目录
    用法：
      python core/scripts/model_asset_verify.py /Volume1/yyc3_hd/data/Qwen/Qwen3.8-27B
      python core/scripts/model_asset_verify.py <dir> --json   # 仅输出 JSON（CI 集成）
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import List, Optional

REPORT_NAME = "model_checksum.report"

# safetensors 文件头 magic（小端 uint32）：b'?,ST' = 0x5A4B53CD
SAFETENSORS_MAGIC = b"?,ST"

# 必需配置文件（缺失判定资产不完整）；README/LICENSE 建议保留但不阻断
REQUIRED_CONFIG_FILES = [
    "config.json",
    "tokenizer.json",
    "tokenizer_config.json",
]
# 存在任一组合即可（tokenizer 双形态：tiktoken 型 vocab/merges vs json 型）
TOKENIZER_VOCAB_ALT = ["vocab.json", "vocab.txt", "tokenizer.model"]

INDEX_FILE = "model.safetensors.index.json"


class VerifyResult:
    """单项校验结果（ok=False 时 message 必填）。"""

    def __init__(self, name: str, ok: bool, message: str = "", detail: Optional[dict] = None):
        self.name = name
        self.ok = ok
        self.message = message
        self.detail = detail or {}

    def to_dict(self) -> dict:
        return {"check": self.name, "ok": self.ok, "message": self.message, "detail": self.detail}


def _load_index(model_dir: Path) -> Optional[dict]:
    """读取 safetensors 索引；文件缺失返回 None（单文件模型无索引属合法形态）。"""
    index_path = model_dir / INDEX_FILE
    if not index_path.is_file():
        return None
    try:
        return json.loads(index_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {"__corrupt__": True}


def check_shard_manifest(model_dir: Path) -> VerifyResult:
    """① 分片对账：index.json 权重映射引用的分片文件必须全部存在。"""
    index = _load_index(model_dir)
    if index is None:
        # 无索引：若目录也无任何 safetensors 文件则失败，否则视为单文件/量化包形态放行
        has_st = any(model_dir.glob("*.safetensors"))
        if has_st:
            return VerifyResult(
                "shard_manifest", True, "无 index.json（单文件/量化包形态），跳过分片对账"
            )
        return VerifyResult("shard_manifest", False, "无 safetensors 权重且无 index.json")
    if index.get("__corrupt__"):
        return VerifyResult("shard_manifest", False, f"{INDEX_FILE} 解析失败（文件损坏）")

    weight_map = index.get("weight_map") or {}
    referenced = sorted(set(weight_map.values()))
    if not referenced:
        return VerifyResult("shard_manifest", False, f"{INDEX_FILE} weight_map 为空")

    missing = [s for s in referenced if not (model_dir / s).is_file()]
    # 额外分片（index 未引用）仅提示不阻断（可能混存 LoRA/适配器）
    actual = sorted(p.name for p in model_dir.glob("*.safetensors"))
    extra = [s for s in actual if s not in referenced]

    if missing:
        return VerifyResult(
            "shard_manifest",
            False,
            f"缺失 {len(missing)}/{len(referenced)} 个分片文件",
            {"missing": missing[:20], "referenced_count": len(referenced)},
        )
    msg = f"分片对账通过（{len(referenced)} 个分片全部在位）"
    if extra:
        msg += f"；{len(extra)} 个未引用分片（提示）"
    return VerifyResult(
        "shard_manifest", True, msg, {"referenced_count": len(referenced), "extra": extra}
    )


def check_safetensors_headers(model_dir: Path, sample_limit: int = 0) -> VerifyResult:
    """② 头部校验：每个 safetensors 文件前 8 字节含 magic；sample_limit>0 时只抽前 N 个（大目录提速）。"""
    st_files = sorted(model_dir.glob("*.safetensors"))
    if not st_files:
        return VerifyResult("safetensors_headers", False, "目录中无任何 .safetensors 文件")
    targets = st_files[:sample_limit] if sample_limit > 0 else st_files

    broken: List[str] = []
    truncated: List[str] = []
    for st in targets:
        try:
            with open(st, "rb") as f:
                head = f.read(8)
            if len(head) < 8:
                truncated.append(st.name)
            elif head[:4] != SAFETENSORS_MAGIC:
                broken.append(st.name)
        except OSError as exc:
            broken.append(f"{st.name}（IO: {exc}）")

    problems = []
    if truncated:
        problems.append(f"截断（<8B）: {truncated[:10]}")
    if broken:
        problems.append(f"magic 不符（损坏/非 safetensors）: {broken[:10]}")
    if problems:
        return VerifyResult(
            "safetensors_headers", False, "；".join(problems), {"checked": len(targets)}
        )
    scope = f"（抽检 {len(targets)}/{len(st_files)}）" if sample_limit > 0 else ""
    return VerifyResult(
        "safetensors_headers", True, f"头部校验通过{scope}，共 {len(st_files)} 个权重文件"
    )


def check_config_files(model_dir: Path) -> VerifyResult:
    """③ 配置存在性：必需文件清单（tokenizer 词表双形态兼容）。"""
    missing = [f for f in REQUIRED_CONFIG_FILES if not (model_dir / f).is_file()]
    has_vocab = any((model_dir / f).is_file() for f in TOKENIZER_VOCAB_ALT)
    # tokenizer.json 存在时词表文件可省（fast tokenizer 自包含）
    if not has_vocab and "tokenizer.json" not in missing:
        missing_note = ""
    else:
        missing_note = "" if has_vocab else ";且无任一词表文件"

    if missing:
        return VerifyResult(
            "config_files", False, f"缺失必需文件: {missing}{missing_note}", {"missing": missing}
        )
    return VerifyResult("config_files", True, "配置文件存在性校验通过")


def verify_model(model_dir: Path, sample_limit: int = 0) -> dict:
    """执行全部校验，返回报告 dict（passed=全部通过）。"""
    results = [
        check_shard_manifest(model_dir),
        check_safetensors_headers(model_dir, sample_limit),
        check_config_files(model_dir),
    ]
    return {
        "model_dir": str(model_dir),
        "verified_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "passed": all(r.ok for r in results),
        "checks": [r.to_dict() for r in results],
    }


def write_report(model_dir: Path, report: dict) -> Path:
    """校验报告写入模型目录（规范要求落盘 model_checksum.report）。"""
    out = model_dir / REPORT_NAME
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return out


def _print_report(report: dict) -> None:
    mark = "✅" if report["passed"] else "❌"
    print(f"{mark} 模型资产校验: {report['model_dir']}")
    for c in report["checks"]:
        flag = "✅" if c["ok"] else "❌"
        print(f"  {flag} [{c['check']}] {c['message']}")


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="HF 模型资产完整性校验（入库门禁）")
    parser.add_argument("model_dir", help="模型目录（HF snapshots 根）")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON（CI 集成）")
    parser.add_argument("--sample", type=int, default=0, help="头部抽检数（0=全量）")
    parser.add_argument("--no-report", action="store_true", help="不写 model_checksum.report")
    args = parser.parse_args(argv)

    model_dir = Path(args.model_dir).expanduser().resolve()
    if not model_dir.is_dir():
        print(f"❌ 目录不存在: {model_dir}", file=sys.stderr)
        return 2

    report = verify_model(model_dir, sample_limit=args.sample)
    if not args.no_report:
        try:
            write_report(model_dir, report)
        except OSError as exc:
            print(f"⚠️ 报告写入失败（只读挂载？）: {exc}", file=sys.stderr)

    if args.json:
        print(json.dumps(report, ensure_ascii=False))
    else:
        _print_report(report)
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
