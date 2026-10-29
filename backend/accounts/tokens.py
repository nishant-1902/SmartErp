"""JWT access-token creation and validation."""

import secrets
from collections.abc import Mapping
from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from common.exceptions import ValidationFailed
from common.object_id import parse_object_id


def _jwt_settings() -> tuple[str, str, str, int]:
    """Return required JWT configuration or fail with a clear configuration error."""
    secret = settings.JWT_SECRET_KEY
    issuer = settings.JWT_ISSUER
    audience = settings.JWT_AUDIENCE
    lifetime = settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    if not secret:
        raise ImproperlyConfigured("JWT_SECRET_KEY is not configured.")
    if not issuer or not audience or lifetime <= 0:
        raise ImproperlyConfigured("JWT issuer, audience, and lifetime must be valid.")
    return secret, issuer, audience, lifetime


def create_access_token(
    user: Mapping[str, Any],
    *,
    now: datetime | None = None,
) -> str:
    """Create a short-lived HS256 access token for a user document."""
    secret, issuer, audience, lifetime = _jwt_settings()
    user_id = parse_object_id(user.get("_id", user.get("id")))
    role = user.get("role")
    token_version = user.get("token_version")
    if not isinstance(role, str) or not role:
        raise ValueError("User role must be a non-empty string.")
    if (
        not isinstance(token_version, int)
        or isinstance(token_version, bool)
        or token_version < 0
    ):
        raise ValueError("User token_version must be a non-negative integer.")

    issued_at = now or datetime.now(timezone.utc)
    if issued_at.tzinfo is None or issued_at.utcoffset() is None:
        raise ValueError("Access-token time must be timezone-aware.")
    issued_at = issued_at.astimezone(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "token_version": token_version,
        "jti": secrets.token_urlsafe(16),
        "iat": issued_at,
        "exp": issued_at + timedelta(seconds=lifetime),
        "iss": issuer,
        "aud": audience,
        "type": "access",
    }
    return jwt.encode(payload, secret, algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify an access JWT's signature, time limits, issuer, audience, and type."""
    secret, issuer, audience, _ = _jwt_settings()
    payload = jwt.decode(
        token,
        secret,
        algorithms=["HS256"],
        issuer=issuer,
        audience=audience,
        options={
            "require": [
                "sub",
                "role",
                "token_version",
                "jti",
                "iat",
                "exp",
                "iss",
                "aud",
                "type",
            ]
        },
    )
    if payload.get("type") != "access":
        raise jwt.InvalidTokenError("Token type must be access.")
    try:
        parse_object_id(payload.get("sub"))
    except ValidationFailed as exc:
        raise jwt.InvalidTokenError("Token subject is invalid.") from exc
    if (
        not isinstance(payload.get("role"), str)
        or not payload["role"]
        or not isinstance(payload.get("token_version"), int)
        or isinstance(payload.get("token_version"), bool)
        or payload["token_version"] < 0
        or not isinstance(payload.get("jti"), str)
        or not payload["jti"]
    ):
        raise jwt.InvalidTokenError("Access-token claims are invalid.")
    return payload
