"""Root URL configuration for the SmartERP API."""

from django.http import HttpRequest, JsonResponse
from django.urls import include, path

from common.views import health_check


def api_root_not_found(request: HttpRequest) -> JsonResponse:
    """Return a safe JSON 404 until API routes are added."""
    return JsonResponse(
        {
            "success": False,
            "error": {
                "code": "NOT_FOUND",
                "message": "The requested endpoint was not found.",
                "details": {},
            },
        },
        status=404,
    )


urlpatterns = [
    path("api/health/", health_check, name="health"),
    path("api/auth/", include("accounts.urls")),
    path("api/users/", include("accounts.user_urls")),
    path("api/audit-logs/", include("accounts.audit_urls")),
    path("api/departments/", include("departments.urls")),
    path("api/employees/", include("employees.urls")),
    path("api/products/", include("inventory.urls")),
    path("api/stock-adjustments/", include("inventory.stock_urls")),
    path("api/stock-movements/", include("inventory.movement_urls")),
    path("", api_root_not_found, name="api-root-not-found"),
]
