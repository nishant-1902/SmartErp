"""JSON auth endpoints for login, refresh, logout, and profile operations."""

from contextlib import contextmanager
from typing import Any

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.decorators import api_view, authentication_classes, permission_classes

from common.permissions import IsAuthenticatedMongo, require
from common.permissions_matrix import ROLE_PERMISSIONS
from accounts.passwords import hash_password, validate_password_strength, verify_password
from accounts.repository import (
    find_refresh_token_by_hash,
    find_user_by_email,
    find_user_by_id,
    update_user,
)
from accounts.serializers import (
    AuditLogQuerySerializer,
    ChangePasswordSerializer,
    EmptyActionSerializer,
    EmailPasswordSerializer,
    PasswordResetConfirmSerializer,
    PasswordResetRequestSerializer,
    UserCreateSerializer,
    UserListQuerySerializer,
    UserPatchSerializer,
)
from accounts.services import (
    InvalidRefreshToken,
    RefreshRace,
    check_login_lockout,
    confirm_password_reset,
    create_refresh_token,
    activate_managed_user,
    create_managed_user,
    deactivate_managed_user,
    get_public_user,
    get_managed_user,
    hash_refresh_token,
    initiate_admin_password_reset,
    list_managed_audit_logs,
    list_managed_users,
    record_failed_login,
    record_successful_login,
    request_password_reset,
    rotate_refresh_token,
    update_managed_user,
    write_security_audit,
)
from accounts.tokens import create_access_token
from common.responses import error_response, success_response
from common.object_id import parse_object_id
from common.pagination import parse_pagination
from common.time import utc_now


@contextmanager
def mongo_database():
    """Open a MongoDB client and yield a database for request-scoped access."""
    mongo_uri = getattr(settings, "MONGO_URI", "")
    database_name = getattr(settings, "MONGO_DB_NAME", "")
    if not mongo_uri:
        raise ImproperlyConfigured("MONGO_URI is not configured.")
    if not database_name:
        raise ImproperlyConfigured("MONGO_DB_NAME is not configured.")
    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        yield client[database_name]


def get_client_ip(request: Any) -> str:
    """Return the best available client IP address for audit and rate-limit records."""
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unknown")


def get_user_agent(request: Any) -> str | None:
    """Return the User-Agent header if present."""
    return request.META.get("HTTP_USER_AGENT") or None


def _auth_user_payload(user: dict[str, Any]) -> dict[str, Any]:
    """Include the role's current capability list in authentication responses."""
    public_user = get_public_user(user)
    public_user["permissions"] = sorted(
        ROLE_PERMISSIONS.get(public_user.get("role"), frozenset())
    )
    return public_user


def build_login_response(data: dict[str, Any], *, refresh_token: str | None = None) -> Any:
    """Create a JSON response that optionally sets the refresh-token cookie."""
    response = success_response(data)
    if refresh_token:
        response.set_cookie(
            key=settings.REFRESH_COOKIE_NAME,
            value=refresh_token,
            max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
            httponly=settings.REFRESH_COOKIE_HTTPONLY,
            secure=settings.REFRESH_COOKIE_SECURE,
            samesite=settings.REFRESH_COOKIE_SAMESITE,
            path=settings.REFRESH_COOKIE_PATH,
            domain=settings.REFRESH_COOKIE_DOMAIN,
        )
    return response


def _authenticated_user_document(request: Any) -> dict[str, Any]:
    """Load the authenticated user's current profile document through the repository."""
    with mongo_database() as database:
        user = find_user_by_id(database, request.user.id)
    if user is None:
        raise ValueError("Authentication required.")
    return user


