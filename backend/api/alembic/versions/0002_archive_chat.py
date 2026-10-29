"""article chat cache and article_chat job kind

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-29 18:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_KINDS = "kind IN ('news_batch', 'crunch', 'quiz_prep', 'classification', 'article_chat')"
_OLD_KINDS = "kind IN ('news_batch', 'crunch', 'quiz_prep', 'classification')"


def upgrade() -> None:
    op.execute("ALTER TABLE ai_jobs DROP CONSTRAINT IF EXISTS ck_ai_jobs_kind_valid")
    op.execute(f"ALTER TABLE ai_jobs ADD CONSTRAINT ck_ai_jobs_kind_valid CHECK ({_KINDS})")

    op.create_table(
        "article_chats",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="CASCADE",
            name=op.f("fk_article_chats_article_id_articles"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name=op.f("fk_article_chats_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_chats")),
        sa.UniqueConstraint("user_id", "article_id", name=op.f("uq_article_chats_user_id_article_id")),
    )
    op.create_index(op.f("ix_article_chats_article_id"), "article_chats", ["article_id"], unique=False)
    op.create_index(op.f("ix_article_chats_user_id"), "article_chats", ["user_id"], unique=False)

    op.create_table(
        "article_chat_messages",
        sa.Column("chat_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False),
        sa.Column("body", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=16), server_default="ready", nullable=False),
        sa.Column("cached", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'assistant')", name=op.f("ck_article_chat_messages_role_valid")),
        sa.CheckConstraint(
            "status IN ('ready', 'pending', 'failed')", name=op.f("ck_article_chat_messages_status_valid")
        ),
        sa.ForeignKeyConstraint(
            ["chat_id"],
            ["article_chats.id"],
            ondelete="CASCADE",
            name=op.f("fk_article_chat_messages_chat_id_article_chats"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_chat_messages")),
    )
    op.create_index(
        op.f("ix_article_chat_messages_chat_id"), "article_chat_messages", ["chat_id"], unique=False
    )
    op.create_index(
        "ix_article_chat_messages_chat_created",
        "article_chat_messages",
        ["chat_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "article_chat_cache",
        sa.Column("article_id", sa.UUID(), nullable=False),
        sa.Column("question_hash", sa.String(length=64), nullable=False),
        sa.Column("answer", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(
            ["article_id"],
            ["articles.id"],
            ondelete="CASCADE",
            name=op.f("fk_article_chat_cache_article_id_articles"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_article_chat_cache")),
        sa.UniqueConstraint(
            "article_id", "question_hash", name=op.f("uq_article_chat_cache_article_id_question_hash")
        ),
    )
    op.create_index(
        op.f("ix_article_chat_cache_article_id"), "article_chat_cache", ["article_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_article_chat_cache_article_id"), table_name="article_chat_cache")
    op.drop_table("article_chat_cache")
    op.drop_index("ix_article_chat_messages_chat_created", table_name="article_chat_messages")
    op.drop_index(op.f("ix_article_chat_messages_chat_id"), table_name="article_chat_messages")
    op.drop_table("article_chat_messages")
    op.drop_index(op.f("ix_article_chats_user_id"), table_name="article_chats")
    op.drop_index(op.f("ix_article_chats_article_id"), table_name="article_chats")
    op.drop_table("article_chats")
    op.execute("ALTER TABLE ai_jobs DROP CONSTRAINT IF EXISTS ck_ai_jobs_kind_valid")
    op.execute(f"ALTER TABLE ai_jobs ADD CONSTRAINT ck_ai_jobs_kind_valid CHECK ({_OLD_KINDS})")
