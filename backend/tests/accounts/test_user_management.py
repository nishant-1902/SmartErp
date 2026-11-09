from datetime import timedelta
import logging
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from bson import ObjectId
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from rest_framework.test import APIClient

from accounts.passwords import hash_password, verify_password
from accounts.repository import count_users, find_refresh_token_by_hash
from accounts.services import (
    deactivate_managed_user,
    hash_refresh_token,
    initiate_admin_password_reset,
)
from accounts.tokens import create_access_token, decode_access_token
from common.exceptions import ConflictError
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase

JWT_SECRET = "user-management-test-secret-key-at-least-32-bytes"


@pytest.fixture
def management_api(monkeypatch):
    """Configure API auth and route database connections to an isolated fake."""
    database = FakeDatabase()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", JWT_SECRET)
    monkeypatch.setattr(settings, "JWT_ISSUER", "user-management-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "user-management-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")
    monkeypatch.setattr(settings, "DEBUG", True)

    class FakeMongoClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def __getitem__(self, database_name):
            assert database_name == "smarterp_test"
            return database

    factory = lambda *args, **kwargs: FakeMongoClient()
    monkeypatch.setattr("accounts.authentication.MongoClient", factory)
    monkeypatch.setattr("accounts.views.MongoClient", factory)
    return database


@pytest.fixture
def client():
    return APIClient()


def insert_user(database, role, **overrides):
    now = utc_now()
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": hash_password("ExistingSafePass887!"),
        "full_name": "Test Account",
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    user.update(overrides)
    database["users"].insert_one(user)
    return user


def headers_for(user):
    token = create_access_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def test_non_admin_cannot_list_or_escalate_user_role(
    client,
    management_api,
):
    employee = insert_user(management_api, "employee")
    target = insert_user(management_api, "employee")

    list_response = client.get(
        "/api/users/",
        **headers_for(employee),
    )
    patch_response = client.patch(
        f"/api/users/{target['_id']}/",
        {"role": "super_admin"},
        format="json",
        **headers_for(employee),
    )

    assert list_response.status_code == 403
    assert patch_response.status_code == 403
    assert management_api["users"].find_one({"_id": target["_id"]})["role"] == "employee"


def test_login_verifies_password_and_issues_access_and_hashed_refresh_tokens(
    client,
    management_api,
):
    user = insert_user(management_api, "employee")

    wrong_password = client.post(
        "/api/auth/login/",
        {"email": user["email"], "password": "WrongPassword887!"},
        format="json",
    )
    login = client.post(
        "/api/auth/login/",
        {"email": user["email"], "password": "ExistingSafePass887!"},
        format="json",
        HTTP_USER_AGENT="pytest",
    )

    assert wrong_password.status_code == 401
    assert wrong_password.json()["success"] is False
    assert wrong_password.json()["error"]["code"] == "invalid_credentials"
    assert "email" not in wrong_password.json()["error"]["details"]
    assert login.status_code == 200
    assert login.json()["success"] is True
    access_token = login.json()["data"]["access_token"]
    assert decode_access_token(access_token)["sub"] == str(user["_id"])

    refresh_cookie = login.cookies[settings.REFRESH_COOKIE_NAME]
    assert refresh_cookie["httponly"] is True
    assert refresh_cookie.value
    refresh_record = find_refresh_token_by_hash(
        management_api,
        hash_refresh_token(refresh_cookie.value),
    )
    assert refresh_record is not None
    assert refresh_record["status"] == "active"
    assert refresh_cookie.value not in refresh_record.values()


def test_login_response_serializes_employee_object_id_and_timestamps(
    client,
    management_api,
):
    employee_id = ObjectId()
    user = insert_user(
        management_api,
        "employee",
        employee_id=employee_id,
    )

    response = client.post(
        "/api/auth/login/",
        {"email": user["email"], "password": "ExistingSafePass887!"},
        format="json",
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["success"] is True
    response_user = payload["data"]["user"]
    assert response_user["employee_id"] == str(employee_id)
    assert response_user["id"] == str(user["_id"])
    assert isinstance(response_user["created_at"], str)
    assert isinstance(response_user["last_login_at"], str)


def test_logout_revokes_refresh_and_following_refresh_returns_401(
    client,
    management_api,
):
    user = insert_user(management_api, "employee")
    login = client.post(
        "/api/auth/login/",
        {"email": user["email"], "password": "ExistingSafePass887!"},
        format="json",
    )
    access_token = login.json()["data"]["access_token"]
    refresh_cookie_name = settings.REFRESH_COOKIE_NAME
    assert client.cookies.get(refresh_cookie_name) is not None

    logout = client.post(
        "/api/auth/logout/",
        {},
        format="json",
        HTTP_AUTHORIZATION=f"Bearer {access_token}",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )
    refresh = client.post(
        "/api/auth/refresh/",
        {},
        format="json",
        HTTP_X_REQUESTED_WITH="XMLHttpRequest",
    )

    assert logout.status_code == 200
    assert logout.json()["success"] is True
    assert refresh.status_code == 401
    assert refresh.json()["success"] is False
    assert refresh.json()["error"]["code"] == "invalid_refresh_token"


def test_admin_can_create_search_and_read_user_without_hashes(
    client,
    management_api,
):
    admin = insert_user(management_api, "super_admin")
    created = client.post(
        "/api/users/",
        {
            "email": "new.person@example.test",
            "password": "UniqueBluePassword771!",
            "full_name": "New Person",
            "role": "employee",
        },
        format="json",
        **headers_for(admin),
    )

    assert created.status_code == 201
    created_user = created.json()["data"]["user"]
    assert created_user["email"] == "new.person@example.test"
    assert "password_hash" not in created_user
    assert "password_reset_token_hash" not in created_user
    assert management_api["audit_logs"].count_documents(
        {"action": "user_created"}
    ) == 1

    listing = client.get(
        "/api/users/?search=NEW.PERSON&role=employee&is_active=true&page=1&page_size=5",
        **headers_for(admin),
    )

    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1
    assert listing.json()["data"]["users"][0]["email"] == "new.person@example.test"
    assert "password_hash" not in listing.json()["data"]["users"][0]
    assert management_api["audit_logs"].find_one(
        {"action": "users_listed", "outcome": "success"}
    ) is not None

    detail = client.get(
        f"/api/users/{created_user['id']}/",
        **headers_for(admin),
    )
    assert detail.status_code == 200
    assert "password_hash" not in detail.json()["data"]["user"]
    assert management_api["audit_logs"].find_one(
        {"action": "user_read", "outcome": "success"}
    ) is not None

    patched = client.patch(
        f"/api/users/{created_user['id']}/",
        {"full_name": "Updated Person"},
        format="json",
        **headers_for(admin),
    )
    assert patched.status_code == 200
    assert patched.json()["data"]["user"]["full_name"] == "Updated Person"
    assert "password_hash" not in patched.json()["data"]["user"]
    assert management_api["audit_logs"].count_documents(
        {"action": "user_updated", "outcome": "success"}
    ) == 1


def test_user_list_rejects_unknown_and_invalid_filters(client, management_api):
    admin = insert_user(management_api, "super_admin")

    unknown_filter = client.get(
        "/api/users/?$where=malicious",
        **headers_for(admin),
    )
    invalid_role = client.get(
        "/api/users/?role=unknown",
        **headers_for(admin),
    )

    assert unknown_filter.status_code == 400
    assert invalid_role.status_code == 400


def test_admin_cannot_mass_assign_privileged_or_secret_fields(
    client,
    management_api,
):
    admin = insert_user(management_api, "super_admin")
    target = insert_user(management_api, "employee")

    secret_update = client.patch(
        f"/api/users/{target['_id']}/",
        {"password_hash": "attacker-controlled"},
        format="json",
        **headers_for(admin),
    )
    active_update = client.patch(
        f"/api/users/{target['_id']}/",
        {"is_active": False},
        format="json",
        **headers_for(admin),
    )
    operator_update = client.patch(
        f"/api/users/{target['_id']}/",
        {"$set": {"role": "super_admin"}},
        format="json",
        **headers_for(admin),
    )

    assert secret_update.status_code == 400
    assert active_update.status_code == 400
    assert operator_update.status_code == 400
    unchanged = management_api["users"].find_one({"_id": target["_id"]})
    assert unchanged["password_hash"] != "attacker-controlled"
    assert unchanged["is_active"] is True
    assert unchanged["role"] == "employee"


def test_user_list_searches_name_and_paginates(client, management_api):
    admin = insert_user(management_api, "super_admin")
    insert_user(
        management_api,
        "employee",
        full_name="Alex Example",
        email="alex@example.test",
    )
    insert_user(
        management_api,
        "employee",
        full_name="Alex Other",
        email="other@example.test",
    )
    insert_user(
        management_api,
        "employee",
        full_name="Morgan Person",
        email="morgan@example.test",
    )
    assert management_api["users"].count_documents(
        {"full_name": {"$regex": "alex", "$options": "i"}}
    ) == 2
    assert count_users(
        management_api,
        search="alex",
        role=None,
        is_active=None,
    ) == 2
    first_page = client.get(
        "/api/users/?search=alex&page=1&page_size=1",
        **headers_for(admin),
    )
    second_page = client.get(
        "/api/users/?search=alex&page=2&page_size=1",
        **headers_for(admin),
    )

    assert first_page.status_code == 200, first_page.json()
    assert first_page.json()["meta"]["total"] == 2
    assert first_page.json()["meta"]["total_pages"] == 2
    assert second_page.status_code == 200
    assert first_page.json()["data"]["users"][0]["id"] != (
        second_page.json()["data"]["users"][0]["id"]
    )


def test_last_active_super_admin_cannot_be_demoted(client, management_api):
    admin = insert_user(management_api, "super_admin")

    response = client.patch(
        f"/api/users/{admin['_id']}/",
        {"role": "hr_manager"},
        format="json",
        **headers_for(admin),
    )

    assert response.status_code == 409
    assert management_api["users"].find_one({"_id": admin["_id"]})["role"] == "super_admin"
    assert management_api["audit_logs"].find_one(
        {"action": "user_updated", "outcome": "denied"}
    ) is not None


def test_last_active_super_admin_cannot_be_deactivated(management_api):
    admin = insert_user(management_api, "super_admin")

    with pytest.raises(ConflictError):
        deactivate_managed_user(
            management_api,
            admin["_id"],
            actor_id=ObjectId(),
            ip="127.0.0.1",
            user_agent="pytest",
        )

    assert management_api["users"].find_one({"_id": admin["_id"]})["is_active"] is True
    assert management_api["audit_logs"].find_one(
        {"action": "user_deactivated", "outcome": "denied"}
    ) is not None


def test_cannot_deactivate_self(client, management_api):
    admin = insert_user(management_api, "super_admin")

    response = client.post(
        f"/api/users/{admin['_id']}/deactivate/",
        {},
        format="json",
        **headers_for(admin),
    )

    assert response.status_code == 409
    assert management_api["users"].find_one({"_id": admin["_id"]})["is_active"] is True
    assert management_api["audit_logs"].find_one(
        {"action": "user_deactivated", "outcome": "denied"}
    ) is not None


def test_deactivation_invalidates_access_and_revokes_refresh_tokens(
    client,
    management_api,
):
    admin = insert_user(management_api, "super_admin")
    target = insert_user(management_api, "employee")
    token_record = {
        "_id": ObjectId(),
        "user_id": target["_id"],
        "token_hash": "hashed-refresh",
        "family_id": "family-id",
        "status": "active",
        "created_at": utc_now(),
        "expires_at": utc_now() + timedelta(days=1),
        "revoked_at": None,
        "replaced_by": None,
        "user_agent": None,
        "ip": None,
    }
    management_api["refresh_tokens"].insert_one(token_record)

    response = client.post(
        f"/api/users/{target['_id']}/deactivate/",
        {},
        format="json",
        **headers_for(admin),
    )

    assert response.status_code == 200
    updated = management_api["users"].find_one({"_id": target["_id"]})
    assert updated["is_active"] is False
    assert updated["token_version"] == 1
    assert management_api["refresh_tokens"].find_one(
        {"_id": token_record["_id"]}
    )["status"] == "revoked"
    assert management_api["audit_logs"].find_one(
        {"action": "user_deactivated", "outcome": "success"}
    ) is not None


def test_activate_and_admin_reset_password_are_audited(
    client,
    management_api,
    caplog,
):
    caplog.set_level(logging.INFO, logger="accounts.services")
    admin = insert_user(management_api, "super_admin")
    target = insert_user(
        management_api,
        "employee",
        is_active=False,
        password_reset_token_hash=None,
        password_reset_expires_at=None,
    )

    activate = client.post(
        f"/api/users/{target['_id']}/activate/",
        {},
        format="json",
        **headers_for(admin),
    )
    reset = client.post(
        f"/api/users/{target['_id']}/reset-password/",
        {},
        format="json",
        **headers_for(admin),
    )

    assert activate.status_code == 200
    assert activate.json()["data"]["user"]["is_active"] is True
    assert reset.status_code == 200
    assert "token" not in reset.json()["data"]
    assert "Development password reset link:" in caplog.text
    reset_link = caplog.text.split("Development password reset link:", 1)[1].strip()
    reset_query = parse_qs(urlsplit(reset_link).query)
    reset_user = management_api["users"].find_one({"_id": target["_id"]})
    assert reset_user["password_reset_token_hash"]
    assert reset_user["password_reset_token_hash"] not in caplog.text
    assert management_api["audit_logs"].find_one(
        {"action": "user_activated", "outcome": "success"}
    ) is not None
    assert management_api["audit_logs"].find_one(
        {"action": "admin_password_reset_requested", "outcome": "success"}
    ) is not None

    confirm_payload = {
        "email": target["email"],
        "token": reset_query["token"][0],
        "password": "NewDistinctPassword880!",
        "confirm_password": "NewDistinctPassword880!",
    }
    confirmation = client.post(
        "/api/auth/password-reset/confirm/",
        confirm_payload,
        format="json",
    )
    replay = client.post(
        "/api/auth/password-reset/confirm/",
        confirm_payload,
        format="json",
    )

    assert confirmation.status_code == 200
    assert replay.status_code == 401
    reset_user = management_api["users"].find_one({"_id": target["_id"]})
    assert reset_user["password_reset_token_hash"] is None
    assert reset_user["token_version"] == 1
    assert verify_password("NewDistinctPassword880!", reset_user["password_hash"])


def test_admin_reset_refuses_to_print_reset_links_outside_development(
    management_api,
    monkeypatch,
):
    admin = insert_user(management_api, "super_admin")
    target = insert_user(management_api, "employee")
    monkeypatch.setattr(settings, "DEBUG", False)

    with pytest.raises(ImproperlyConfigured):
        initiate_admin_password_reset(
            management_api,
            target["_id"],
            actor_id=admin["_id"],
            ip="127.0.0.1",
            user_agent="pytest",
        )

    assert "password_reset_token_hash" not in management_api["users"].find_one(
        {"_id": target["_id"]}
    )
    assert management_api["audit_logs"].count_documents({}) == 0


def test_audit_logs_require_permission_and_support_filters(client, management_api):
    admin = insert_user(management_api, "super_admin")
    employee = insert_user(management_api, "employee")
    now = utc_now()
    management_api["audit_logs"].insert_one(
        {
            "actor_id": admin["_id"],
            "action": "user_created",
            "entity_type": "user",
            "entity_id": str(employee["_id"]),
            "before": None,
            "after": None,
            "request_id": None,
            "created_at": now,
            "outcome": "success",
            "ip": "127.0.0.1",
            "user_agent": "pytest",
        }
    )
    management_api["audit_logs"].insert_one(
        {
            "actor_id": admin["_id"],
            "action": "user_updated",
            "entity_type": "user",
            "entity_id": str(employee["_id"]),
            "before": None,
            "after": None,
            "request_id": None,
            "created_at": now - timedelta(days=2),
            "outcome": "success",
            "ip": "127.0.0.1",
            "user_agent": "pytest",
        }
    )

    denied = client.get(
        "/api/audit-logs/",
        **headers_for(employee),
    )
    filtered = client.get(
        "/api/audit-logs/"
        f"?user={employee['_id']}&action=user_created"
        f"&start_date={(now - timedelta(hours=1)).isoformat().replace('+00:00', 'Z')}"
        f"&end_date={(now + timedelta(hours=1)).isoformat().replace('+00:00', 'Z')}",
        **headers_for(admin),
    )

    assert denied.status_code == 403
    assert filtered.status_code == 200, filtered.json()
    result = filtered.json()
    assert result["meta"]["total"] == 1
    assert result["data"]["audit_logs"][0]["action"] == "user_created"
    assert result["data"]["audit_logs"][0]["actor_id"] == str(admin["_id"])
    assert management_api["audit_logs"].find_one(
        {"action": "audit_logs_read", "outcome": "success"}
    ) is not None


def test_invalid_user_id_returns_400(client, management_api):
    admin = insert_user(management_api, "super_admin")

    response = client.get(
        "/api/users/not-an-object-id/",
        **headers_for(admin),
    )

    assert response.status_code == 400
