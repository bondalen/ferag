"""add_chat_messages_table

Revision ID: a7b8c9d0e1f2
Revises: 1316c47e2e74
Create Date: 2026-02-22

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7b8c9d0e1f2'
down_revision: Union[str, Sequence[str], None] = '1316c47e2e74'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'chat_messages',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('rag_id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('role', sa.Text(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('context_used', sa.Integer(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default='now()', nullable=False),
        sa.ForeignKeyConstraint(['rag_id'], ['rag_instances.id'], ),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_chat_messages_rag_id'), 'chat_messages', ['rag_id'], unique=False)
    op.create_index(op.f('ix_chat_messages_user_id'), 'chat_messages', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_chat_messages_user_id'), table_name='chat_messages')
    op.drop_index(op.f('ix_chat_messages_rag_id'), table_name='chat_messages')
    op.drop_table('chat_messages')
