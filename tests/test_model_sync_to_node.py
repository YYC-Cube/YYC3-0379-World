#!/usr/bin/env python3
"""
@file test_model_sync_to_node.py
@description NAS→节点增量同步脚本测试——增量计划/rsync 命令构造/排除规则
@tags [test,model-asset,sync,fast]

纯 plan/build 层测试（不执行 rsync 子进程，零外部依赖）。
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "scripts"))

from model_sync_to_node import build_rsync_command, plan_sync  # noqa: E402


def _tree(root, files):
    root.mkdir(parents=True, exist_ok=True)
    for name, size in files.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)


class TestPlanSync:
    def test_full_copy_when_dst_empty(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        _tree(src, {"a.safetensors": 100, "b.json": 10})
        plan = plan_sync(src, dst)
        assert plan["total_source_files"] == 2
        assert plan["to_copy"] == ["a.safetensors", "b.json"]
        assert plan["already_synced"] == 0

    def test_incremental_skips_synced(self, tmp_path):
        src, dst = tmp_path / "src", tmp_path / "dst"
        _tree(src, {"a.safetensors": 100, "b.json": 10})
        _tree(dst, {"a.safetensors": 100})
        plan = plan_sync(src, dst)
        assert plan["to_copy"] == ["b.json"]
        assert plan["already_synced"] == 1

    def test_partial_resume_detected(self, tmp_path):
        """目标侧更小的同名文件视为中断残片，列入续传。"""
        src, dst = tmp_path / "src", tmp_path / "dst"
        _tree(src, {"a.safetensors": 100})
        _tree(dst, {"a.safetensors": 40})
        plan = plan_sync(src, dst)
        assert plan["partial_resume"] == ["a.safetensors"]
        assert plan["to_copy"] == []

    def test_dst_missing_dir_treated_empty(self, tmp_path):
        plan = plan_sync(tmp_path / "src", tmp_path / "nope")
        assert plan["total_source_files"] == 0


class TestRsyncCommand:
    def test_command_shape_and_trailing_slashes(self):
        cmd = build_rsync_command("/nas/model/", "/ssd/model/", None, dry_run=False)
        assert cmd[0] == "rsync"
        assert "-a" in cmd and "--partial" in cmd
        assert cmd[-2] == "/nas/model/" and cmd[-1] == "/ssd/model/"

    def test_dry_run_flag(self):
        cmd = build_rsync_command("/a", "/b", None, dry_run=True)
        assert "--dry-run" in cmd

    def test_ssh_transport_flag(self):
        cmd = build_rsync_command("/a", "/b", "yyc3-45", dry_run=False)
        assert "-e" in cmd and "ssh yyc3-45" in cmd

    def test_excludes_report_and_junk(self):
        cmd = build_rsync_command("/a", "/b", None, dry_run=False)
        excludes = [cmd[i + 1] for i, f in enumerate(cmd) if f == "--exclude"]
        assert "model_checksum.report" in excludes
        assert ".DS_Store" in excludes