def _guard_csrf(request: Any) -> bool:
    """Require the custom X-Requested-With header for cookie-based refresh and logout."""
    return request.headers.get("X-Requested-With") == "XMLHttpRequest"


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def login_view(request):
    """Authenticate a user and issue a short-lived access token plus refresh cookie."""
    serializer = EmailPasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]
    client_ip = get_client_ip(request)
    user_agent = get_user_agent(request)
    now = utc_now()

    with mongo_database() as database:
        locked, retry_after = check_login_lockout(database, email, client_ip)
        if locked:
            return error_response(
                "rate_limited",
                "Too many failed login attempts. Please try again later.",
                details={"retry_after": retry_after},
                status=429,
                headers={"Retry-After": str(retry_after)},
            )

        user = find_user_by_email(database, email)
        if user is None:
            dummy_hash = hash_password("dummy-password-for-rate-similarity-123456")
            verify_password(password, dummy_hash)
            record_failed_login(
                database,
                email=email,
                client_ip=client_ip,
                user=None,
                ip=client_ip,
                user_agent=user_agent,
                now=now,
            )
            return error_response(
                "invalid_credentials",
                "Invalid email or password",
                status=401,
            )

        if user.get("is_active") is not True:
            record_failed_login(
                database,
                email=email,
                client_ip=client_ip,
                user=user,
                ip=client_ip,
                user_agent=user_agent,
                now=now,
            )
            return error_response(
                "invalid_credentials",
                "Invalid email or password",
                status=401,
            )

        if not verify_password(password, user.get("password_hash", "")):
            record_failed_login(
                database,
                email=email,
                client_ip=client_ip,
                user=user,
                ip=client_ip,
                user_agent=user_agent,
                now=now,
            )
            return error_response(
                "invalid_credentials",
                "Invalid email or password",
                status=401,
            )

        user["last_login_at"] = now
        database["users"].update_one(
            {"_id": user["_id"]},
            {"$set": {"last_login_at": now, "updated_at": now}},
        )
        access_token = create_access_token(user)
        refresh_token = create_refresh_token(
            database,
            user["_id"],
            user_agent=user_agent,
            ip=client_ip,
            family_id=__import__('secrets').token_urlsafe(16),
            now=now,
        )
        record_successful_login(database, user=user, ip=client_ip, user_agent=user_agent, now=now)
        response = build_login_response(
            {
                "access_token": access_token,
                "token_type": "Bearer",
                "user": _auth_user_payload(user),
            },
            refresh_token=refresh_token,
        )
        return response


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def refresh_view(request):
    """Rotate a refresh token and return a new access token plus replacement cookie."""
    if not _guard_csrf(request):
        return error_response(
            "csrf_required",
            "Missing X-Requested-With header for refresh.",
            status=403,
        )

    raw_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    if not raw_token:
        return error_response(
            "invalid_refresh_token",
            "Refresh token is invalid or expired.",
            status=401,
        )

    with mongo_database() as database:
        try:
            record = find_refresh_token_by_hash(database, hash_refresh_token(raw_token))
            if record is None:
                raise InvalidRefreshToken("Refresh token is invalid or expired.")
            user = find_user_by_id(database, record["user_id"])
            if user is None or user.get("is_active") is not True:
                raise InvalidRefreshToken("Refresh token is invalid or expired.")
            new_refresh = rotate_refresh_token(
                database,
                raw_token,
                user_agent=get_user_agent(request),
                ip=get_client_ip(request),
                now=utc_now(),
            )
            access_token = create_access_token(user)
            response = success_response({
                "access_token": access_token,
                "token_type": "Bearer",
                "user": _auth_user_payload(user),
            })
            response.set_cookie(
                key=settings.REFRESH_COOKIE_NAME,
                value=new_refresh,
                max_age=settings.JWT_REFRESH_TOKEN_LIFETIME_SECONDS,
                httponly=settings.REFRESH_COOKIE_HTTPONLY,
                secure=settings.REFRESH_COOKIE_SECURE,
                samesite=settings.REFRESH_COOKIE_SAMESITE,
                path=settings.REFRESH_COOKIE_PATH,
                domain=settings.REFRESH_COOKIE_DOMAIN,
            )
            return response
        except RefreshRace as exc:
            return error_response(exc.default_code, exc.default_detail, status=exc.status_code)
        except InvalidRefreshToken as exc:
            return error_response(
                exc.default_code or "invalid_refresh_token",
                exc.default_detail,
                status=exc.status_code,
            )


