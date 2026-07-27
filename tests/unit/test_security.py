from app.core.security import secrets_match


def test_secrets_match_uses_exact_values() -> None:
    assert secrets_match("secret", "secret") is True
    assert secrets_match("secret", "different") is False
    assert secrets_match("secret", "secret-longer") is False
