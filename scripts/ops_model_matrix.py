# file: ops_model_matrix.py
# description: 统一 API 全模型可用性矩阵——逐模型实调探针（chat/embeddings/rerank 分发）
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-11-02
# status: active
# tags: [ops],[model-matrix],[smoke],[api]
# stdlib-only（零依赖；与 ops_vkey.py 同款 SSRF 边界校验；--json 输出走 stdout 不落盘）

"""
@file: scripts/ops_model_matrix.py
@description: 对 /v1/models 全量模型逐个实调，输出可用性矩阵（统一 API「可用」的
机器判据 + 指导文档模型目录的数据源）。
@usage:
  export YYC3_API_KEY=<业务key>
  python3 scripts/ops_model_matrix.py                 # 终端矩阵
  python3 scripts/ops_model_matrix.py --json > /tmp/matrix.json   # JSON 走 stdout
@判分: chat=content 非空 / embeddings=向量维度>0 / rerank=results 非空。
"""

import argparse
import ipaddress
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

DEFAULT_BASE = os.environ.get("YYC3_GATEWAY_BASE", "http://100.65.172.88:8000")
_ALLOWED_SCHEMES = ("http", "https")
ALLOW_PRIVATE_TARGETS = True
_HARD_BLOCK_NETS = [
    ipaddress.ip_network(n)
    for n in ("169.254.0.0/16", "0.0.0.0/8", "224.0.0.0/4", "240.0.0.0/4")
]
# 云依赖模型（云适配器通道；自用不上云红线——依赖外部 key，状态如实呈现不隐藏）
_CLOUD_HINTS = ("glm-", "gpt-", "deepseek-chat", "deepseek-coder")


def _validate_base(base: str) -> str:
    """URL 边界校验（SSRF 加固）：仅 http(s)、禁内嵌凭据、DNS 解析后逐 IP
    校验硬禁段（云元数据/链路本地/保留段）；私网/环回显式放行（运维工具语义）。"""
    u = urlparse(base)
    if u.scheme not in _ALLOWED_SCHEMES:
        raise ValueError(f"仅允许 http/https，收到: {u.scheme!r}")
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


def _post(base, key, path, body, timeout):
    req = urllib.request.Request(
        _validate_base(base) + path,
        method="POST",
        data=json.dumps(body).encode(),
        headers={"X-API-Key": key, "Content-Type": "application/json"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return 0, {"error": str(e)}


def _classify(models, upstreams):
    """model -> (capability, class)。精确匹配优先；前缀通配次之；`*` 全捕获与
    无 capability 的上游（纯 chat 池）不参与能力推断（对齐网关侧 fnmatch 语义）。"""
    exact, wild = {}, []
    for u in upstreams:
        cap = u.get("capability")
        if not cap:
            continue
        for pat in u.get("models") or []:
            if pat == "*":
                continue
            if pat.endswith("*"):
                wild.append((pat[:-1], cap))
            else:
                exact[pat] = cap
    out = {}
    for m in models:
        if m in exact:
            cap = exact[m]
        else:
            caps = [c for pre, c in wild if m.startswith(pre)]
            cap = caps[0] if caps else "chat"
        cls = "cloud" if (m.startswith(_CLOUD_HINTS) or m in _CLOUD_HINTS) else "local"
        out[m] = (cap, cls)
    return out


def _probe(base, key, model, cap, timeout):
    """单模型探针：按 capability 分发到对应统一端点，返回 (ok, detail)。"""
    if cap == "embedding":
        code, d = _post(base, key, "/v1/embeddings", {"model": model, "input": "统一API探针"}, timeout)
        emb = (d.get("data") or [{}])[0].get("embedding") or []
        ok = code == 200 and len(emb) > 0
        detail = f"dim={len(emb)}" if ok else f"http={code} {str(d.get('detail') or d.get('error') or '')[:70]}"
    elif cap == "rerank":
        code, d = _post(base, key, "/v1/rerank", {"model": model, "query": "统一API探针", "documents": ["阳光", "雨夹雪", "冰雹"], "top_n": 3}, timeout)
        res = d.get("results") or []
        ok = code == 200 and len(res) > 0
        detail = f"results={len(res)}" if ok else f"http={code} {str(d.get('detail') or d.get('error') or '')[:70]}"
    else:
        code, d = _post(base, key, "/v1/chat/completions", {"model": model, "messages": [{"role": "user", "content": "回复ok即可"}], "max_tokens": 8}, timeout)
        content = (d.get("choices") or [{}])[0].get("message", {}).get("content", "")
        ok = code == 200 and bool(content.strip())
        detail = "content ok" if ok else f"http={code} {str(d.get('detail') or d.get('error') or '')[:70]}"
    return ok, detail


def main():
    ap = argparse.ArgumentParser(description="YYC³ 统一 API 全模型可用性矩阵")
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"网关基址（默认 {DEFAULT_BASE}）")
    ap.add_argument("--key", default=os.environ.get("YYC3_API_KEY", ""), help="业务 API Key（缺省读 YYC3_API_KEY）")
    ap.add_argument("--timeout", type=int, default=45)
    ap.add_argument("--json", dest="json_out", action="store_true", help="末尾追加输出 JSON（stdout，不落盘）")
    args = ap.parse_args()
    if not args.key:
        sys.exit("❌ 缺业务 Key：--key 或 export YYC3_API_KEY=<...>")
    try:
        base = _validate_base(args.base)
    except ValueError as e:
        sys.exit(f"❌ {e}")

    try:
        req = urllib.request.Request(base + "/v1/models", headers={"X-API-Key": args.key})
        with urllib.request.urlopen(req, timeout=15) as r:
            models = [m.get("id") for m in json.loads(r.read().decode())]
    except urllib.error.HTTPError as e:
        sys.exit(f"❌ /v1/models HTTP {e.code}（检查 Key）")
    try:
        req2 = urllib.request.Request(base + "/v1/admin/upstreams", headers={"X-API-Key": args.key})
        with urllib.request.urlopen(req2, timeout=15) as r2:
            upstreams = json.loads(r2.read().decode())
        if isinstance(upstreams, dict):
            upstreams = upstreams.get("upstreams", [])
    except Exception:
        upstreams = []

    plan = _classify(models, upstreams)
    rows = []
    for m in models:
        cap, cls = plan.get(m, ("chat", "local"))
        ok, detail = False, ""
        t0 = time.time()
        probe_path = "/v1/chat/completions"
        if cap == "embedding":
            probe_path = "/v1/embeddings"
        elif cap == "rerank":
            probe_path = "/v1/rerank"
        try:
            ok, detail = _probe(base, args.key, m, cap, args.timeout)
        except Exception as e:
            detail = f"probe error: {e}"
        rows.append({"model": m, "capability": cap, "class": cls, "path": probe_path,
                     "pass": ok, "wall_s": round(time.time() - t0, 1), "detail": detail})
        print(f"{'✅' if ok else '❌'} {m:26} {cap:9} {cls:5} {rows[-1]['wall_s']:5.1f}s  {detail}", flush=True)

    npass = sum(1 for r in rows if r["pass"])
    nlocal = sum(1 for r in rows if r["class"] == "local" and r["pass"])
    ncloud = sum(1 for r in rows if r["class"] == "cloud")
    print(f"\n== 矩阵小结: {npass}/{len(rows)} 可用 · 本地绿 {nlocal} · 云依赖 {ncloud} 项（自用不上云红线，状态如实呈现）==")
    if args.json_out:
        print(json.dumps({"base": base, "generated_at": time.strftime("%Y-%m-%d %H:%M:%S"), "rows": rows}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
