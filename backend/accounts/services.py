"""Business logic for refresh-token issuance and rotation."""

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from bson import ObjectId
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo.database import Database
from rest_framework.exceptions import APIException

from accounts.repository import (
    create_refresh_token as insert_refresh_token,
    delete_refresh_token,
    find_refresh_token_by_hash,
    revoke_refresh_token_family,
    rotate_refresh_token_record,
)
from common.object_id import parse_object_id
from common.time import utc_now

REFRESH_RACE_GRACE_SECONDS = 10


class InvalidRefreshToken(APIException):
    """An expired, unknown, revoked, or reused refresh token."""

    status_code = 401
    default_detail = "Refresh token is invalid or expired."
    default_code = "invalid_refresh_token"


class RefreshRace(APIException):
    """A previous token was retried shortly after a successful rotation."""

    status_code = 401
    default_detail = "Refresh token was already rotated; retry with the current cookie."
    default_code = "REFRESH_RACE"


def _refresh_lifetime() -> int:
    """Read the configured refresh lifetime and reject invalid configuration."""
    lifetime = settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS
    if lifetime <= 0:
        raise ImproperlyConfigured("JWT refresh-token lifetime must be positive.")
    return lifetime


def hash_refresh_token(token: str) -> str:
    """Return a hex SHA-256 digest for an opaque refresh token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _new_refresh_token() -> str:
    """Generate an opaque token with 256 bits of random entropy."""
    return secrets.token_urlsafe(32)


def _as_utc(value: datetime) -> datetime:
    """Treat MongoDB's default naive UTC datetimes as UTC-aware values."""
    if value.tzinfo is None or value.utcoffset() is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_refresh_token(
    database: Database[Any],
    user_id: ObjectId | str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
    family_id: str | None = None,
    now: datetime | None = None,
) -> str:
    """Issue a new refresh token and persist only its SHA-256 digest."""
    created_at = _as_utc(now or utc_now())
    raw_token = _new_refresh_token()
    insert_refresh_token(
        database,
        user_id=user_id,
        token_hash=hash_refresh_token(raw_token),
        family_id=family_id or secrets.token_urlsafe(16),
        expires_at=created_at + timedelta(seconds=_refresh_lifetime()),
        user_agent=user_agent,
        ip=ip,
        now=created_at,
    )
    return raw_token


def _raise_for_reuse(
    database: Database[Any],
    record: dict[str, Any],
    now: datetime,
) -> None:
    """Apply the duplicate-request grace rule or revoke a reused token family."""
    replacement_id = record.get("replaced_by")
    rotated_at = record.get("revoked_at")
    if (
        record.get("status") == "rotated"
        and isinstance(replacement_id, ObjectId)
        and isinstance(rotated_at, datetime)
        and now - _as_utc(rotated_at)
        <= timedelta(seconds=REFRESH_RACE_GRACE_SECONDS)
    ):
        replacement = database["refresh_tokens"].find_one({"_id": replacement_id})
        if (
            replacement is not None
            and replacement.get("family_id") == record.get("family_id")
            and replacement.get("status") == "active"
        ):
            raise RefreshRace()

    revoke_refresh_token_family(database, record["family_id"], now)
    raise InvalidRefreshToken("Refresh token reuse detected; sign in again.")


def rotate_refresh_token(
    database: Database[Any],
    token: str,
    *,
    user_agent: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> str:
    """Rotate a refresh token, detect reuse, and return the replacement token."""
    if not token:
        raise InvalidRefreshToken()
    current_time = _as_utc(now or utc_now())
    record = find_refresh_token_by_hash(database, hash_refresh_token(token))
    if record is None:
        raise InvalidRefreshToken()
    if record.get("status") != "active":
        _raise_for_reuse(database, record, current_time)
    if _as_utc(record["expires_at"]) <= current_time:
        raise InvalidRefreshToken()

    replacement = _new_refresh_token()
    replacement_id = insert_refresh_token(
        database,
        user_id=parse_object_id(record["user_id"]),
        token_hash=hash_refresh_token(replacement),
        family_id=record["family_id"],
        expires_at=current_time + timedelta(seconds=_refresh_lifetime()),
        user_agent=user_agent,
        ip=ip,
        now=current_time,
    )
    if not rotate_refresh_token_record(
        database,
        record["_id"],
        replacement_id,
        current_time,
    ):
        delete_refresh_token(database, replacement_id)
        updated_record = find_refresh_token_by_hash(
            database,
            hash_refresh_token(token),
        )
        if updated_record is not None:
            _raise_for_reuse(database, updated_record, current_time)
        raise InvalidRefreshToken()
    return replacement
