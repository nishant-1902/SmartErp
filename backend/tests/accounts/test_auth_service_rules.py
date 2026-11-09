"""Service-level security tests for login throttling and password resets."""

from datetime import timedelta
import hashlib

import pytest
from django.test import override_settings

from accounts.passwords import hash_password, verify_password
from accounts.services import (
    InvalidRefreshToken,
    check_login_lockout,
    confirm_password_reset,
    record_failed_login,
    record_successful_login,
    request_password_reset,
)
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase


def insert_user(database, *, email="security@example.test"):
    """Insert a minimal account record with the fields used by auth services."""
    user = {
        "email": email,
        "password_hash": hash_password("ExistingSafePass887!"),
        "role": "employee",
        "is_active": True,
        "token_version": 0,
    }
    user["_id"] = database["users"].insert_one(user).inserted_id
    return user


def test_login_lockout_starts_after_fifth_failure_and_expires():
    database = FakeDatabase()
    now = utc_now()

    for attempt in range(1, 5):
        assert record_failed_login(
            database,
            email="blocked@example.test",
            client_ip="127.0.0.1",
            user=None,
            ip="127.0.0.1",
            user_agent="pytest",
            now=now,
        ) == (False, 0)

    assert record_failed_login(
        database,
        email="blocked@example.test",
        client_ip="127.0.0.1",
        user=None,
        ip="127.0.0.1",
        user_agent="pytest",
        now=now,
    ) == (True, 900)
    locked, retry_after = check_login_lockout(
        database,
        "blocked@example.test",
        "127.0.0.1",
    )
    assert locked is True
    assert 1 <= retry_after <= 900
    assert database["audit_logs"].count_documents(
        {"action": "login_failed", "outcome": "rate_limited"}
    ) == 1

    expired = now - timedelta(seconds=1)
    database["login_attempts"].insert_one(
        {
            "email": "expired@example.test",
            "client_ip": "127.0.0.1",
            "failed_count": 5,
            "expires_at": expired,
            "locked_until": expired,
        }
    )
    assert check_login_lockout(
        database,
        "expired@example.test",
        "127.0.0.1",
    ) == (False, 0)
    assert database["login_attempts"].find_one(
        {"email": "expired@example.test"}
    ) is None


@pytest.mark.parametrize("use_naive_datetimes", [False, True])
def test_login_lockout_compares_naive_and_aware_datetimes_as_utc(
    use_naive_datetimes,
):
    database = FakeDatabase()
    now = utc_now()
    locked_until = now + timedelta(minutes=5)
    expires_at = now + timedelta(minutes=20)
    if use_naive_datetimes:
        locked_until = locked_until.replace(tzinfo=None)
        expires_at = expires_at.replace(tzinfo=None)
    database["login_attempts"].insert_one(
        {
            "email": "locked@example.test",
            "client_ip": "127.0.0.1",
            "failed_count": 5,
            "expires_at": expires_at,
            "locked_until": locked_until,
        }
    )

    locked, retry_after = check_login_lockout(
        database,
        "locked@example.test",
        "127.0.0.1",
    )

    assert locked is True
    assert 1 <= retry_after <= 300


@pytest.mark.parametrize("use_naive_datetime", [False, True])
def test_expired_login_attempt_is_removed_for_naive_or_aware_expiry(
    use_naive_datetime,
):
    database = FakeDatabase()
    expired_at = utc_now() - timedelta(seconds=1)
    if use_naive_datetime:
        expired_at = expired_at.replace(tzinfo=None)
    database["login_attempts"].insert_one(
        {
            "email": "expired@example.test",
            "client_ip": "127.0.0.1",
            "failed_count": 5,
            "expires_at": expired_at,
            "locked_until": expired_at,
        }
    )

    assert check_login_lockout(
        database,
        "expired@example.test",
        "127.0.0.1",
    ) == (False, 0)
    assert database["login_attempts"].find_one(
        {"email": "expired@example.test"}
    ) is None


def test_login_attempt_with_missing_expiry_and_lock_fields_is_safe():
    database = FakeDatabase()
    database["login_attempts"].insert_one(
        {
            "email": "legacy@example.test",
            "client_ip": "127.0.0.1",
            "failed_count": 1,
        }
    )

    assert check_login_lockout(
        database,
        "legacy@example.test",
        "127.0.0.1",
    ) == (False, 0)


def test_successful_login_clears_attempts_and_writes_audit():
    database = FakeDatabase()
    user = insert_user(database)
    database["login_attempts"].insert_one(
        {
            "email": user["email"],
            "client_ip": "127.0.0.1",
            "failed_count": 3,
        }
    )

    record_successful_login(
        database,
        user=user,
        ip="127.0.0.1",
        user_agent="pytest",
    )

    assert database["login_attempts"].find_one(
        {"email": user["email"], "client_ip": "127.0.0.1"}
    ) is None
    assert database["audit_logs"].find_one(
        {"action": "login_success", "actor_id": user["_id"]}
    ) is not None


def test_password_reset_request_is_generic_for_unknown_email(capsys):
    with override_settings(DEBUG=True):
        result = request_password_reset(
            FakeDatabase(),
            email="missing@example.test",
        )

    assert result is None
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize(
    ("email", "stored_hash", "expires_at", "submitted_token"),
    [
        ("missing@example.test", None, None, "reset-token"),
        ("reset@example.test", None, None, "reset-token"),
        (
            "reset@example.test",
            hashlib.sha256(b"reset-token").hexdigest(),
            utc_now() - timedelta(seconds=1),
            "reset-token",
        ),
        (
            "reset@example.test",
            hashlib.sha256(b"another-token").hexdigest(),
            utc_now() + timedelta(minutes=5),
            "reset-token",
        ),
    ],
)
def test_password_reset_rejects_unknown_expired_or_mismatched_tokens(
    email,
    stored_hash,
    expires_at,
    submitted_token,
):
    database = FakeDatabase()
    if email != "missing@example.test":
        insert_user(database, email=email)
        database["users"].update_one(
            {"email": email},
            {
                "$set": {
                    "password_reset_token_hash": stored_hash,
                    "password_reset_expires_at": expires_at,
                }
            },
        )

    with pytest.raises(InvalidRefreshToken):
        confirm_password_reset(
            database,
            email=email,
            raw_token=submitted_token,
            new_password="A-Strong-Unique-Password-882!",
        )

    if email != "missing@example.test":
        stored_user = database["users"].find_one({"email": email})
        assert verify_password("ExistingSafePass887!", stored_user["password_hash"])
