import pytest
from pydantic import ValidationError

from app.schemas.contact import ContactCreate


def test_contact_input_is_normalized() -> None:
    contact = ContactCreate(
        name="  Ada   Lovelace ",
        phone=" +44 (20) 7946-0123 ",
        email=" ADA@Example.COM ",
        comment="  I would like to discuss a backend project.  ",
    )

    assert contact.name == "Ada Lovelace"
    assert contact.phone == "+442079460123"
    assert str(contact.email) == "ada@example.com"
    assert contact.comment == "I would like to discuss a backend project."


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("name", " "),
        ("phone", "123"),
        ("phone", "+1 202 CALL-NOW"),
        ("email", "not-an-email"),
        ("comment", "too short"),
    ],
)
def test_contact_input_rejects_invalid_values(field: str, value: str) -> None:
    payload = {
        "name": "Ada Lovelace",
        "phone": "+442079460123",
        "email": "ada@example.com",
        "comment": "A sufficiently long comment.",
    }
    payload[field] = value

    with pytest.raises(ValidationError):
        ContactCreate.model_validate(payload)


def test_contact_input_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        ContactCreate(
            name="Ada Lovelace",
            phone="+442079460123",
            email="ada@example.com",
            comment="A sufficiently long comment.",
            unexpected="value",  # type: ignore[call-arg]
        )
