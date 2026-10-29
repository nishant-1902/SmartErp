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

from accounts.passwords import hash_password, verify_password
from accounts.repository import (
    clear_login_attempts,
    create_refresh_token as insert_refresh_token,
    delete_refresh_token,
    find_refresh_token_by_hash,
    find_user_by_email,
    find_user_by_id,
    get_login_attempt,
    revoke_refresh_token_family,
    rotate_refresh_token_record,
    upsert_login_attempt,
    write_audit_log,
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


def write_security_audit(
    database: Database[Any],
    *,
    actor_id: ObjectId | str | None,
    action: str,
    resource: str,
    resource_id: str | ObjectId | None,
    outcome: str,
    ip: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> None:
    """Record a security-sensitive event for later auditing."""
    write_audit_log(
        database,
        actor_id=actor_id,
        action=action,
        resource=resource,
        resource_id=resource_id,
        outcome=outcome,
        ip=ip,
        user_agent=user_agent,
        now=now,
    )


def get_public_user(user: dict[str, Any]) -> dict[str, Any]:
    """Return a user-like object with secret fields removed."""
    public = dict(user)
    public.pop("password_hash", None)
    public.pop("password_reset_token_hash", None)
    public.pop("password_reset_expires_at", None)
    public["id"] = str(public["_id"])
    public["_id"] = str(public["_id"])
    return public


def get_login_retry_after(database: Database[Any], email: str, client_ip: str) -> int:
    """Return the remaining lock duration in seconds for a locked email/IP pair."""
    record = get_login_attempt(database, email, client_ip)
    if record is None:
        return 0
    now = utc_now()
    locked_until = record.get("locked_until")
    if locked_until is None:
        return 0
    remaining = (locked_until - now).total_seconds()
    return max(1, int(remaining))


def check_login_lockout(database: Database[Any], email: str, client_ip: str) -> tuple[bool, int]:
    """Return whether a login is temporarily blocked and the remaining retry time."""
    record = get_login_attempt(database, email, client_ip)
    if record is None:
        return False, 0
    now = utc_now()
    locked_until = record.get("locked_until")
    if isinstance(locked_until, datetime) and locked_until > now:
        return True, get_login_retry_after(database, email, client_ip)
    if record.get("expires_at") and record.get("expires_at") <= now:
        database["login_attempts"].delete_one({
            "email": record.get("email"),
            "client_ip": client_ip,
        })
    return False, 0


def record_failed_login(
    database: Database[Any],
    *,
    email: str,
    client_ip: str,
    user: dict[str, Any] | None,
    ip: str | None,
    user_agent: str | None,
    now: datetime | None = None,
) -> tuple[bool, int]:
    """Increment the failed-login counter and lock after the fifth failure."""
    current_time = _as_utc(now or utc_now())
    record = get_login_attempt(database, email, client_ip)
    if record is not None and record.get("expires_at") and _as_utc(record["expires_at"]) <= current_time:
        record = None
    if record is None:
        record = {
            "email": email,
            "client_ip": client_ip,
            "failed_count": 0,
            "window_started_at": current_time,
            "expires_at": current_time + timedelta(minutes=15),
            "locked_until": None,
        }
    failed_count = int(record.get("failed_count", 0)) + 1
    if failed_count >= 5:
        locked_until = current_time + timedelta(minutes=15)
        upsert_login_attempt(
            database,
            email,
            client_ip,
            failed_count=failed_count,
            window_started_at=current_time,
            expires_at=locked_until + timedelta(minutes=15),
            locked_until=locked_until,
        )
        write_security_audit(
            database,
            actor_id=user.get("_id") if user else None,
            action="login_failed",
            resource="user",
            resource_id=user.get("_id") if user else email,
            outcome="rate_limited",
            ip=ip,
            user_agent=user_agent,
            now=current_time,
        )
        return True, 900
    upsert_login_attempt(
        database,
        email,
        client_ip,
        failed_count=failed_count,
        window_started_at=record.get("window_started_at", current_time),
        expires_at=current_time + timedelta(minutes=15),
        locked_until=None,
    )
    return False, 0


def record_successful_login(
    database: Database[Any],
    *,
    user: dict[str, Any],
    ip: str | None,
    user_agent: str | None,
    now: datetime | None = None,
) -> None:
    """Clear failed attempts and log a successful sign-in."""
    clear_login_attempts(database, user["email"], ip or "unknown")
    write_security_audit(
        database,
        actor_id=user.get("_id"),
        action="login_success",
        resource="user",
        resource_id=user.get("_id"),
        outcome="success",
        ip=ip,
        user_agent=user_agent,
        now=now or utc_now(),
    )


def request_password_reset(
    database: Database[Any],
    *,
    email: str,
    ip: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> str | None:
    """Issue a single-use password-reset token for the matching email account."""
    user = find_user_by_email(database, email)
    if user is None:
        return None
    current_time = _as_utc(now or utc_now())
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
    database["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_reset_token_hash": token_hash,
                "password_reset_expires_at": current_time + timedelta(minutes=15),
                "updated_at": current_time,
            }
        },
    )
    link = (
        f"http://localhost:5173/reset-password?email={user['email']}&token={token}"
    )
    print(f"Password reset link: {link}")
    write_security_audit(
        database,
        actor_id=user.get("_id"),
        action="password_reset_requested",
        resource="user",
        resource_id=user.get("_id"),
        outcome="success",
        ip=ip,
        user_agent=user_agent,
        now=current_time,
    )
    return link


def confirm_password_reset(
    database: Database[Any],
    *,
    email: str,
    raw_token: str,
    new_password: str,
    ip: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Validate the reset token, replace the password, and invalidate refresh sessions."""
    current_time = _as_utc(now or utc_now())
    user = find_user_by_email(database, email)
    if user is None:
        raise InvalidRefreshToken("Password reset link is invalid or expired.")
    token_hash = user.get("password_reset_token_hash")
    expires_at = user.get("password_reset_expires_at")
    if not token_hash or not expires_at or _as_utc(expires_at) < current_time:
        raise InvalidRefreshToken("Password reset link is invalid or expired.")
    if hashlib.sha256(raw_token.encode("utf-8")).hexdigest() != token_hash:
        raise InvalidRefreshToken("Password reset link is invalid or expired.")
    database["users"].update_one(
        {"_id": user["_id"]},
        {
            "$set": {
                "password_hash": hash_password(new_password),
                "password_reset_token_hash": None,
                "password_reset_expires_at": None,
                "correct_token_version": user.get("token_version", 0) + 1,
                "token_version": user.get("token_version", 0) + 1,
                "updated_at": current_time,
            }
        },
    )
    database["refresh_tokens"].update_many(
        {"user_id": user["_id"], "status": {"$ne": "revoked"}},
        {"$set": {"status": "revoked", "revoked_at": current_time}},
    )
    write_security_audit(
        database,
        actor_id=user.get("_id"),
        action="password_reset_confirmed",
        resource="user",
        resource_id=user.get("_id"),
        outcome="success",
        ip=ip,
        user_agent=user_agent,
        now=current_time,
    )
    return {"status": "password_reset"}


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
