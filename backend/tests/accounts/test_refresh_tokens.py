from datetime import datetime, timedelta, timezone
import hashlib

import pytest
from bson import ObjectId
from django.test import override_settings

from accounts.repository import find_refresh_token_by_hash
from accounts.services import (
    InvalidRefreshToken,
    RefreshRace,
    create_refresh_token,
    hash_refresh_token,
    rotate_refresh_token,
)
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def refresh_settings():
    with override_settings(JWT_REFRESH_TOKEN_LIFETIME_SECONDS=3600):
        yield


def test_refresh_tokens_are_stored_hashed_and_rotate(refresh_settings):
    database = FakeDatabase()
    user_id = ObjectId()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    raw_token = create_refresh_token(database, user_id, now=now)
    original_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
    original = find_refresh_token_by_hash(database, original_hash)

    assert original is not None
    assert original_hash == hash_refresh_token(raw_token)
    assert raw_token not in original.values()

    replacement = rotate_refresh_token(database, raw_token, now=now + timedelta(seconds=1))
    replacement_record = find_refresh_token_by_hash(
        database,
        hash_refresh_token(replacement),
    )
    original_after_rotation = find_refresh_token_by_hash(database, original_hash)

    assert replacement != raw_token
    assert replacement_record is not None
    assert replacement_record["user_id"] == user_id
    assert replacement_record["family_id"] == original["family_id"]
    assert replacement_record["status"] == "active"
    assert original_after_rotation["status"] == "rotated"
    assert original_after_rotation["replaced_by"] == replacement_record["_id"]


def test_immediate_previous_token_retry_is_401_race_without_family_revocation(
    refresh_settings,
):
    database = FakeDatabase()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_token = create_refresh_token(database, ObjectId(), now=now)
    replacement = rotate_refresh_token(database, old_token, now=now)

    with pytest.raises(RefreshRace) as exc_info:
        rotate_refresh_token(
            database,
            old_token,
            now=now + timedelta(seconds=5),
        )

    assert exc_info.value.status_code == 401
    assert exc_info.value.default_code == "REFRESH_RACE"
    family_records = list(database["refresh_tokens"].documents.values())
    assert sorted(record["status"] for record in family_records) == ["active", "rotated"]
    assert find_refresh_token_by_hash(
        database,
        hash_refresh_token(replacement),
    )["status"] == "active"


def test_reuse_after_grace_revokes_entire_family(refresh_settings):
    database = FakeDatabase()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    old_token = create_refresh_token(database, ObjectId(), now=now)
    replacement = rotate_refresh_token(database, old_token, now=now)

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(
            database,
            old_token,
            now=now + timedelta(seconds=11),
        )

    assert {
        record["status"]
        for record in database["refresh_tokens"].documents.values()
    } == {"revoked"}
    assert find_refresh_token_by_hash(
        database,
        hash_refresh_token(replacement),
    )["status"] == "revoked"


def test_expired_refresh_token_is_rejected(refresh_settings):
    database = FakeDatabase()
    now = datetime(2026, 1, 1, tzinfo=timezone.utc)
    token = create_refresh_token(database, ObjectId(), now=now)

    with pytest.raises(InvalidRefreshToken):
        rotate_refresh_token(database, token, now=now + timedelta(hours=1))
