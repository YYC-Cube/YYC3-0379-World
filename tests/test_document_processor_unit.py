#!/usr/bin/env python3
"""
@file test_document_processor_unit.py
@description 文档处理服务纯单元测试——0% 覆盖盲区攻坚 + P0 死循环回归
@author: YanYuCloudCube Team
@tags [test,document-processor,rag,unit]

背景：services/document_processor.py（101 语句）此前 0% 覆盖。审计实证
chunk_text 尾段死循环（任何 >chunk_size 文档无限挂起，上传永卡 processing），
已修复（end 触顶退出 + overlap≥size 显式拒绝），本文件锁定修复后行为。
process_document 用 FakeSession 桩替 DB（不建表，走通流程分支）。
"""

import asyncio
import os
import sys
import types

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "core", "api"))

from app.services import document_processor as dp_mod  # noqa: E402
from app.services.document_processor import DocumentProcessor  # noqa: E402

pytestmark = pytest.mark.unit


def _run(coro):
    return asyncio.run(coro)


# ── chunk_text：P0 死循环回归 ─────────────────────────────


def test_chunk_text_short_text_single_chunk():
    dp = DocumentProcessor()
    chunks = dp.chunk_text("你好，世界。", chunk_size=500, chunk_overlap=50)
    assert len(chunks) == 1
    assert chunks[0][0] == 0
    assert chunks[0][1] == "你好，世界。"


def test_chunk_text_long_text_terminates_with_overlap():
    """P0 回归：2400 token 文本（远超 chunk_size）必须在有限步内完成"""
    dp = DocumentProcessor()
    text = "你好世界。" * 400  # ~2400 tokens
    chunks = dp.chunk_text(text, chunk_size=500, chunk_overlap=50)
    assert len(chunks) >= 4  # 有重叠推进，至少 4 段
    # 索引连续
    assert [i for i, _ in chunks] == list(range(len(chunks)))
    # 段间有重叠（前段尾部在后段头部重现）
    assert chunks[1][1][:20] in chunks[0][1][-60:]
    # 末段以原文收尾
    assert chunks[-1][1].endswith("你好世界。")


def test_chunk_text_empty_text():
    dp = DocumentProcessor()
    assert dp.chunk_text("") == []


def test_chunk_text_overlap_ge_size_raises():
    """防御：overlap ≥ chunk_size 会倒退死循环 → 显式拒绝"""
    dp = DocumentProcessor()
    with pytest.raises(ValueError):
        dp.chunk_text("abc", chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError):
        dp.chunk_text("abc", chunk_size=100, chunk_overlap=200)


def test_count_tokens_monotonic():
    dp = DocumentProcessor()
    assert dp.count_tokens("") == 0
    assert dp.count_tokens("hello") > 0
    assert dp.count_tokens("hello world") > dp.count_tokens("hello")


# ── parse_file：四类分支 ──────────────────────────────────


def test_parse_file_txt(tmp_path):
    dp = DocumentProcessor()
    p = tmp_path / "doc.txt"
    p.write_text("纯文本内容", encoding="utf-8")
    assert _run(dp.parse_file(str(p), ".txt")) == "纯文本内容"


def test_parse_file_unknown_extension_ignores_errors(tmp_path):
    dp = DocumentProcessor()
    p = tmp_path / "blob.bin"
    p.write_bytes("文本部分".encode("utf-8") + "二进制噪声".encode("utf-8")[:2] + b"\xff\xfe")
    out = _run(dp.parse_file(str(p), ".bin"))
    assert "文本部分" in out  # errors=ignore 路径


def test_parse_file_pdf(tmp_path):
    fitz = pytest.importorskip("fitz")
    dp = DocumentProcessor()
    p = tmp_path / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "PDF Content 2026")  # base-14 字体不含 CJK，用 ASCII
    doc.save(str(p))
    doc.close()
    assert "PDF Content 2026" in _run(dp.parse_file(str(p), ".pdf"))


def test_parse_file_pdf_missing_dependency(monkeypatch, tmp_path):
    dp = DocumentProcessor()
    p = tmp_path / "doc.pdf"
    p.write_bytes(b"%PDF-1.4 fake")
    monkeypatch.setitem(sys.modules, "fitz", None)  # 令 import fitz 抛 ImportError
    with pytest.raises(Exception, match="PyMuPDF"):
        _run(dp.parse_file(str(p), ".pdf"))


