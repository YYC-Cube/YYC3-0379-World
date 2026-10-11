#!/usr/bin/env python3
"""
@file test_crypto_unit.py
@description 加密工具（CryptoManager）纯单元测试——0% 覆盖盲区攻坚
@author: YanYuCloudCube Team
@tags [test,crypto,unit]

背景：utils/crypto.py（45 语句）此前 0% 覆盖
（docs/0379-world-执行记录/21-深度审核与实况测试报告.md §三 P2-2）。
本文件锁定：显式密钥/环境密钥/缺省生成三条构造路径、加解密往返、
字段级加解密（含空值跳过与坏值容错）。 cryptography 为纯本地计算，无外部依赖。
"""

import os
import sys

import pytest
from cryptography.fernet import Fernet

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

from app.utils.crypto import CryptoManager  # noqa: E402

pytestmark = pytest.mark.unit

_KEY = Fernet.generate_key().decode()


def test_roundtrip_with_explicit_key():
    cm = CryptoManager(encryption_key=_KEY)
    token = cm.encrypt("sk-secret-value")
    assert token != "sk-secret-value"
    assert cm.decrypt(token) == "sk-secret-value"


def test_cross_instance_env_key(monkeypatch):
    """环境密钥路径：两个实例（如重启前后）必须可互解（持久化语义）"""
    monkeypatch.setenv("ENCRYPTION_KEY", _KEY)
    a = CryptoManager()
    b = CryptoManager()
    token = a.encrypt("hello-yyc3")
    assert b.decrypt(token) == "hello-yyc3"


def test_missing_env_key_generates_and_still_works(monkeypatch):
    monkeypatch.delenv("ENCRYPTION_KEY", raising=False)
    cm = CryptoManager()
    assert cm.decrypt(cm.encrypt("x")) == "x"  # 生成的密钥当进程内可用


def test_encrypt_dict_only_target_keys_and_no_mutation():
    cm = CryptoManager(encryption_key=_KEY)
    original = {"api_key": "sk-1", "name": "demo", "empty": "", "note": None}
    out = cm.encrypt_dict(original, ["api_key", "empty", "note"])
    assert out["api_key"] != "sk-1"
    assert cm.decrypt(out["api_key"]) == "sk-1"
    assert out["name"] == "demo"  # 未指定字段不动
    assert out["empty"] == "" and out["note"] is None  # 空值跳过
    assert original["api_key"] == "sk-1"  # 入参不被污染


def test_decrypt_dict_tolerates_bad_values():
    cm = CryptoManager(encryption_key=_KEY)
    good = cm.encrypt("good-value")
    out = cm.decrypt_dict({"k1": good, "k2": "not-a-token"}, ["k1", "k2"])
    assert out["k1"] == "good-value"
    assert out["k2"] == "not-a-token"  # 坏值保留原样并告警，不抛异常


def test_decrypt_invalid_token_raises():
    cm = CryptoManager(encryption_key=_KEY)
    with pytest.raises(Exception):
        cm.decrypt("garbage-token")
