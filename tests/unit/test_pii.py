from app.utils.pii import hash_ip, mask_email, mask_phone


def test_hash_ip_is_stable_and_does_not_contain_source() -> None:
    digest = hash_ip("203.0.113.42", salt="test-salt")

    assert digest == hash_ip("203.0.113.42", salt="test-salt")
    assert digest is not None
    assert "203.0.113.42" not in digest


def test_mask_email_hides_local_part() -> None:
    assert mask_email("person@example.com") == "p***@example.com"
    assert mask_email("invalid") == "***"


def test_mask_phone_exposes_only_last_two_digits() -> None:
    assert mask_phone("+1 (202) 555-0199") == "***99"
    assert mask_phone("no digits") == "***"