@api_view(["POST"])
def logout_view(request):
    """Clear the current refresh cookie and revoke the token family."""
    if not _guard_csrf(request):
        return error_response(
            "csrf_required",
            "Missing X-Requested-With header for logout.",
            status=403,
        )

    raw_token = request.COOKIES.get(settings.REFRESH_COOKIE_NAME)
    user = None
    with mongo_database() as database:
        if raw_token:
            record = find_refresh_token_by_hash(database, hash_refresh_token(raw_token))
            if record is not None:
                user = find_user_by_id(database, record["user_id"])
                database["refresh_tokens"].update_many(
                    {"family_id": record["family_id"]},
                    {"$set": {"status": "revoked", "revoked_at": utc_now()}},
                )
                write_security_audit(
                    database,
                    actor_id=user.get("_id") if user else None,
                    action="logout",
                    resource="user",
                    resource_id=user.get("_id") if user else None,
                    outcome="success",
                    ip=get_client_ip(request),
                    user_agent=get_user_agent(request),
                    now=utc_now(),
                )
    response = success_response({"logged_out": True})
    response.delete_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        path=settings.REFRESH_COOKIE_PATH,
        domain=settings.REFRESH_COOKIE_DOMAIN,
        samesite=settings.REFRESH_COOKIE_SAMESITE,
    )
    return response


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo, require("own-profile:read")])
def me_view(request):
    """Return the current authenticated user profile."""
    try:
        user = _authenticated_user_document(request)
    except ValueError:
        return error_response("authentication_required", "Authentication required.", status=401)
    return success_response({"user": _auth_user_payload(user)})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo, require("own-password:change")])
def change_password_view(request):
    """Require the current password, then replace it and revoke all refresh sessions."""
    serializer = ChangePasswordSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )

    try:
        user = _authenticated_user_document(request)
    except ValueError:
        return error_response("authentication_required", "Authentication required.", status=401)

    old_password = serializer.validated_data["old_password"]
    new_password = serializer.validated_data["new_password"]
    if not verify_password(old_password, user.get("password_hash", "")):
        return error_response("invalid_credentials", "Invalid email or password", status=401)

    try:
        validate_password_strength(new_password, user.get("email", ""))
    except Exception as exc:
        return error_response("validation_error", str(exc), status=400)

    with mongo_database() as database:
        update_user(database, user["_id"], {"password_hash": hash_password(new_password)})
        database["refresh_tokens"].update_many(
            {"user_id": user["_id"]},
            {"$set": {"status": "revoked", "revoked_at": utc_now()}},
        )
        write_security_audit(
            database,
            actor_id=user.get("_id"),
            action="password_changed",
            resource="user",
            resource_id=user.get("_id"),
            outcome="success",
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            now=utc_now(),
        )
    return success_response({"message": "Password changed successfully."})


@api_view(["POST"])
def password_reset_request_view(request):
    """Request a password reset for an email address; the link is printed in development."""
    serializer = PasswordResetRequestSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )

    email = serializer.validated_data["email"]
    with mongo_database() as database:
        request_password_reset(
            database,
            email=email,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
            now=utc_now(),
        )
    return success_response({
        "message": "If an account matches this email, a password reset link has been generated."
    })


@api_view(["POST"])
@authentication_classes([])
@permission_classes([])
def password_reset_confirm_view(request):
    """Confirm a single-use password-reset token and replace the password."""
    serializer = PasswordResetConfirmSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )

    email = serializer.validated_data["email"]
    token = serializer.validated_data["token"]
    password = serializer.validated_data["password"]
    try:
        with mongo_database() as database:
            confirm_password_reset(
                database,
                email=email,
                raw_token=token,
                new_password=password,
                ip=get_client_ip(request),
                user_agent=get_user_agent(request),
                now=utc_now(),
            )
        return success_response({"message": "Password reset complete."})
    except InvalidRefreshToken as exc:
        return error_response(
            exc.default_code or "invalid_reset_token",
            exc.default_detail,
            status=exc.status_code,
        )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo, require("users:manage")])
