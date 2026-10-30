"""Backend response and CORS contract tests for the frontend auth flow."""

from django.conf import settings
from django.test import Client, override_settings

from accounts.views import _auth_user_payload
from common.permissions_matrix import ROLE_PERMISSIONS


def test_auth_user_payload_includes_permissions_from_role_matrix():
    payload = _auth_user_payload(
        {
            "_id": "test-user-id",
            "email": "hr@example.test",
            "role": "hr_manager",
            "is_active": True,
            "password_hash": "never-return-this",
        }
    )

    assert payload["permissions"] == sorted(ROLE_PERMISSIONS["hr_manager"])
    assert "password_hash" not in payload


def test_cors_preflight_allows_exact_origin_credentials_and_custom_headers():
    origin = "http://localhost:5173"
    requested_headers = (
        "authorization,content-type,x-requested-with,idempotency-key"
    )
    with override_settings(CORS_ALLOWED_ORIGINS=[origin]):
        response = Client().options(
            "/api/auth/refresh/",
            HTTP_ORIGIN=origin,
            HTTP_ACCESS_CONTROL_REQUEST_METHOD="POST",
            HTTP_ACCESS_CONTROL_REQUEST_HEADERS=requested_headers,
        )

    assert response.status_code == 200
    assert response["Access-Control-Allow-Origin"] == origin
    assert response["Access-Control-Allow-Credentials"] == "true"
    allowed_headers = response["Access-Control-Allow-Headers"].lower()
    assert "authorization" in allowed_headers
    assert "content-type" in allowed_headers
    assert "x-requested-with" in allowed_headers
    assert "idempotency-key" in allowed_headers
    assert settings.CORS_ALLOW_CREDENTIALS is True
    assert "*" not in settings.CORS_ALLOWED_ORIGINS
