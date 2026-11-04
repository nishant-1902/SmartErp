from datetime import datetime, timedelta, timezone

import jwt
import pytest
from bson import ObjectId
from django.test import override_settings

from accounts.tokens import create_access_token, decode_access_token

JWT_SECRET = "unit-test-only-secret-for-HS256-not-production"
JWT_ISSUER = "test-api"
JWT_AUDIENCE = "test-client"


@pytest.fixture(autouse=True)
def configured_jwt():
    with override_settings(
        JWT_SECRET_KEY=JWT_SECRET,
        JWT_ISSUER=JWT_ISSUER,
        JWT_AUDIENCE=JWT_AUDIENCE,
        JWT_ACCESS_TOKEN_LIFETIME_SECONDS=900,
    ):
        yield


def make_payload(**overrides):
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(ObjectId()),
        "role": "employee",
        "token_version": 0,
        "jti": "test-token-id",
        "iat": now,
        "exp": now + timedelta(minutes=5),
        "iss": JWT_ISSUER,
        "aud": JWT_AUDIENCE,
        "type": "access",
    }
    payload.update(overrides)
    return payload


def test_access_token_has_expected_claims_and_round_trips():
    now = datetime.now(timezone.utc)
    user = {
        "_id": ObjectId(),
        "role": "employee",
        "token_version": 3,
        "email": "not-in-the-token@example.com",
        "password_hash": "not-in-the-token",
    }

    payload = decode_access_token(create_access_token(user, now=now))

    assert payload["sub"] == str(user["_id"])
    assert payload["role"] == "employee"
    assert payload["token_version"] == 3
    assert payload["iss"] == JWT_ISSUER
    assert payload["aud"] == JWT_AUDIENCE
    assert payload["type"] == "access"
    assert payload["iat"] == int(now.timestamp())
    assert payload["exp"] - payload["iat"] == 900
    assert "email" not in payload
    assert "password_hash" not in payload


def test_expired_access_token_is_rejected():
    token = jwt.encode(
        make_payload(
            iat=datetime.now(timezone.utc) - timedelta(minutes=10),
            exp=datetime.now(timezone.utc) - timedelta(minutes=5),
        ),
        JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_tampered_access_token_is_rejected():
    token = create_access_token(
        {"_id": ObjectId(), "role": "employee", "token_version": 0}
    )
    tampered = token[:-1] + ("a" if token[-1] != "a" else "b")

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(tampered)


def test_wrong_audience_is_rejected():
    token = jwt.encode(
        make_payload(aud="another-client"),
        JWT_SECRET,
        algorithm="HS256",
    )

    with pytest.raises(jwt.InvalidAudienceError):
        decode_access_token(token)


@pytest.mark.parametrize(
    ("overrides", "error"),
    [
        ({"iss": "another-api"}, jwt.InvalidIssuerError),
        ({"type": "refresh"}, jwt.InvalidTokenError),
        ({"sub": "not-an-object-id"}, jwt.InvalidTokenError),
        ({"token_version": True}, jwt.InvalidTokenError),
    ],
)
def test_invalid_issuer_type_subject_and_token_version_are_rejected(
    overrides,
    error,
):
    token = jwt.encode(make_payload(**overrides), JWT_SECRET, algorithm="HS256")

    with pytest.raises(error):
        decode_access_token(token)


def test_missing_required_access_token_claim_is_rejected():
    payload = make_payload()
    payload.pop("jti")
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with pytest.raises(jwt.MissingRequiredClaimError):
        decode_access_token(token)


def test_none_algorithm_is_rejected():
    token = jwt.encode(make_payload(), key="", algorithm="none")

    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(token)
