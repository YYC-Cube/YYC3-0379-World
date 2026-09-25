# file: test_admin_key_separation.py
# description: ADMIN_API_KEYS 与 API_KEYS 分离语义单元测试（P2-6，快速层纯逻辑）
# author: YanYuCloudCube Team <admin@0379.email>
# created: 2026-09-23
# status: active
# tags: [test],[rbac],[admin-keys]

"""
@file: test_admin_key_separation.py
@description: 管理面/推理面密钥分离的语义契约（auth_config.ADMIN_API_KEYS 属性）：
  ① 未配置 admin_api_keys → 回退 VALID_API_KEYS（单机部署兼容）
  ② 配置后 → 与 API_KEYS 严格分离（业务 Key 不得入管理面）
  ③ 解析容错：逗号分隔、空白条目剔除
  ④ 环境面契约：.env 模板含 ADMIN_API_KEYS 占位（防模板漂移）
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))

from app.middleware.auth import AuthConfig  # noqa: E402

_BIZ_KEYS = "sk-biz-001, sk-biz-002,,"
_ADMIN_KEYS = "sk-admin-001"


def test_admin_keys_fallback_when_unset(monkeypatch):
    """① 未配置 → 回退 VALID_API_KEYS（单机兼容：旧部署只设 API_KEYS 不破坏 admin 入口）"""
    from app.config import settings

    monkeypatch.setattr(settings, "api_keys", _BIZ_KEYS)
    monkeypatch.setattr(settings, "admin_api_keys", "")
    cfg = AuthConfig()
    assert cfg.ADMIN_API_KEYS == {"sk-biz-001", "sk-biz-002"}


def test_admin_keys_separated_when_set(monkeypatch):
    """② 配置后 → 严格分离：管理面仅含 admin Key，业务 Key 不入管理面"""
    from app.config import settings

    monkeypatch.setattr(settings, "api_keys", _BIZ_KEYS)
    monkeypatch.setattr(settings, "admin_api_keys", _ADMIN_KEYS)
    cfg = AuthConfig()
    assert cfg.ADMIN_API_KEYS == {"sk-admin-001"}
    assert cfg.ADMIN_API_KEYS.isdisjoint(
        cfg.VALID_API_KEYS
    ), "管理面与推理面密钥必须互斥（最小权限）"


def test_admin_keys_parse_tolerates_whitespace(monkeypatch):
    """③ 逗号分隔解析：空白/空段剔除"""
    from app.config import settings

    monkeypatch.setattr(settings, "api_keys", "k1")
    monkeypatch.setattr(settings, "admin_api_keys", " a , ,b ,")
    cfg = AuthConfig()
    assert cfg.ADMIN_API_KEYS == {"a", "b"}


def test_env_example_declares_admin_keys():
    """④ 环境面契约：.env.example 必须声明 ADMIN_API_KEYS（防模板与代码漂移）"""
    root = Path(__file__).resolve().parents[1]
    content = (root / ".env.example").read_text(encoding="utf-8")
    assert "ADMIN_API_KEYS=" in content, ".env.example 缺 ADMIN_API_KEYS 声明（v8 补齐项回归锚）"


@pytest.mark.parametrize("missing", [None, ""])
def test_admin_keys_fallback_on_falsy(missing, monkeypatch):
    """边界：admin_api_keys 为 None/空串 → 均回退（getattr 默认 + or 兜底双层）"""
    from app.config import settings

    monkeypatch.setattr(settings, "api_keys", "k1")
    monkeypatch.setattr(settings, "admin_api_keys", missing)
    assert AuthConfig().ADMIN_API_KEYS == {"k1"}
