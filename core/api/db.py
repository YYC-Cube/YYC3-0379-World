# file: db.py
# description: 数据库连接和操作模块
# author: YanYuCloudCube Team
# version: v1.0.0
# created: 2026-03-21
# updated: 2026-04-04
# status: active
# tags: [database],[postgresql],[connection]

"""
@file: app/db.py
@description: 数据库模块，提供 PostgreSQL 数据库连接和操作
@author: YanYuCloudCube Team <admin@0379.email>
@version: v1.0.0
@created: 2026-03-13
@updated: 2026-03-13
@status: stable
@license: MIT
@copyright: Copyright (c) 2026 YanYuCloudCube Team
@tags: db,python,postgresql,core,public
"""

import os
from datetime import datetime

from app.config import settings
from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()

DATABASE_URL = f"postgresql+asyncpg://{settings.db_user}:{settings.db_password}@{settings.db_host}:{settings.db_port}/{settings.db_name}"

echo_sql = os.getenv("ENVIRONMENT", "production") != "production"
engine = create_async_engine(DATABASE_URL, echo=echo_sql)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class ModelRegistry(Base):
    __tablename__ = "model_registry"

    id = Column(String, primary_key=True)
    display_name = Column(String, nullable=False)
    backend_type = Column(String, nullable=False)
    backend_name = Column(String, nullable=False)
    enabled = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class UsageLog(Base):
    __tablename__ = "usage_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    model = Column(String, nullable=False)
    backend_type = Column(String, nullable=False)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    user_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class KnowledgeBase(Base):
    """知识库表"""

    __tablename__ = "knowledge_bases"

    id = Column(String, primary_key=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    embedding_model = Column(String(50), default="embedding-3")
    icon = Column(String(50), default="book")
    background = Column(String(50), default="blue")
    status = Column(String(20), default="active")
    document_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    storage_size = Column(BigInteger, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255))
    extra_metadata = Column("metadata", JSONB)

    documents = relationship(
        "Document", back_populates="knowledge_base", cascade="all, delete-orphan"
    )


class Document(Base):
    """文档表"""

    __tablename__ = "documents"

    id = Column(String, primary_key=True)
    knowledge_base_id = Column(
        String, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    title = Column(String(500), nullable=False)
    source_type = Column(String(50), nullable=False)
    source_url = Column(Text)
    file_path = Column(Text)
    file_size = Column(BigInteger)
    file_type = Column(String(50))
    status = Column(String(20), default="pending")
    chunk_count = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)
    error_message = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    extra_metadata = Column("metadata", JSONB)

    knowledge_base = relationship("KnowledgeBase", back_populates="documents")
    chunks = relationship(
        "DocumentChunk", back_populates="document", cascade="all, delete-orphan"
    )


class DocumentChunk(Base):
    """文档切片表"""

    __tablename__ = "document_chunks"

    id = Column(String, primary_key=True)
    document_id = Column(
        String, ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    knowledge_base_id = Column(
        String, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536))
    token_count = Column(Integer, default=0)
    extra_metadata = Column("metadata", JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)

    document = relationship("Document", back_populates="chunks")


class QAPair(Base):
    """问答对表"""

    __tablename__ = "qa_pairs"

    id = Column(String, primary_key=True)
    knowledge_base_id = Column(
        String, ForeignKey("knowledge_bases.id", ondelete="CASCADE"), nullable=False
    )
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    question_embedding = Column(Vector(1536))
    extra_metadata = Column("metadata", JSONB)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SearchHistory(Base):
    """检索历史表"""

    __tablename__ = "search_history"

    id = Column(String, primary_key=True)
    knowledge_base_id = Column(
        String, ForeignKey("knowledge_bases.id", ondelete="CASCADE")
    )
    query = Column(Text, nullable=False)
    query_embedding = Column(Vector(1536))
    result_count = Column(Integer, default=0)
    response_time_ms = Column(Integer)
    model_used = Column(String(100))
    user_id = Column(String(255))
    created_at = Column(DateTime, default=datetime.utcnow)


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_model_backend(model_name: str) -> tuple[str, str]:
    async with async_session() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(ModelRegistry.backend_name, ModelRegistry.backend_type).where(
                ModelRegistry.id == model_name
            )
        )
        row = result.first()
        if not row:
            raise ValueError(f"Model {model_name} not found in registry")
        return row.backend_name, row.backend_type


async def log_usage(
    model: str,
    backend_type: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    user_id: str | None = None,
):
    async with async_session() as session:
        log = UsageLog(
            model=model,
            backend_type=backend_type,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
            user_id=user_id,
        )
        session.add(log)
        await session.commit()
