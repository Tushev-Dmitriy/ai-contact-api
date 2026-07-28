"""Contact API request and response schemas."""

import re
import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

from app.db.models.contact_request import (
    ContactCategory,
    EmailStatus,
    ProcessingStatus,
    ProviderStatus,
    Sentiment,
    Urgency,
)

PHONE_CHARACTERS = re.compile(r"^[+\d\s().-]+$")


class ContactCreate(BaseModel):
    """Validated and normalized contact request input."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Anna Ivanova",
                    "phone": "+7 (912) 345-67-89",
                    "email": "anna@example.com",
                    "comment": "I would like to discuss a backend development project.",
                }
            ]
        },
    )

    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=7, max_length=16)
    email: EmailStr
    comment: str = Field(min_length=10, max_length=3000)

    @field_validator("name", mode="before")
    @classmethod
    def normalize_name(cls, value: object) -> object:
        """Trim and collapse whitespace in a textual name."""
        if not isinstance(value, str):
            return value
        return " ".join(value.split())

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value: object) -> object:
        """Trim and lowercase email for consistent storage."""
        if not isinstance(value, str):
            return value
        return value.strip().lower()

    @field_validator("phone", mode="before")
    @classmethod
    def normalize_phone(cls, value: object) -> object:
        """Normalize a practical international phone representation."""
        if not isinstance(value, str):
            return value
        candidate = value.strip()
        if len(candidate) > 64:
            raise ValueError("Phone number is too long")
        if not PHONE_CHARACTERS.fullmatch(candidate):
            raise ValueError("Phone number contains unsupported characters")
        if candidate.count("+") > 1 or (
            "+" in candidate and not candidate.startswith("+")
        ):
            raise ValueError("Phone number has an invalid plus sign")

        digits = "".join(character for character in candidate if character.isdigit())
        if not 7 <= len(digits) <= 15:
            raise ValueError("Phone number must contain between 7 and 15 digits")
        return f"+{digits}" if candidate.startswith("+") else digits


class ContactAccepted(BaseModel):
    """Public response after a contact request is persisted."""

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "request_id": "f5a881fd-4bee-4c83-91b9-f204619db856",
                    "status": "accepted",
                    "message": "Contact request accepted for processing",
                    "category": "project_request",
                }
            ]
        }
    )

    request_id: uuid.UUID
    status: str = "accepted"
    message: str = "Contact request accepted for processing"
    category: str | None = None


class ContactDetail(BaseModel):
    """A locally inspectable contact and all processing results."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    phone: str
    email: EmailStr
    comment: str
    category: ContactCategory | None
    sentiment: Sentiment | None
    urgency: Urgency | None
    ai_summary: str | None
    ai_provider_status: ProviderStatus
    processing_status: ProcessingStatus
    owner_email_status: EmailStatus
    user_email_status: EmailStatus
    created_at: datetime
    updated_at: datetime