def test_parse_file_docx(tmp_path):
    docx = pytest.importorskip("docx")
    dp = DocumentProcessor()
    p = tmp_path / "doc.docx"
    d = docx.Document()
    d.add_paragraph("Word 第一段")
    d.add_paragraph("Word 第二段")
    d.save(str(p))
    out = _run(dp.parse_file(str(p), ".docx"))
    assert "Word 第一段" in out and "Word 第二段" in out


def test_parse_file_docx_missing_dependency(monkeypatch, tmp_path):
    dp = DocumentProcessor()
    p = tmp_path / "doc.docx"
    p.write_bytes(b"PK fake")
    monkeypatch.setitem(sys.modules, "docx", None)
    with pytest.raises(Exception, match="python-docx"):
        _run(dp.parse_file(str(p), ".docx"))


# ── process_document：FakeSession 流程分支 ────────────────


class _Result:
    def __init__(self, obj):
        self._obj = obj

    def scalar_one_or_none(self):
        return self._obj


class FakeSession:
    """按序应答两次 execute（文档查询 → 知识库查询）的会话桩"""

    def __init__(self, doc=None, kb=None):
        self._answers = [doc, kb]
        self.commits = 0
        self.added = []

    async def execute(self, _query):
        return _Result(self._answers.pop(0) if self._answers else None)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1


def _make_doc(tmp_path, file_type=".txt", content="知识库文档内容。"):
    p = tmp_path / f"doc{file_type}"
    p.write_text(content, encoding="utf-8")
    return types.SimpleNamespace(
        id="doc-1",
        title="测试文档",
        status="pending",
        file_path=str(p),
        file_type=file_type,
        knowledge_base_id="kb-1",
        chunk_count=0,
        total_tokens=0,
        error_message=None,
    )


def _make_kb():
    return types.SimpleNamespace(id="kb-1", total_tokens=0, document_count=0)


def _stub_embedding(monkeypatch):
    async def _fake(text):
        return [0.1] * 8

    monkeypatch.setattr(dp_mod.embedding_service, "get_embedding_zhipu", _fake)


def test_process_document_not_found(monkeypatch):
    dp = DocumentProcessor()
    session = FakeSession(doc=None)
    _run(dp.process_document("ghost", session))  # 静默返回
    assert session.commits == 0


def test_process_document_missing_file_marks_failed(monkeypatch, tmp_path):
    dp = DocumentProcessor()
    doc = _make_doc(tmp_path)
    doc.file_path = str(tmp_path / "不存在.txt")
    session = FakeSession(doc=doc, kb=_make_kb())
    _stub_embedding(monkeypatch)
    _run(dp.process_document("doc-1", session))
    assert doc.status == "failed"
    assert "文件不存在" in doc.error_message


def test_process_document_happy_path(monkeypatch, tmp_path):
    dp = DocumentProcessor()
    doc = _make_doc(tmp_path, content="切片测试。" * 300)  # 多片段
    kb = _make_kb()
    session = FakeSession(doc=doc, kb=kb)
    _stub_embedding(monkeypatch)

    _run(dp.process_document("doc-1", session))

    assert doc.status == "completed"
    assert doc.chunk_count == len(session.added) > 0
    assert doc.total_tokens > 0
    assert kb.document_count == 1
    assert kb.total_tokens == doc.total_tokens
    # 片段字段完整
    first = session.added[0]
    assert first.document_id == "doc-1"
    assert first.knowledge_base_id == "kb-1"
    assert first.chunk_index == 0
    assert first.embedding == [0.1] * 8
    assert first.token_count > 0


def test_process_document_parse_failure_marks_failed(monkeypatch, tmp_path):
    dp = DocumentProcessor()
    doc = _make_doc(tmp_path, file_type=".pdf")  # 伪造 PDF 触发解析异常
    session = FakeSession(doc=doc, kb=_make_kb())
    monkeypatch.setitem(sys.modules, "fitz", None)
    _run(dp.process_document("doc-1", session))
    assert doc.status == "failed"
    assert "PyMuPDF" in doc.error_message


def test_process_document_task_wrapper(monkeypatch, tmp_path):
    """模块级后台任务入口：透传到实例方法"""
    called = {}

    async def _fake(document_id, db):
        called["id"] = document_id

    monkeypatch.setattr(dp_mod.document_processor, "process_document", _fake)
    _run(dp_mod.process_document_task("doc-x", None))
    assert called["id"] == "doc-x"
