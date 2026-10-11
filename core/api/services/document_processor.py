# file: document_processor.py
# description: 文档处理服务
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-04-08
# updated: 2026-04-08
# status: active
# tags: [service],[document-processor],[rag]

import os
import uuid
from typing import List, Tuple

import tiktoken
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import Document, DocumentChunk, KnowledgeBase
from app.services.embedding import embedding_service
from app.utils.logger import get_logger

logger = get_logger(__name__)


class DocumentProcessor:
    """文档处理服务"""

    def __init__(self):
        self.encoding = tiktoken.get_encoding("cl100k_base")

    def count_tokens(self, text: str) -> int:
        """计算文本的 token 数量"""
        return len(self.encoding.encode(text))

    def chunk_text(
        self,
        text: str,
        chunk_size: int = 500,
        chunk_overlap: int = 50,
    ) -> List[Tuple[int, str]]:
        """
        将文本切分成多个片段

        Args:
            text: 原始文本
            chunk_size: 每个片段的最大 token 数
            chunk_overlap: 片段之间的重叠 token 数

        Returns:
            [(chunk_index, chunk_text), ...]
        """
        tokens = self.encoding.encode(text)
        chunks = []

        # P0 修复（2026-10-11 深度审计活捉）：原实现「start = end - overlap」后仅
        # 以 start >= len(tokens) 判停——end 触顶后 start 恒为 len-overlap < len，
        # 永不满足退出条件 → 任何超 chunk_size 的文档死循环，上传处理永卡
        # processing（chunk_text 0% 覆盖盲区，实证：2400 token 文本 3s 不返回）。
        # 现改为 end 触顶即正常退出；overlap ≥ chunk_size 显式拒绝（会倒退死循环）。
        if chunk_overlap >= chunk_size:
            raise ValueError(f"chunk_overlap({chunk_overlap}) 必须小于 chunk_size({chunk_size})")

        start = 0
        chunk_index = 0

        while start < len(tokens):
            end = min(start + chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            chunks.append((chunk_index, chunk_text))

            chunk_index += 1
            if end >= len(tokens):
                break
            start = end - chunk_overlap

        return chunks

    async def parse_file(self, file_path: str, file_type: str) -> str:
        """
        解析文件内容

        Args:
            file_path: 文件路径
            file_type: 文件类型

        Returns:
            文本内容
        """
        if file_type in [".txt", ".md", ".py", ".js", ".java", ".go", ".rs"]:
            with open(file_path, "r", encoding="utf-8") as f:
                return f.read()

        elif file_type == ".pdf":
            try:
                import fitz

                doc = fitz.open(file_path)
                text = ""
                for page in doc:
                    text += page.get_text()
                doc.close()
                return text
            except ImportError:
                logger.warning("PyMuPDF 未安装，无法解析 PDF")
                raise Exception("PDF 解析需要安装 PyMuPDF: pip install PyMuPDF")

        elif file_type in [".docx", ".doc"]:
            try:
                from docx import Document as DocxDocument

                doc = DocxDocument(file_path)
                text = "\n".join([para.text for para in doc.paragraphs])
                return text
            except ImportError:
                logger.warning("python-docx 未安装，无法解析 Word 文档")
                raise Exception("Word 解析需要安装 python-docx: pip install python-docx")

        else:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()

    async def process_document(
        self,
        document_id: str,
        db: AsyncSession,
    ):
        """
        处理文档：解析、切片、向量化

        Args:
            document_id: 文档ID
            db: 数据库会话
        """
        try:
            doc_query = select(Document).where(Document.id == document_id)
            doc_result = await db.execute(doc_query)
            doc = doc_result.scalar_one_or_none()

            if not doc:
                logger.error(f"文档不存在: {document_id}")
                return

            doc.status = "processing"
            await db.commit()

            if not doc.file_path or not os.path.exists(doc.file_path):
                raise Exception(f"文件不存在: {doc.file_path}")

            text = await self.parse_file(doc.file_path, doc.file_type or ".txt")
            logger.info(f"文档解析完成: {doc.title}, 文本长度: {len(text)}")

            chunks = self.chunk_text(text)
            logger.info(f"文档切片完成: {len(chunks)} 个片段")

            kb_query = select(KnowledgeBase).where(KnowledgeBase.id == doc.knowledge_base_id)
            kb_result = await db.execute(kb_query)
            kb = kb_result.scalar_one_or_none()

            if not kb:
                raise Exception(f"知识库不存在: {doc.knowledge_base_id}")

            total_tokens = 0
            for chunk_index, chunk_text in chunks:
                token_count = self.count_tokens(chunk_text)
                total_tokens += token_count

                embedding = await embedding_service.get_embedding_zhipu(chunk_text)

                chunk = DocumentChunk(
                    id=str(uuid.uuid4()),
                    document_id=doc.id,
                    knowledge_base_id=doc.knowledge_base_id,
                    chunk_index=chunk_index,
                    content=chunk_text,
                    embedding=embedding,
                    token_count=token_count,
                )
                db.add(chunk)

            doc.chunk_count = len(chunks)
            doc.total_tokens = total_tokens
            doc.status = "completed"

            kb.total_tokens += total_tokens
            kb.document_count += 1

            await db.commit()
            logger.info(f"文档处理完成: {doc.title}")

        except Exception as e:
            logger.error(f"文档处理失败: {e}")
            if doc:
                doc.status = "failed"
                doc.error_message = str(e)
                await db.commit()


document_processor = DocumentProcessor()


async def process_document_task(document_id: str, db: AsyncSession):
    """后台任务：处理文档"""
    await document_processor.process_document(document_id, db)
