"""add_chat_sessions

Таблица chat_sessions; session_id в chat_messages (NOT NULL после backfill).
Вариант A: для каждой пары (rag_id, user_id) с существующими сообщениями создаётся одна
дефолтная сессия, всем этим сообщениям проставляется session_id.

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b8c9d0e1f2a3"
down_revision: Union[str, Sequence[str], None] = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("rag_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["rag_id"], ["rag_instances.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_chat_sessions_rag_id", "chat_sessions", ["rag_id"], unique=False)
    op.create_index("ix_chat_sessions_user_id", "chat_sessions", ["user_id"], unique=False)

    # Добавляем session_id как nullable, backfill, затем NOT NULL
    op.add_column("chat_messages", sa.Column("session_id", sa.Integer(), nullable=True))
    conn = op.get_bind()

    # Для каждой пары (rag_id, user_id), у которой есть сообщения, создаём одну сессию
    rows = conn.execute(
        sa.text(
            "SELECT DISTINCT rag_id, user_id FROM chat_messages ORDER BY rag_id, user_id"
        )
    ).fetchall()
    for (rag_id, user_id) in rows:
        conn.execute(
            sa.text(
                "INSERT INTO chat_sessions (rag_id, user_id, title, created_at) "
                "VALUES (:rag_id, :user_id, NULL, now())"
            ),
            {"rag_id": rag_id, "user_id": user_id},
        )
        r = conn.execute(
            sa.text(
                "SELECT id FROM chat_sessions WHERE rag_id = :rag_id AND user_id = :user_id ORDER BY id DESC LIMIT 1"
            ),
            {"rag_id": rag_id, "user_id": user_id},
        ).fetchone()
        session_id = r[0]
        conn.execute(
            sa.text(
                "UPDATE chat_messages SET session_id = :sid WHERE rag_id = :rag_id AND user_id = :user_id"
            ),
            {"sid": session_id, "rag_id": rag_id, "user_id": user_id},
        )

    op.alter_column(
        "chat_messages",
        "session_id",
        existing_type=sa.Integer(),
        nullable=False,
    )
    op.create_foreign_key(
        "fk_chat_messages_session_id",
        "chat_messages",
        "chat_sessions",
        ["session_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_chat_messages_session_id", "chat_messages", ["session_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_chat_messages_session_id", table_name="chat_messages")
    op.drop_constraint("fk_chat_messages_session_id", "chat_messages", type_="foreignkey")
    op.drop_column("chat_messages", "session_id")
    op.drop_index("ix_chat_sessions_user_id", table_name="chat_sessions")
    op.drop_index("ix_chat_sessions_rag_id", table_name="chat_sessions")
    op.drop_table("chat_sessions")
