"""Standalone password hashing and strength validation."""

from django.contrib.auth.hashers import (
    check_password,
    get_hasher,
    identify_hasher,
    make_password,
)
from django.contrib.auth.password_validation import CommonPasswordValidator
from django.core.exceptions import ValidationError

from common.exceptions import ValidationFailed


def validate_password_strength(password: str, email: str) -> None:
    """Require a long, non-common password that is not the account email."""
    if len(password) < 10:
        raise ValidationFailed(
            "Password must contain at least 10 characters.",
            details={"field": "password"},
        )
    if password.casefold() == email.strip().casefold():
        raise ValidationFailed(
            "Password must not be the same as the email address.",
            details={"field": "password"},
        )
    try:
        CommonPasswordValidator().validate(password)
    except ValidationError as exc:
        raise ValidationFailed(
            "Choose a password that is not commonly used.",
            details={"field": "password"},
        ) from exc


def hash_password(password: str) -> str:
    """Hash a password with the configured preferred Django hasher."""
    return make_password(password)


def verify_password(password: str, encoded_password: str) -> bool:
    """Check a password against a standalone Django password hash."""
    try:
        return check_password(password, encoded_password)
    except ValueError:
        return False


def needs_rehash(encoded_password: str) -> bool:
    """Return whether a stored hash does not use the preferred password hasher."""
    try:
        return identify_hasher(encoded_password).algorithm != get_hasher().algorithm
    except ValueError:
        return True
