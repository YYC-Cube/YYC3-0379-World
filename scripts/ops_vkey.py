# file: ops_vkey.py
# description: 统一 API 虚拟密钥（vk）生命周期运维 CLI——签发/列表/用量/停启用/吊销
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-11-02
# status: active
# tags: [ops],[virtual-key],[cli],[api]
# stdlib-only（零依赖，Mac/NAS 任意 python3 可跑，对齐 model_register_agent.py 纪律）

"""
@file: scripts/ops_vkey.py
@description: 经网关管理面 API（/v1/admin/virtual-keys*）完成 vk 全生命周期。
@usage:
  export YYC3_ADMIN_KEY=<管理密钥>            # ADMIN_API_KEYS 或（未配时）API_KEYS 首把
  python3 scripts/ops_vkey.py issue --name ts-family --owner TS仓 --budget 5 --tpm 60000
  python3 scripts/ops_vkey.py list
  python3 scripts/ops_vkey.py usage <key_id>
  python3 scripts/ops_vkey.py patch <key_id> --status disabled     # 停用（吊销用 revoke）
  python3 scripts/ops_vkey.py patch <key_id> --whitelist nemotron-3.5-super-vl,qwen3-coder-30b
  python3 scripts/ops_vkey.py revoke <key_id>
@security: 明文 Key 仅签发响应出现一次；本脚本不落盘、不回显历史明文。
"""

import argparse
import ipaddress
import json
import os
import socket
import sys
import urllib.error
import urllib.request
from urllib.parse import urlparse

DEFAULT_BASE = os.environ.get("YYC3_GATEWAY_BASE", "http://100.65.172.88:8000")
_ALLOWED_SCHEMES = ("http", "https")
# 运维 CLI 语义：目标即内网网关（LAN/Tailscale/localhost 是合法目标）——
# 以显式常量放行私网/环回，但保留解析级边界校验（元数据/链路本地/保留段硬禁止）
ALLOW_PRIVATE_TARGETS = True
_HARD_BLOCK_NETS = [
    ipaddress.ip_network(n)
    for n in ("169.254.0.0/16", "0.0.0.0/8", "224.0.0.0/4", "240.0.0.0/4")
]


def _validate_base(base: str) -> str:
    """URL 边界校验（SSRF 加固 2026-11-02）：仅 http(s)、禁内嵌凭据、DNS 解析后
    逐 IP 校验硬禁段（云元数据/链路本地 169.254、保留段）；私网/环回经
    ALLOW_PRIVATE_TARGETS 显式放行（本工具专用于内网网关运维）。"""
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


