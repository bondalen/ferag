"""ORM-модели таблиц БД."""
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(Text, unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class RagInstance(Base):
    __tablename__ = "rag_instances"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fuseki_dataset: Mapped[str] = mapped_column(Text, nullable=False)
    cycle_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )


class RagMember(Base):
    __tablename__ = "rag_members"

    rag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rag_instances.id"), primary_key=True, nullable=False
    )
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id"), primary_key=True, nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)  # 'viewer' | 'editor'


class UploadCycle(Base):
    __tablename__ = "upload_cycles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rag_instances.id"), nullable=False
    )
    cycle_n: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )  # pending | running | review | merged | archived | failed
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    merged_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    rag_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("rag_instances.id"), nullable=False
    )
    cycle_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("upload_cycles.id"), nullable=True
    )
    type: Mapped[str] = mapped_column(Text, nullable=False)
    # graphrag | schema_induction | merge_ontologies | merge_triples | load_to_prod
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="pending"
    )  # pending | running | done | failed
    celery_task_id: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default="now()", nullable=False
    )
