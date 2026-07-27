"""Contact request persistence model."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, Index, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ContactCategory(enum.StrEnum):
    """Supported AI contact categories."""

    JOB_OFFER = "job_offer"
    PROJECT_REQUEST = "project_request"
    COLLABORATION = "collaboration"
    SUPPORT = "support"
    FEEDBACK = "feedback"
    SPAM = "spam"
    OTHER = "other"


class Sentiment(enum.StrEnum):
    """Supported contact sentiment values."""

    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"


class Urgency(enum.StrEnum):
    """Supported contact urgency values."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ProviderStatus(enum.StrEnum):
    """AI provider result states."""

    PENDING = "pending"
    AVAILABLE = "available"
    UNAVAILABLE = "unavailable"
    INVALID_RESPONSE = "invalid_response"


class ProcessingStatus(enum.StrEnum):
    """Overall contact processing states."""

    PROCESSING = "processing"
    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class EmailStatus(enum.StrEnum):
    """Delivery states for each email notification."""

    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


def string_enum(
    enum_type: type[enum.StrEnum],
    *,
    name: str,
    length: int,
) -> Enum:
    """Store stable enum values as constrained strings across databases."""
    return Enum(
        enum_type,
        values_callable=lambda members: [member.value for member in members],
        native_enum=False,
        create_constraint=True,
        validate_strings=True,
        name=name,
        length=length,
    )


class ContactRequest(Base):
    """A persisted portfolio contact request and its processing state."""

    __tablename__ = "contact_requests"
    __table_args__ = (
        Index("ix_contact_requests_created_at", "created_at"),
        Index("ix_contact_requests_category", "category"),
        Index("ix_contact_requests_processing_status", "processing_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(100))
    phone: Mapped[str] = mapped_column(String(32))
    email: Mapped[str] = mapped_column(String(320))
    comment: Mapped[str] = mapped_column(Text)
    category: Mapped[ContactCategory | None] = mapped_column(
        string_enum(ContactCategory, name="ck_contact_category", length=32),
        nullable=True,
    )
    sentiment: Mapped[Sentiment | None] = mapped_column(
        string_enum(Sentiment, name="ck_contact_sentiment", length=16),
        nullable=True,
    )
    urgency: Mapped[Urgency | None] = mapped_column(
        string_enum(Urgency, name="ck_contact_urgency", length=16),
        nullable=True,
    )
    ai_summary: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ai_provider_status: Mapped[ProviderStatus] = mapped_column(
        string_enum(ProviderStatus, name="ck_contact_ai_provider_status", length=24),
        default=ProviderStatus.PENDING,
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        string_enum(ProcessingStatus, name="ck_contact_processing_status", length=16),
        default=ProcessingStatus.PROCESSING,
    )
    owner_email_status: Mapped[EmailStatus] = mapped_column(
        string_enum(EmailStatus, name="ck_contact_owner_email_status", length=16),
        default=EmailStatus.PENDING,
    )
    user_email_status: Mapped[EmailStatus] = mapped_column(
        string_enum(EmailStatus, name="ck_contact_user_email_status", length=16),
        default=EmailStatus.PENDING,
    )
    source_ip_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
