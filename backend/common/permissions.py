"""Reusable DRF permissions backed by the centralized role matrix."""

from typing import Any

from rest_framework.permissions import BasePermission


class IsAuthenticatedMongo(BasePermission):
    """Allow only request identities supplied by MongoJWTAuthentication."""

    message = "Authentication is required."

    def has_permission(self, request: Any, view: Any) -> bool:
        """Handle the configured ``UNAUTHENTICATED_USER = None`` safely."""
        user = getattr(request, "user", None)
        return user is not None and getattr(user, "is_authenticated", False) is True


def has_permission(user: object | None, perm: str) -> bool:
    """Return whether an authenticated request identity has a named permission."""
    if user is None or getattr(user, "is_authenticated", False) is not True:
        return False
    permissions = getattr(user, "permissions", ())
    return perm in permissions


def require(perm: str) -> type[BasePermission]:
    """Create a DRF permission class that requires one named capability."""
    if not isinstance(perm, str) or not perm.strip():
        raise ValueError("Permission name must be a non-empty string.")

    def check_permission(self, request: Any, view: Any) -> bool:
        """Check the current request user's permissions."""
        return has_permission(getattr(request, "user", None), perm)

    class HasPermission(BasePermission):
        """Permission class generated for one capability."""

        message = f"The '{perm}' permission is required."
        has_permission = check_permission

    HasPermission.__name__ = "HasPermission"
    HasPermission.__qualname__ = "HasPermission"
    return HasPermission
