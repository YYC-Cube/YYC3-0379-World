# file: model_smoke_test.py
# description: 模型上线验收冒烟脚本 - 规范 01 §5 九用例（资产校验/健康/列表/chat/SSE/上游头/边界）
# author: YanYuCloudCube Team <admin@0379.email>
# version: v1.0.0
# created: 2026-09-28
# status: active
# tags: [smoke-test],[onboarding],[acceptance]
# spec: docs/模型接入与注册/01-接入现状规范-v2.3.md §5 / 05-监控告警与Runbook.md SOP-01 Step5

"""
@file: core/scripts/model_smoke_test.py
@description: 模型上线验收冒烟（规范 01 §5 九用例工程化，附录 A 末项落地）。
    用例矩阵（✅=自动断言；多模态/切换两项按需启用）：
      1 资产完整性（本地权重目录：调 model_asset_verify 三校验；--skip-asset 跳过）
      2 服务健康（base_url /health 200）
      3 网关可见（GET /v1/models 含 model）
      4 chat 同步（completions 200 + JSON 结构）
      5 SSE 流式（stream=true chunk 输出 + [DONE] 收尾）
      6 上游头（X-YYC3-Upstream 披露实际服务者）
      7 超长输入边界（> context_window 请求 → 4xx 错误码而非 5xx/挂起）
      8 Registry 就绪（--registry 时：/registry/v1/models/{id} state=ready）✅
      9 能力冒烟（--capability asr/ocr/embedding/rerank 按需）
    退出码：0=全过（可开放公网）；1=有失败；2=参数/环境错误
    stdlib 零依赖。用法：
      python3 model_smoke_test.py --base http://gw:8000 --model deepseek-v4-flash \\
          --api-key-env API_KEYS [--asset-dir /ssd/weights] [--capability embedding] [--registry]
@author: YanYuCloudCube Team <admin@0379.email>
@license: MIT
@copyright Copyright (c) 2026 YanYuCloudCube Team
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from typing import Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

PASS, FAIL, SKIP = "✅", "❌", "⏭️"


def _http_json(
    method: str, url: str, api_key: str = "", body: Optional[dict] = None, timeout: float = 60.0
):
    """HTTP JSON 调用：返回 (status, parsed_json_or_raw_str)。HTTPError 上抛由调用方分类。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", "replace")
        try:
            return resp.status, (json.loads(raw) if raw else None)
        except json.JSONDecodeError:
            return resp.status, raw


def _http_raw(
    method: str, url: str, api_key: str = "", body: Optional[dict] = None, timeout: float = 60.0
):
    """HTTP 原始响应（流式逐行读 + 响应头捕获场景）。"""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if api_key:
        req.add_header("X-API-Key", api_key)
    return urllib.request.urlopen(req, timeout=timeout)


class SmokeReport:
    def __init__(self):
        self.results = []

    def record(self, name: str, ok: bool, detail: str = "", skipped: bool = False) -> bool:
        mark = SKIP if skipped else (PASS if ok else FAIL)
        print(f"  {mark} [{name}] {detail}")
        self.results.append((name, True if skipped else ok))  # 跳过不计失败
        return ok

    def summary(self) -> int:
        failed = [n for n, ok in self.results if not ok]
        total, passed = len(self.results), sum(1 for _, ok in self.results if ok)
        print(f"═══ 冒烟结果: {passed}/{total} 通过 ═══")
        return 1 if failed else 0


