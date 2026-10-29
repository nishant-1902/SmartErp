import pytest
from django.contrib.auth.hashers import make_password

from accounts.passwords import (
    hash_password,
    needs_rehash,
    validate_password_strength,
    verify_password,
)
from common.exceptions import ValidationFailed


def test_hash_and_verify_password():
    encoded = hash_password("a-long-unique-password-8")

    assert encoded != "a-long-unique-password-8"
    assert verify_password("a-long-unique-password-8", encoded)
    assert not needs_rehash(encoded)


def test_wrong_password_does_not_verify():
    encoded = hash_password("a-long-unique-password-8")

    assert not verify_password("not-the-password", encoded)


def test_needs_rehash_when_hash_uses_nonpreferred_hasher():
    encoded = make_password("a-long-unique-password-8", hasher="pbkdf2_sha256")

    assert needs_rehash(encoded)


@pytest.mark.parametrize(
    ("password", "email"),
    [
        ("short", "person@example.com"),
        ("password123", "person@example.com"),
        ("person@example.com", "person@example.com"),
        ("PERSON@EXAMPLE.COM", "person@example.com"),
    ],
)
def test_password_strength_rejects_weak_or_email_password(password, email):
    with pytest.raises(ValidationFailed):
        validate_password_strength(password, email)


def test_password_strength_accepts_long_unique_password():
    validate_password_strength("violet-river-planet-482", "person@example.com")
