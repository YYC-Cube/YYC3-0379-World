# file: test_auth_bearer_compat.py
# description: Bearer sk-/vk- 前缀按 API Key 链认证的兼容契约（生产 403 复盘 2026-09-27）
# author: YanYuCloudCube Team <admin@0379.email>
# created: 2026-09-27
# status: active
# tags: [test],[auth],[openai-compat]

"""
@file: test_auth_bearer_compat.py
@description: 认证中间件 Bearer 兼容语义（AuthMiddleware._authenticate 单元层）：
  ① Bearer sk- 静态键 → api_key 身份放行（不再被当 JWT 解析 403）
  ② Bearer sk- 管理键 → admin 身份（/v1/admin/** 可入）
  ③ Bearer vk- 键 → vk 认证链优先（打桩 vk_manager.authenticate）
  ④ 三段式 JWT 走原 JWT 链（无效 token 仍 403 语义：has_creds=True, result=None）
  ⑤ X-API-Key 头回归不受影响
"""

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from app.middleware.auth import AuthMiddleware  # noqa: E402

_SK = "sk-biz-bearer-001"
_ADMIN = "sk-admin-bearer-001"
_FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJ4IjoxfQ.bad-sig"  # 三段式，无业务前缀


def _mk_request(headers: dict):
    from starlette.requests import Request

    scope = {
        "type": "http",
        "method": "GET",
        "path": "/v1/models",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "query_string": b"",
    }
    return Request(scope)


def _auth(headers: dict):
    # ASGI 兼容 dummy：_authenticate 仅读 request 头，不触碰下游 app
    async def _noop_asgi(scope, receive, send):  # noqa: ANN001
        return None

    return asyncio.run(AuthMiddleware(app=_noop_asgi)._authenticate(_mk_request(headers)))


@pytest.fixture(autouse=True)
def _keys(monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "api_keys", _SK)
    monkeypatch.setattr(settings, "admin_api_keys", _ADMIN)


def test_bearer_sk_static_key_routes_to_api_key_chain():
    """① Bearer sk- 静态键 → api_key 身份（生产 403 场景的修复锚）"""
    has_creds, result = _auth({"Authorization": f"Bearer {_SK}"})
    assert has_creds is True
    assert result == {
        "type": "api_key",
        "key_hash": __import__("hashlib").sha256(_SK.encode()).hexdigest(),
        "admin": False,
    }


def test_bearer_admin_key_keeps_admin_identity():
    """② Bearer 管理键 → admin=True（RBAC 语义随链路保持）"""
    _, result = _auth({"Authorization": f"Bearer {_ADMIN}"})
    assert result is not None and result["admin"] is True


def test_bearer_vk_prefix_hits_vk_chain_first(monkeypatch):
    """③ Bearer vk- 键 → vk 认证链优先命中（虚拟密钥身份）"""

    from app.services import virtual_key_manager as vkm

    async def _fake_authenticate(key: str):
        assert key.startswith("vk-")
        return {"id": "vk-uuid-1", "name": "t"}

    monkeypatch.setattr(vkm.vk_manager, "authenticate", _fake_authenticate)
    _, result = _auth({"Authorization": "Bearer vk-abc123"})
    assert result is not None and result["type"] == "virtual_key"


def test_plain_jwt_still_goes_jwt_chain():
    """④ 三段式 JWT 不受前缀分流影响：无效签名 → has_creds=True + result=None（403 语义）"""
    has_creds, result = _auth({"Authorization": f"Bearer {_FAKE_JWT}"})
    assert has_creds is True
    assert result is None


def test_x_api_key_header_regression():
    """⑤ X-API-Key 头回归：静态键照常放行（原生通道不受 Bearer 增强影响）"""
    has_creds, result = _auth({"X-API-Key": _SK})
    assert has_creds is True
    assert result is not None and result["type"] == "api_key"
