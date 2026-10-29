"""DRF authentication backed by the current MongoDB user record."""

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Iterator

import jwt
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.request import Request

from common.permissions_matrix import ROLE_PERMISSIONS


@dataclass(frozen=True)
class AuthUser:
    """Small request identity that contains no MongoDB document secrets."""

    id: str
    email: str
    role: str
    permissions: frozenset[str]

    @property
    def is_authenticated(self) -> bool:
        """Report that this user passed JWT and database validation."""
        return True

    @property
    def is_anonymous(self) -> bool:
        """Report that this identity is not anonymous."""
        return False

    @property
    def pk(self) -> str:
        """Provide the conventional primary-key alias used by integrations."""
        return self.id


@contextmanager
def _mongo_database() -> Iterator[Any]:
    """Open the configured MongoDB database for a single authentication lookup."""
    mongo_uri = getattr(settings, "MONGO_URI", "")
    database_name = getattr(settings, "MONGO_DB_NAME", "")
    if not mongo_uri:
        raise ImproperlyConfigured("MONGO_URI is not configured.")
    if not database_name:
        raise ImproperlyConfigured("MONGO_DB_NAME is not configured.")

    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        yield client[database_name]


class MongoJWTAuthentication(BaseAuthentication):
    """Authenticate bearer JWTs and confirm their user state from MongoDB."""

    def authenticate(
        self,
        request: Request,
    ) -> tuple[AuthUser, dict[str, Any]] | None:
        """Validate a bearer token and return its current MongoDB user identity."""
        header = get_authorization_header(request).split()
        if not header:
            return None
        if header[0].lower() != b"bearer":
            return None
        if len(header) != 2:
            raise AuthenticationFailed("Invalid access token.")

        try:
            from accounts.tokens import decode_access_token

            payload = decode_access_token(header[1].decode("utf-8"))
        except (UnicodeDecodeError, jwt.PyJWTError) as exc:
            raise AuthenticationFailed("Invalid or expired access token.") from exc

        from accounts.repository import find_user_by_id

        with _mongo_database() as database:
            user = find_user_by_id(database, payload["sub"])

        if (
            user is None
            or user.get("is_active") is not True
            or user.get("token_version") != payload.get("token_version")
        ):
            raise AuthenticationFailed("Invalid or expired access token.")

        role = user.get("role")
        if not isinstance(role, str):
            raise AuthenticationFailed("Invalid or expired access token.")

        auth_user = AuthUser(
            id=str(user["_id"]),
            email=user["email"],
            role=role,
            permissions=ROLE_PERMISSIONS.get(role, frozenset()),
        )
        return auth_user, payload

    def authenticate_header(self, request: Request) -> str:
        """Tell DRF to use HTTP 401 responses with a Bearer challenge."""
        return "Bearer"
