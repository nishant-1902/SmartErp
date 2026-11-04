"""Permission-checked reports API views."""

from contextlib import contextmanager
from typing import Any, Generator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.decorators import api_view, permission_classes

from common.pagination import Pagination, parse_pagination
from common.permissions import IsAuthenticatedMongo, has_permission
from common.responses import error_response, success_response
from reports.serializers import ReportQuerySerializer
from reports.services import (
    dashboard_report,
    departments_report,
    employees_report,
    inventory_report,
    low_stock_report,
    monthly_sales_report,
    purchases_report,
    sales_report,
    suppliers_report,
)


@contextmanager
def mongo_database() -> Generator[Any, None, None]:
    """Open a request-scoped connection to the configured MongoDB database."""
    mongo_uri = getattr(settings, "MONGO_URI", "")
    database_name = getattr(settings, "MONGO_DB_NAME", "")
    if not mongo_uri:
        raise ImproperlyConfigured("MONGO_URI is not configured.")
    if not database_name:
        raise ImproperlyConfigured("MONGO_DB_NAME is not configured.")
    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        yield client[database_name]


def _validated_request(data: Any) -> dict[str, Any]:
    """Validate shared report query parameters."""
    serializer = ReportQuerySerializer(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _pagination(filters: dict[str, Any]) -> Pagination:
    """Build pagination only from validated query values."""
    return parse_pagination(filters.get("page"), filters.get("page_size"))


def _permission_denied(permission: str):
    """Return a consistent permission error response."""
    return error_response(
        "permission_denied",
        f"The '{permission}' permission is required.",
        status=403,
    )


def _query_permission(request: Any, permission: str) -> bool:
    """Require general report access and the relevant business-data permission."""
    if not has_permission(request.user, "reports:read"):
        return False
    return has_permission(request.user, permission)


def _report_response(request: Any, permission: str, report: str):
    """Validate query input and execute the selected report service."""
    if not has_permission(request.user, "reports:read"):
        return _permission_denied("reports:read")
    if not has_permission(request.user, permission):
        return _permission_denied(permission)
    filters = _validated_request(request.query_params)
    with mongo_database() as database:
        result = {
            "sales": lambda: sales_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "inventory": lambda: inventory_report(database),
            "low_stock": lambda: low_stock_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "employees": lambda: employees_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "departments": lambda: departments_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "suppliers": lambda: suppliers_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "purchases": lambda: purchases_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
            "monthly_sales": lambda: monthly_sales_report(
                database,
                date_from=filters.get("date_from"),
                date_to=filters.get("date_to"),
                pagination=_pagination(filters),
            ),
        }[report]()
    if isinstance(result, tuple):
        values, meta = result
        return success_response({report: values}, meta=meta)
    return success_response({report: result})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def dashboard_view(request):
    """Return only dashboard widgets allowed by the caller's permissions."""
    if not has_permission(request.user, "reports:read"):
        return _permission_denied("reports:read")
    filters = _validated_request(request.query_params)
    with mongo_database() as database:
        dashboard = dashboard_report(
            database,
            permissions=request.user.permissions,
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
        )
    return success_response({"dashboard": dashboard})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def sales_view(request):
    return _report_response(request, "sales:read", "sales")


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def inventory_view(request):
    if not _query_permission(request, "products:read"):
        return _permission_denied(
            "reports:read"
            if not has_permission(request.user, "reports:read")
            else "products:read"
        )
    if not has_permission(request.user, "stock:read"):
        return _permission_denied("stock:read")
    filters = _validated_request(request.query_params)
    with mongo_database() as database:
        result = inventory_report(database)
    return success_response({"inventory": result})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def low_stock_view(request):
    if not _query_permission(request, "products:read"):
        return _permission_denied(
            "reports:read"
            if not has_permission(request.user, "reports:read")
            else "products:read"
        )
    if not has_permission(request.user, "stock:read"):
        return _permission_denied("stock:read")
    filters = _validated_request(request.query_params)
    pagination = _pagination(filters)
    with mongo_database() as database:
        values, meta = low_stock_report(
            database,
            date_from=filters.get("date_from"),
            date_to=filters.get("date_to"),
            pagination=pagination,
        )
    return success_response({"low_stock": values}, meta=meta)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def employees_view(request):
    return _report_response(request, "employees:read", "employees")


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def departments_view(request):
    return _report_response(request, "departments:read", "departments")


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def suppliers_view(request):
    return _report_response(request, "suppliers:read", "suppliers")


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def purchases_view(request):
    return _report_response(request, "purchase:read", "purchases")


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def monthly_sales_view(request):
    return _report_response(request, "sales:read", "monthly_sales")
