from datetime import timedelta
from uuid import uuid4

import pytest
from bson import ObjectId
from django.conf import settings
from django.test import override_settings
from django.urls import path
from django.utils.module_loading import import_string
from rest_framework.decorators import api_view, permission_classes
from rest_framework.test import APIClient

from accounts.authentication import AuthUser, MongoJWTAuthentication
from accounts.tokens import create_access_token
from common.permissions import IsAuthenticatedMongo, has_permission, require
from common.permissions_matrix import ROLE_PERMISSIONS
from common.responses import success_response
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo, require("employees:write")])
def protected_employees_endpoint(request):
    return success_response({"role": request.user.role})


urlpatterns = [path("protected/employees/", protected_employees_endpoint)]


@pytest.fixture
def configured_auth(monkeypatch):
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "authentication-test-secret-key-with-adequate-length",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "authentication-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "authentication-test-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")


@pytest.fixture
def fake_mongo(monkeypatch):
    database = FakeDatabase()

    class FakeMongoClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def __getitem__(self, database_name):
            assert database_name == "smarterp_test"
            return database

    monkeypatch.setattr(
        "accounts.authentication.MongoClient",
        lambda *args, **kwargs: FakeMongoClient(),
    )
    return database


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def auth_urlconf(configured_auth, monkeypatch):
    monkeypatch.setattr(settings, "ROOT_URLCONF", __name__)


def insert_user(database, role, **overrides):
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "role": role,
        "is_active": True,
        "token_version": 0,
    }
    user.update(overrides)
    database["users"].insert_one(user)
    return user


def bearer_token(user, *, now=None):
    return create_access_token(user, now=now)


def request_protected(client, token=None):
    headers = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token else {}
    return client.get("/protected/employees/", **headers)


def test_missing_token_returns_401_with_bearer_challenge(
    client,
    auth_urlconf,
):
    response = request_protected(client)

    assert response.status_code == 401
    assert MongoJWTAuthentication().authenticate_header(None) == "Bearer"


def test_invalid_token_returns_401(client, auth_urlconf):
    response = request_protected(client, "not-a-jwt")

    assert response.status_code == 401


def test_expired_token_returns_401(client, auth_urlconf, fake_mongo):
    user = insert_user(fake_mongo, "hr_manager")
    token = bearer_token(user, now=utc_now() - timedelta(minutes=30))

    response = request_protected(client, token)

    assert response.status_code == 401


@pytest.mark.parametrize(
    "updated_fields",
    [
        {"is_active": False},
        {"token_version": 1},
    ],
)
def test_deactivated_or_revoked_user_returns_401(
    client,
    auth_urlconf,
    fake_mongo,
    updated_fields,
):
    user = insert_user(fake_mongo, "hr_manager")
    token = bearer_token(user)
    fake_mongo["users"].update_one(
        {"_id": user["_id"]},
        {"$set": updated_fields},
    )

    response = request_protected(client, token)

    assert response.status_code == 401


def test_wrong_role_returns_403(client, auth_urlconf, fake_mongo):
    user = insert_user(fake_mongo, "employee")

    response = request_protected(client, bearer_token(user))

    assert response.status_code == 403


def test_correct_role_returns_200(client, auth_urlconf, fake_mongo):
    user = insert_user(fake_mongo, "hr_manager")

    response = request_protected(client, bearer_token(user))

    assert response.status_code == 200
    assert response.json()["data"]["role"] == "hr_manager"


@pytest.mark.parametrize(
    ("role", "expected_status"),
    [
        (
            role,
            200 if "employees:write" in permissions else 403,
        )
        for role, permissions in ROLE_PERMISSIONS.items()
    ],
)
def test_protected_endpoint_follows_entire_role_matrix(
    client,
    auth_urlconf,
    fake_mongo,
    role,
    expected_status,
):
    user = insert_user(fake_mongo, role)

    response = request_protected(client, bearer_token(user))

    assert response.status_code == expected_status


def test_default_drf_settings_use_mongo_auth_and_authenticated_permission():
    auth_classes = [
        import_string(path)
        for path in settings.REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]
    ]
    permission_classes = [
        import_string(path)
        for path in settings.REST_FRAMEWORK["DEFAULT_PERMISSION_CLASSES"]
    ]

    assert auth_classes == [MongoJWTAuthentication]
    assert permission_classes == [IsAuthenticatedMongo]


def test_health_login_refresh_and_password_reset_are_public(client):
    with override_settings(ROOT_URLCONF="config.urls"):
        assert client.get("/api/health/").status_code == 200
        assert client.post("/api/auth/login/", {}, format="json").status_code == 400
        assert client.post("/api/auth/refresh/", {}, format="json").status_code == 403
        assert client.post("/api/auth/logout/").status_code == 401
        assert (
            client.post(
                "/api/auth/password-reset/confirm/",
                {},
                format="json",
            ).status_code
            == 400
        )
        assert (
            client.post(
                "/api/auth/password-reset/request/",
                {},
                format="json",
            ).status_code == 400
        )


def test_permission_helpers_deny_missing_user_and_check_role_permissions():
    user = AuthUser(
        id=str(ObjectId()),
        email="manager@example.test",
        role="hr_manager",
        permissions=ROLE_PERMISSIONS["hr_manager"],
    )

    assert has_permission(None, "employees:write") is False
    assert has_permission(user, "employees:write") is True
    assert has_permission(user, "stock:adjust") is False