def users_list_create_view(request):
    """List users or create a new account for an administrator."""
    with mongo_database() as database:
        if request.method == "GET":
            serializer = UserListQuerySerializer(data=request.query_params)
            if not serializer.is_valid():
                return error_response(
                    "validation_error",
                    "Request validation failed.",
                    details=serializer.errors,
                    status=400,
                )
            filters = serializer.validated_data
            pagination = parse_pagination(
                filters["page"],
                filters["page_size"],
            )
            users, meta = list_managed_users(
                database,
                search=filters.get("search"),
                role=filters.get("role"),
                is_active=filters.get("is_active"),
                pagination=pagination,
                actor_id=request.user.id,
                ip=get_client_ip(request),
                user_agent=get_user_agent(request),
            )
            return success_response({"users": users}, meta=meta)

        serializer = UserCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "validation_error",
                "Request validation failed.",
                details=serializer.errors,
                status=400,
            )
        user = create_managed_user(
            database,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
            full_name=serializer.validated_data["full_name"],
            role=serializer.validated_data["role"],
            employee_id=serializer.validated_data.get("employee_id"),
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return success_response({"user": user}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo, require("users:manage")])
def user_detail_view(request, user_id: str):
    """Read or edit one managed user account."""
    parsed_user_id = parse_object_id(user_id)
    with mongo_database() as database:
        if request.method == "GET":
            return success_response(
                {
                    "user": get_managed_user(
                        database,
                        parsed_user_id,
                        actor_id=request.user.id,
                        ip=get_client_ip(request),
                        user_agent=get_user_agent(request),
                    )
                }
            )

        serializer = UserPatchSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response(
                "validation_error",
                "Request validation failed.",
                details=serializer.errors,
                status=400,
            )
        user = update_managed_user(
            database,
            parsed_user_id,
            serializer.validated_data,
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
        return success_response({"user": user})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo, require("users:manage")])
def user_activate_view(request, user_id: str):
    """Activate a managed user account."""
    serializer = EmptyActionSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )
    with mongo_database() as database:
        user = activate_managed_user(
            database,
            parse_object_id(user_id),
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    return success_response({"user": user})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo, require("users:manage")])
def user_deactivate_view(request, user_id: str):
    """Deactivate a managed user account and revoke its refresh tokens."""
    serializer = EmptyActionSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )
    with mongo_database() as database:
        user = deactivate_managed_user(
            database,
            parse_object_id(user_id),
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    return success_response({"user": user})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo, require("users:manage")])
def user_reset_password_view(request, user_id: str):
    """Start the single-use password-reset flow for a managed user."""
    serializer = EmptyActionSerializer(data=request.data)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )
    with mongo_database() as database:
        initiate_admin_password_reset(
            database,
            parse_object_id(user_id),
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    return success_response(
        {"message": "A password reset link has been generated."}
    )


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo, require("audit:read")])
def audit_logs_list_view(request):
    """List audit records for authorized users with filters and pagination."""
    serializer = AuditLogQuerySerializer(data=request.query_params)
    if not serializer.is_valid():
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=serializer.errors,
            status=400,
        )
    filters = serializer.validated_data
    pagination = parse_pagination(
        filters["page"],
        filters["page_size"],
    )
    with mongo_database() as database:
        records, meta = list_managed_audit_logs(
            database,
            user_id=filters.get("user"),
            action=filters.get("action"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            pagination=pagination,
            actor_id=request.user.id,
            ip=get_client_ip(request),
            user_agent=get_user_agent(request),
        )
    return success_response({"audit_logs": records}, meta=meta)
