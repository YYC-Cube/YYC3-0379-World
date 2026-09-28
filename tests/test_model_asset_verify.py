#!/usr/bin/env python3
"""
@file test_model_asset_verify.py
@description 模型资产完整性校验脚本测试——分片对账/头部magic/配置存在性/报告落盘/CLI退出码
@tags [test,model-asset,verify,fast]

tmp_path 构造 HF 模型目录全形态（完整/缺分片/坏magic/缺config/单文件），
纯文件系统操作零外部依赖（快层）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "scripts"))

import pytest  # noqa: E402
from model_asset_verify import (  # noqa: E402
    SAFETENSORS_MAGIC,
    main,
    verify_model,
    write_report,
)


def _make_model(
    root, shards=2, missing=(), corrupt=(), drop_config=(), extra_shard=False, name="Qwen3-Test"
):
    """构造 HF 模型目录：index.json 引用 shards 个分片；missing 删文件；corrupt 写坏 magic。"""
    d = root / name
    d.mkdir(parents=True)
    weight_map = {}
    for i in range(1, shards + 1):
        name = f"model-{i:05d}-of-{shards:05d}.safetensors"
        weight_map[f"layer.{i}"] = name
        if name in missing:
            continue
        data = SAFETENSORS_MAGIC + b"\x00" * 64
        if name in corrupt:
            data = b"BADBAD!" + b"\x00" * 64
        (d / name).write_bytes(data)
    if extra_shard:
        (d / "model-loose-00001-of-00002.safetensors").write_bytes(SAFETENSORS_MAGIC + b"\x00" * 16)
    (d / "model.safetensors.index.json").write_text(json.dumps({"weight_map": weight_map}))
    for f in ("config.json", "tokenizer.json", "tokenizer_config.json", "vocab.json", "merges.txt"):
        if f in drop_config:
            continue
        (d / f).write_text("{}")
    return d


class TestShardManifest:
    def test_complete_model_passes(self, tmp_path):
        d = _make_model(tmp_path)
        report = verify_model(d)
        assert report["passed"] is True

    def test_missing_shard_fails(self, tmp_path):
        d = _make_model(tmp_path, missing=("model-00001-of-00002.safetensors",))
        report = verify_model(d)
        shard = next(c for c in report["checks"] if c["check"] == "shard_manifest")
        assert shard["ok"] is False
        assert "model-00001-of-00002.safetensors" in shard["detail"]["missing"]

    def test_extra_unreferenced_shard_is_hint_not_failure(self, tmp_path):
        d = _make_model(tmp_path, extra_shard=True)
        report = verify_model(d)
        assert report["passed"] is True
        shard = next(c for c in report["checks"] if c["check"] == "shard_manifest")
        assert "提示" in shard["message"]

    def test_single_file_model_without_index_passes(self, tmp_path):
        """单文件形态（无 index.json）放行。"""
        d = tmp_path / "single"
        d.mkdir()
        (d / "model.safetensors").write_bytes(SAFETENSORS_MAGIC + b"\x00" * 32)
        for f in ("config.json", "tokenizer.json", "tokenizer_config.json"):
            (d / f).write_text("{}")
        assert verify_model(d)["passed"] is True

    def test_empty_dir_fails(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        report = verify_model(d)
        assert report["passed"] is False


class TestHeadersAndConfig:
    def test_corrupt_magic_fails(self, tmp_path):
        d = _make_model(tmp_path, corrupt=("model-00002-of-00002.safetensors",))
        report = verify_model(d)
        headers = next(c for c in report["checks"] if c["check"] == "safetensors_headers")
        assert headers["ok"] is False

    def test_truncated_shard_fails(self, tmp_path):
        d = _make_model(tmp_path)
        (d / "model-00001-of-00002.safetensors").write_bytes(SAFETENSORS_MAGIC[:2])
        report = verify_model(d)
        headers = next(c for c in report["checks"] if c["check"] == "safetensors_headers")
        assert headers["ok"] is False

    def test_missing_tokenizer_fails(self, tmp_path):
        d = _make_model(tmp_path, drop_config=("tokenizer.json", "tokenizer_config.json"))
        report = verify_model(d)
        cfg = next(c for c in report["checks"] if c["check"] == "config_files")
        assert cfg["ok"] is False


class TestReportAndCli:
    def test_report_written_to_model_dir(self, tmp_path):
        d = _make_model(tmp_path)
        report = verify_model(d)
        out = write_report(d, report)
        assert out.name == "model_checksum.report"
        assert json.loads(out.read_text())["passed"] is True

    def test_cli_exit_codes(self, tmp_path, capsys):
        good = _make_model(tmp_path)
        assert main([str(good), "--no-report", "--json"]) == 0
        bad = _make_model(
            tmp_path,
            missing=("model-00001-of-00002.safetensors",),
            drop_config=("config.json",),
            name="Bad-Model",
        )
        assert main([str(bad), "--no-report", "--json"]) == 1
        assert main([str(tmp_path / "nope")]) == 2

    def test_cli_json_output_has_checks(self, tmp_path, capsys):
        d = _make_model(tmp_path)
        main([str(d), "--no-report", "--json"])
        payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
        assert {c["check"] for c in payload["checks"]} == {
            "shard_manifest",
            "safetensors_headers",
            "config_files",
        }


@pytest.mark.parametrize("sample", [1, 0])
def test_sample_limit_only_checks_first_n(tmp_path, sample):
    """--sample 抽检：坏 magic 在第 2 片时，抽 1 片应通过、全量应失败。"""
    d = _make_model(tmp_path, corrupt=("model-00002-of-00002.safetensors",))
    report = verify_model(d, sample_limit=sample)
    headers = next(c for c in report["checks"] if c["check"] == "safetensors_headers")
    assert headers["ok"] is (sample == 1)