def _call(base, admin_key, method, path, body=None):
    req = urllib.request.Request(
        _validate_base(base) + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"X-API-Key": admin_key, "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"raw": str(e)}
    except urllib.error.URLError as e:
        sys.exit(f"❌ 网关不可达 {base}: {e.reason}")


def _admin_key(args):
    key = args.admin_key or os.environ.get("YYC3_ADMIN_KEY", "")
    if not key:
        sys.exit("❌ 缺管理密钥：--admin-key 或 export YYC3_ADMIN_KEY=<...>")
    return key


def cmd_issue(a):
    body = {
        "name": a.name,
        "owner": a.owner,
        "monthly_budget_usd": a.budget,
        "rate_limit_tpm": a.tpm,
        "model_whitelist": [s.strip() for s in (a.whitelist or "").split(",") if s.strip()],
    }
    if a.expires:
        body["expires_at"] = a.expires
    code, d = _call(a.base, _admin_key(a), "POST", "/v1/admin/virtual-keys", body)
    if code in (200, 201):
        print("✅ 签发成功")
        print(f"   明文 Key（仅此一次，立即保存）: {d.get('key')}")
        print(f"   key_id: {d.get('id')}")
        print(f"   名称/属主: {d.get('name')} / {d.get('owner')}")
        print(f"   预算 ${d.get('monthly_budget_usd', 0)} · TPM {d.get('rate_limit_tpm', 0)} · 白名单 {d.get('model_whitelist') or '全模型'}")
    else:
        sys.exit(f"❌ 签发失败 HTTP {code}: {json.dumps(d, ensure_ascii=False)[:300]}")


def cmd_list(a):
    code, d = _call(a.base, _admin_key(a), "GET", "/v1/admin/virtual-keys")
    keys = d.get("keys", d if isinstance(d, list) else [])
    print(f"共 {len(keys)} 把虚拟密钥：")
    for k in keys:
        spent = k.get("spent_usd", 0)
        budget = k.get("monthly_budget_usd", 0)
        budget_s = f"${spent}/{budget}" if budget else f"${spent}/∞"
        print(f"  {str(k.get('id'))[:8]}  {k.get('status', '?'):8}  {k.get('name')}  owner={k.get('owner')}  用量={budget_s}  TPM={k.get('rate_limit_tpm', 0)}  白名单={k.get('model_whitelist') or '全模型'}")


def cmd_usage(a):
    code, d = _call(a.base, _admin_key(a), "GET", f"/v1/admin/virtual-keys/{a.key_id}/usage")
    print(json.dumps(d, ensure_ascii=False, indent=1) if code == 200 else f"❌ HTTP {code}: {d}")


def cmd_patch(a):
    body = {}
    if a.status:
        body["status"] = a.status
    if a.budget is not None:
        body["monthly_budget_usd"] = a.budget
    if a.tpm is not None:
        body["rate_limit_tpm"] = a.tpm
    if a.whitelist is not None:
        body["model_whitelist"] = [s.strip() for s in a.whitelist.split(",") if s.strip()]
    if not body:
        sys.exit("❌ 无可更新字段（--status/--budget/--tpm/--whitelist 至少一个）")
    code, d = _call(a.base, _admin_key(a), "PATCH", f"/v1/admin/virtual-keys/{a.key_id}", body)
    if code == 200:
        print(f"✅ 已更新 {a.key_id[:8]}: {json.dumps(body, ensure_ascii=False)}")
    else:
        sys.exit(f"❌ HTTP {code}: {json.dumps(d, ensure_ascii=False)[:300]}")


def cmd_revoke(a):
    code, d = _call(a.base, _admin_key(a), "DELETE", f"/v1/admin/virtual-keys/{a.key_id}")
    if code in (200, 204):
        print(f"✅ 已吊销 {a.key_id[:8]}（hash 失效，明文即弃）")
    else:
        sys.exit(f"❌ HTTP {code}: {json.dumps(d, ensure_ascii=False)[:300]}")


def main():
    ap = argparse.ArgumentParser(description="YYC³ 统一 API 虚拟密钥运维 CLI")
    ap.add_argument("--base", default=DEFAULT_BASE, help=f"网关基址（默认 {DEFAULT_BASE}）")
    ap.add_argument("--admin-key", default="", help="管理密钥（缺省读 YYC3_ADMIN_KEY）")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("issue", help="签发虚拟密钥")
    p.add_argument("--name", required=True)
    p.add_argument("--owner", required=True)
    p.add_argument("--budget", type=float, default=0, help="月预算 USD（0=不限）")
    p.add_argument("--tpm", type=int, default=0, help="每分钟 token 上限（0=不限）")
    p.add_argument("--whitelist", default="", help="逗号分隔模型白名单（空=全模型）")
    p.add_argument("--expires", default="", help="ISO 到期时间（可选）")
    p.set_defaults(fn=cmd_issue)

    p = sub.add_parser("list", help="列出虚拟密钥")
    p.set_defaults(fn=cmd_list)
    p = sub.add_parser("usage", help="查询用量")
    p.add_argument("key_id")
    p.set_defaults(fn=cmd_usage)
    p = sub.add_parser("patch", help="更新预算/TPM/白名单/状态")
    p.add_argument("key_id")
    p.add_argument("--status", choices=["active", "disabled"])
    p.add_argument("--budget", type=float)
    p.add_argument("--tpm", type=int)
    p.add_argument("--whitelist")
    p.set_defaults(fn=cmd_patch)
    p = sub.add_parser("revoke", help="吊销（不可逆）")
    p.add_argument("key_id")
    p.set_defaults(fn=cmd_revoke)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
