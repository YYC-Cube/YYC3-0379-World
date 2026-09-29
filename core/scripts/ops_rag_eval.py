#!/usr/bin/env python3
# file: ops_rag_eval.py
# description: ops_rag 检索评测——golden set 跑批（Top-K 命中率 + 时延，多配置对照）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [script],[eval],[rag],[golden-set],[rerank]
#
# 用法（NAS 网关本机或可达端）：
#   python3 core/scripts/ops_rag_eval.py --endpoint http://localhost:8000 --api-key sk-xxx \
#       --library main --top-k 3            # 单配置（纯向量）
#   ... --all-configs                      # 四配置对照（vec / hybrid / rerank / hybrid+rerank）
#   ... --fixture core/scripts/ops_rag_golden_v3.json --json-out /tmp/eval.json
# 匹配规则（与固化件一致）：source.startswith(source_prefix) AND heading.startswith(heading_prefix)
# 依赖：仅标准库（NAS python3 直接可跑）。

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, List

DEFAULT_FIXTURE = Path(__file__).parent / "ops_rag_golden_v3.json"

CONFIGS = [
    {"name": "vec", "hybrid": False, "rerank": False},
    {"name": "hybrid", "hybrid": True, "rerank": False},
    {"name": "rerank", "hybrid": False, "rerank": True},
    {"name": "hybrid+rerank", "hybrid": True, "rerank": True},
]

# 装饰字符（emoji/变体选择符）：语料标题常见「📂/🖥️/🎯 文档关联图」式前缀，语义与裸标题一致
_EMOJI_RE = re.compile(
    r"[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\ufe0f\u200d]+"
)


def _norm_heading(h: str) -> str:
    return _EMOJI_RE.sub("", h or "").strip()


def is_hit(result: Dict[str, Any], item: Dict[str, str]) -> bool:
    """source 前缀匹配 + heading 去装饰后包含匹配（emoji 前缀/「YYC³ 」式标题
    前缀不构成语义差异；contains 而非 startswith 以兼容「九、xxx」「使用 xxx」）"""
    if not result.get("source", "").startswith(item["source_prefix"]):
        return False
    return _norm_heading(item["heading_prefix"]) in _norm_heading(
        result.get("heading", "")
    )


def call_ops(
    endpoint: str, api_key: str, payload: Dict[str, Any], timeout: float
) -> Dict[str, Any]:
    req = urllib.request.Request(
        endpoint.rstrip("/") + "/v1/rag/ops",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", "X-API-Key": api_key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def run_config(
    endpoint: str,
    api_key: str,
    library: str,
    cfg: Dict[str, Any],
    items: List[Dict[str, str]],
    top_k: int,
    timeout: float,
    verbose: bool = False,
) -> Dict[str, Any]:
    hits, latencies, misses = 0, [], []
    t_all = time.perf_counter()
    for item in items:
        payload = {
            "query": item["query"],
            "top_k": top_k,
            "library": library,
            "hybrid": cfg["hybrid"],
            "rerank": cfg["rerank"],
        }
        t0 = time.perf_counter()
        try:
            out = call_ops(endpoint, api_key, payload, timeout)
        except urllib.error.HTTPError as e:
            print(
                f"[ERR] q{item['id']} HTTP {e.code}: {e.read()[:120]}", file=sys.stderr
            )
            out = {"results": []}
        except Exception as e:  # noqa: BLE001 — 跑批不因单题中断
            print(f"[ERR] q{item['id']}: {e}", file=sys.stderr)
            out = {"results": []}
        latencies.append(int((time.perf_counter() - t0) * 1000))
        top = out.get("results", [])[:top_k]
        if any(is_hit(r, item) for r in top):
            hits += 1
        else:
            misses.append(
                {
                    "id": item["id"],
                    "query": item["query"],
                    "expect": f"{item['source_prefix']}::{item['heading_prefix']}",
                    "got": [
                        f"{r.get('source','')[:30]}::{r.get('heading','')[:20]}"
                        for r in top
                    ],
                }
            )
    n = len(items)
    return {
        "config": cfg["name"],
        "library": library,
        "hybrid": cfg["hybrid"],
        "rerank": cfg["rerank"],
        "top_k": top_k,
        "hits": hits,
        "n": n,
        "hit_rate": round(hits / n, 4) if n else 0.0,
        "avg_ms": round(sum(latencies) / len(latencies)) if latencies else 0,
        "total_s": round(time.perf_counter() - t_all, 1),
        "misses": misses if verbose else len(misses),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="ops_rag golden set 评测")
    ap.add_argument("--endpoint", default="http://localhost:8000")
    ap.add_argument("--api-key", default=os.environ.get("API_KEY", ""))
    ap.add_argument("--library", default="main")
    ap.add_argument("--top-k", type=int, default=3)
    ap.add_argument("--fixture", default=str(DEFAULT_FIXTURE))
    ap.add_argument("--all-configs", action="store_true", help="四配置对照")
    ap.add_argument("--hybrid", action="store_true")
    ap.add_argument("--rerank", action="store_true")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--verbose", action="store_true", help="打印未命中明细")
    ap.add_argument("--json-out", default="")
    args = ap.parse_args()

    if not args.api_key:
        print("[ERR] 缺 API Key（--api-key 或环境变量 API_KEY）", file=sys.stderr)
        return 2
    fixture = json.loads(Path(args.fixture).read_text(encoding="utf-8"))
    items = fixture["items"]
    print(
        f"fixture={fixture.get('version')} items={len(items)} library={args.library} "
        f"top_k={args.top_k} endpoint={args.endpoint}"
    )

    configs = (
        CONFIGS
        if args.all_configs
        else [{"name": "custom", "hybrid": args.hybrid, "rerank": args.rerank}]
    )
    results = []
    for cfg in configs:
        r = run_config(
            args.endpoint,
            args.api_key,
            args.library,
            cfg,
            items,
            args.top_k,
            args.timeout,
            args.verbose,
        )
        results.append(r)
        note = (
            "（rerank 降级原序）"
            if cfg["rerank"] and any("降级" in str(x) for x in [r])
            else ""
        )
        print(
            f"{r['config']:<16} hit@{args.top_k} = {r['hits']}/{r['n']}"
            f" ({r['hit_rate']*100:.1f}%)  avg {r['avg_ms']}ms  total {r['total_s']}s {note}"
        )
        if args.verbose and isinstance(r["misses"], list):
            for m in r["misses"][:6]:
                print(f"  MISS q{m['id']}: expect {m['expect']} | got {m['got'][:2]}")

    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps(
                {"fixture": fixture.get("version"), "results": results},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        print(f"json -> {args.json_out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
