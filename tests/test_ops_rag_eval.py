#!/usr/bin/env python3
"""
@file test_ops_rag_eval.py
@description golden set 固化件与评测脚本测试——schema/匹配规则/请求体（零网络）
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-09-28
@tags [test,eval,golden-set,rag]
"""

import importlib.util
import json
from pathlib import Path

_SCRIPTS = Path(__file__).parent.parent / "core" / "scripts"

_spec = importlib.util.spec_from_file_location(
    "ops_rag_eval", _SCRIPTS / "ops_rag_eval.py"
)
assert _spec is not None and _spec.loader is not None
eval_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(eval_mod)

_FIXTURE = json.loads((_SCRIPTS / "ops_rag_golden_v3.json").read_text(encoding="utf-8"))


def test_fixture_schema_40_items():
    items = _FIXTURE["items"]
    assert _FIXTURE["version"].startswith("v3")
    assert len(items) == 40
    ids = [i["id"] for i in items]
    assert ids == list(range(1, 41))
    for it in items:
        assert it["query"].strip() and it["source_prefix"] and it["heading_prefix"]


def test_fixture_prefixes_unique_within_source():
    """同 source 下 heading_prefix 不得重复（防一题多解歧义）"""
    seen = {}
    for it in _FIXTURE["items"]:
        key = (it["source_prefix"], it["heading_prefix"])
        assert key not in seen, f"重复期望对: {key}"
        seen[key] = it["id"]


def test_is_hit_prefix_semantics():
    item = {"source_prefix": "DGX-Spark双机推理部署指南.md", "heading_prefix": "18.2"}
    assert eval_mod.is_hit(
        {
            "source": "DGX-Spark双机推理部署指南.md",
            "heading": "18.2 上线前必办（阻断项，按序）",
        },
        item,
    )
    assert not eval_mod.is_hit(
        {"source": "API全链路闭环文档.md", "heading": "5.2 缓存策略"},
        {"source_prefix": "DGX-Spark双机推理部署指南.md", "heading_prefix": "5.2"},
    ), "heading 相同但 source 不同不得命中"
    assert not eval_mod.is_hit(
        {"source": "DGX-Spark双机推理部署指南.md", "heading": "19.3-ter 重启排障"},
        item,
    ), "heading 无包含关系不得命中"


def test_is_hit_emoji_and_decorated_prefix():
    """v4.1：emoji/装饰性标题前缀不算语义差异（8 题伪失归因的护栏）"""
    item = {"source_prefix": "X.md", "heading_prefix": "CLI 工具情感启动画面"}
    assert eval_mod.is_hit(
        {"source": "X.md", "heading": "🖥️ 九、CLI 工具情感启动画面"}, item
    ), "emoji + 编号前缀应命中"
    assert eval_mod.is_hit(
        {"source": "X.md", "heading": "YYC³ 公开仓密钥安审报告（P0 事件）"},
        {"source_prefix": "X.md", "heading_prefix": "公开仓密钥安审报告"},
    ), "「YYC³ 」式标题前缀应命中"
    assert eval_mod.is_hit(
        {"source": "X.md", "heading": "使用 nvidia-smi 查看 GPU 利用率"},
        {"source_prefix": "X.md", "heading_prefix": "nvidia-smi 查看 GPU"},
    ), "「使用 」式前缀应命中"


def test_configs_matrix_covers_four():
    names = [c["name"] for c in eval_mod.CONFIGS]
    assert names == ["vec", "hybrid", "rerank", "hybrid+rerank"]
    flags = {(c["hybrid"], c["rerank"]) for c in eval_mod.CONFIGS}
    assert flags == {(False, False), (True, False), (False, True), (True, True)}