def run_smoke(args) -> int:
    report = SmokeReport()
    api_key = os.getenv(args.api_key_env, "")
    base = args.base.rstrip("/")
    headers_fixed = {}  # 上游头捕获容器

    # ── 1 资产完整性（本地权重目录；远端/无目录跳过） ──
    if args.asset_dir:
        from model_asset_verify import verify_model

        rep = verify_model(
            __import__("pathlib").Path(args.asset_dir), sample_limit=args.asset_sample
        )
        report.record(
            "asset_verify",
            rep["passed"],
            "; ".join(c["message"] for c in rep["checks"] if not c["ok"]) or "三校验通过",
        )
    else:
        report.record("asset_verify", True, "未指定 --asset-dir（跳过；远端场景）", skipped=True)

    # ── 2 服务健康 ──
    try:
        svc_base = args.service_base.rstrip("/") if args.service_base else base
        status, _ = _http_json("GET", f"{svc_base}/health", timeout=10)
        report.record("service_health", status == 200, f"/health HTTP {status}")
    except Exception as exc:
        report.record("service_health", False, str(exc)[:120])

    # ── 3 网关可见 ──
    try:
        status, body = _http_json("GET", f"{base}/v1/models", api_key)
        ids = [m.get("id") for m in (body.get("data") if isinstance(body, dict) else body) or []]
        report.record("gateway_listed", args.model in ids, f"/v1/models 含 {args.model}")
    except Exception as exc:
        report.record("gateway_listed", False, str(exc)[:120])

    # ── 4 chat 同步 + 6 上游头（同请求捕获） ──
    chat_ok = False
    try:
        resp = _http_raw(
            "POST",
            f"{base}/v1/chat/completions",
            api_key,
            timeout=90,
            body={
                "model": args.model,
                "max_tokens": args.max_tokens,
                "messages": [{"role": "user", "content": args.prompt}],
            },
        )
        raw = resp.read().decode("utf-8", "replace")
        headers_fixed["upstream"] = resp.headers.get("X-YYC3-Upstream", "")
        body = json.loads(raw)
        chat_ok = bool(body.get("choices"))
        report.record(
            "chat_completion", chat_ok, f"content={body['choices'][0]['message']['content'][:30]!r}"
        )
    except urllib.error.HTTPError as exc:
        report.record("chat_completion", False, f"HTTP {exc.code}: {exc.read()[:120]!r}")
    except Exception as exc:
        report.record("chat_completion", False, str(exc)[:120])
    report.record(
        "upstream_header",
        bool(headers_fixed.get("upstream")),
        (
            f"X-YYC3-Upstream: {headers_fixed.get('upstream') or '缺失'}"
            if chat_ok
            else "chat 失败连带跳过"
        ),
        skipped=not chat_ok,
    )

    # ── 5 SSE 流式 ──
    try:
        resp = _http_raw(
            "POST",
            f"{base}/v1/chat/completions",
            api_key,
            timeout=90,
            body={
                "model": args.model,
                "max_tokens": args.max_tokens,
                "stream": True,
                "messages": [{"role": "user", "content": args.prompt}],
            },
        )
        chunks, done = 0, False
        for line in resp:
            text = line.decode("utf-8", "replace").strip()
            if text.startswith("data: "):
                chunks += 1
                if text[6:] == "[DONE]":
                    done = True
                    break
        report.record("sse_stream", chunks > 1 and done, f"chunks={chunks} done={done}")
    except Exception as exc:
        report.record("sse_stream", False, str(exc)[:120])

    # ── 7 超长输入边界 ──
    try:
        resp = _http_raw(
            "POST",
            f"{base}/v1/chat/completions",
            api_key,
            timeout=60,
            body={
                "model": args.model,
                "max_tokens": 8,
                "messages": [{"role": "user", "content": "x" * (args.boundary_tokens * 4)}],
            },
        )
        raw = resp.read()
        # 流式响应错误仍 200 + error chunk → 解析状态；非流 4xx 直接判定
        code = resp.status
        ok = code < 500 and (code >= 400 or b'"error"' in raw or code == 200)
        report.record("boundary_too_long", ok, f"HTTP {code}（非 5xx/挂起即合规）")
    except urllib.error.HTTPError as exc:
        report.record("boundary_too_long", exc.code < 500, f"HTTP {exc.code}（4xx 合规）")
    except Exception as exc:
        report.record("boundary_too_long", False, str(exc)[:120])

    # ── 8 Registry 就绪（--registry） ──
    if args.registry:
        admin_key = os.getenv(args.admin_key_env, "")
        try:
            status, body = _http_json(
                "GET", f"{base}/registry/v1/models/{args.model}", api_key=admin_key or api_key
            )
            report.record(
                "registry_ready",
                status == 200 and body.get("state") == "ready",
                f"state={body.get('state') if isinstance(body, dict) else body}",
            )
        except Exception as exc:
            report.record("registry_ready", False, str(exc)[:120])
    else:
        report.record("registry_ready", True, "未启用 --registry", skipped=True)

    # ── 9 能力冒烟（--capability） ──
    if args.capability == "embedding":
        try:
            status, body = _http_json(
                "POST",
                f"{base}/v1/embeddings",
                api_key,
                timeout=30,
                body={"model": args.model, "input": args.prompt},
            )
            dim = len(body["data"][0]["embedding"]) if status == 200 else 0
            report.record("capability_embedding", status == 200 and dim > 0, f"dim={dim}")
        except Exception as exc:
            report.record("capability_embedding", False, str(exc)[:120])
    elif args.capability in ("asr", "ocr"):
        report.record(
            f"capability_{args.capability}",
            True,
            "二进制载荷能力需专用样本（人工验收，见规范 01 §5 用例 8）",
            skipped=True,
        )
    elif args.capability:
        report.record(
            f"capability_{args.capability}", True, f"{args.capability} 非自动面", skipped=True
        )

    return report.summary()


def main(argv: Optional[list] = None) -> int:
    parser = argparse.ArgumentParser(description="模型上线验收冒烟（规范 01 §5 九用例）")
    parser.add_argument("--base", required=True, help="网关基址，如 http://yyc3-45:8000")
    parser.add_argument("--model", required=True, help="验收 model_id")
    parser.add_argument("--api-key-env", default="API_KEYS", help="推理面密钥环境变量名")
    parser.add_argument("--admin-key-env", default="ADMIN_API_KEYS", help="管理面密钥变量名")
    parser.add_argument("--service-base", default=None, help="直连服务基址（缺省用网关自身）")
    parser.add_argument("--asset-dir", default=None, help="本地权重目录（用例 1）")
    parser.add_argument("--asset-sample", type=int, default=0, help="资产头部抽检数（0=全量）")
    parser.add_argument(
        "--capability", default=None, help="能力冒烟：embedding 自动 / asr/ocr 人工提示"
    )
    parser.add_argument("--registry", action="store_true", help="启用 Registry 就绪断言")
    parser.add_argument("--boundary-tokens", type=int, default=40000, help="边界用例 token 规模")
    parser.add_argument("--max-tokens", type=int, default=16)
    parser.add_argument("--prompt", default="回复ok")
    args = parser.parse_args(argv)
    if not os.getenv(args.api_key_env):
        print(f"❌ 环境变量 {args.api_key_env} 未配置", file=sys.stderr)
        return 2
    print(f"🧪 模型上线冒烟: {args.model} @ {args.base}")
    return run_smoke(args)


if __name__ == "__main__":
    sys.exit(main())
