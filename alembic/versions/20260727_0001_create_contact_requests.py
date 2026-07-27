"""Create contact requests table.

Revision ID: 20260727_0001
Revises:
Create Date: 2026-07-27
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260727_0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create contact request persistence."""
    op.create_table(
        "contact_requests",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column(
            "category",
            sa.Enum(
                "job_offer",
                "project_request",
                "collaboration",
                "support",
                "feedback",
                "spam",
                "other",
                name="ck_contact_category",
                native_enum=False,
                create_constraint=True,
                length=32,
            ),
            nullable=True,
        ),
        sa.Column(
            "sentiment",
            sa.Enum(
                "positive",
                "neutral",
                "negative",
                name="ck_contact_sentiment",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column(
            "urgency",
            sa.Enum(
                "low",
                "medium",
                "high",
                name="ck_contact_urgency",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=True,
        ),
        sa.Column("ai_summary", sa.String(length=200), nullable=True),
        sa.Column(
            "ai_provider_status",
            sa.Enum(
                "pending",
                "available",
                "unavailable",
                "invalid_response",
                name="ck_contact_ai_provider_status",
                native_enum=False,
                create_constraint=True,
                length=24,
            ),
            nullable=False,
        ),
        sa.Column(
            "processing_status",
            sa.Enum(
                "processing",
                "completed",
                "partial",
                "failed",
                name="ck_contact_processing_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "owner_email_status",
            sa.Enum(
                "pending",
                "sent",
                "failed",
                "skipped",
                name="ck_contact_owner_email_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column(
            "user_email_status",
            sa.Enum(
                "pending",
                "sent",
                "failed",
                "skipped",
                name="ck_contact_user_email_status",
                native_enum=False,
                create_constraint=True,
                length=16,
            ),
            nullable=False,
        ),
        sa.Column("source_ip_hash", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_contact_requests_category",
        "contact_requests",
        ["category"],
    )
    op.create_index(
        "ix_contact_requests_created_at",
        "contact_requests",
        ["created_at"],
    )
    op.create_index(
        "ix_contact_requests_processing_status",
        "contact_requests",
        ["processing_status"],
    )


def downgrade() -> None:
    """Drop contact request persistence."""
    op.drop_index(
        "ix_contact_requests_processing_status",
        table_name="contact_requests",
    )
    op.drop_index("ix_contact_requests_created_at", table_name="contact_requests")
    op.drop_index("ix_contact_requests_category", table_name="contact_requests")
    op.drop_table("contact_requests")
