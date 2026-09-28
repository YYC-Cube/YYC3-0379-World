#!/usr/bin/env python3
"""
@file test_model_smoke_test.py
@description 上线冒烟脚本测试——报告器/入口参数校验（HTTP 面由生产冒烟实跑覆盖）
@tags [test,smoke,fast]
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "scripts"))

import pytest  # noqa: E402

from model_smoke_test import SmokeReport, main  # noqa: E402


class TestSmokeReport:
    def test_all_pass_exit_zero(self):
        report = SmokeReport()
        report.record("a", True, "ok")
        report.record("b", True, "ok")
        assert report.summary() == 0

    def test_fail_exit_one(self, capsys):
        report = SmokeReport()
        report.record("a", True)
        report.record("b", False, "boom")
        assert report.summary() == 1
        out = capsys.readouterr().out
        assert "1/2" in out

    def test_skipped_counts_passed_not_failed(self, capsys):
        report = SmokeReport()
        report.record("a", True, "", skipped=True)  # 跳过不计失败
        report.record("b", True)
        assert report.summary() == 0
        assert "2/2" in capsys.readouterr().out

    def test_marks_rendered(self, capsys):
        report = SmokeReport()
        report.record("ok_case", True, "fine")
        report.record("bad_case", False, "err")
        report.record("skip_case", True, "n/a", skipped=True)
        out = capsys.readouterr().out
        assert "✅" in out and "❌" in out and "⏭️" in out


class TestCli:
    def test_missing_api_key_env_exit_2(self, monkeypatch):
        monkeypatch.delenv("API_KEYS", raising=False)
        monkeypatch.delenv("ADMIN_API_KEYS", raising=False)
        assert main(["--base", "http://x", "--model", "m"]) == 2

    def test_bad_path_exit_2_on_unknown_arg(self):
        with pytest.raises(SystemExit):
            main(["--nope"])
