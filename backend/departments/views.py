"""HTTP endpoints for department and department-employee operations."""

from contextlib import contextmanager
from typing import Any, Generator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.decorators import api_view, permission_classes

from common.object_id import parse_object_id
from common.pagination import Pagination, parse_pagination
from common.permissions import IsAuthenticatedMongo, has_permission, require
from common.responses import error_response, success_response
from departments.repository import DEPARTMENT_SORT_FIELDS, EMPLOYEE_SORT_FIELDS
from departments.serializers import (
    DepartmentCreateSerializer,
    DepartmentEmployeesQuerySerializer,
    DepartmentListQuerySerializer,
    DepartmentPatchSerializer,
)
from departments.services import (
    create_department,
    get_department,
    list_department_employees,
    list_departments,
    update_department,
)


@contextmanager
def mongo_database() -> Generator[Any, None, None]:
    """Open a request-scoped PyMongo database connection."""
    mongo_uri = getattr(settings, "MONGO_URI", "")
    database_name = getattr(settings, "MONGO_DB_NAME", "")
    if not mongo_uri:
        raise ImproperlyConfigured("MONGO_URI is not configured.")
    if not database_name:
        raise ImproperlyConfigured("MONGO_DB_NAME is not configured.")
    with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
        yield client[database_name]


def _validated_request(serializer_class: Any, data: Any) -> dict[str, Any]:
    """Validate request data and raise the standard DRF validation exception."""
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _pagination(
    filters: dict[str, Any],
    allowed_sort_fields: frozenset[str],
) -> Pagination:
    """Build shared pagination from validated query parameters."""
    return parse_pagination(
        filters.get("page"),
        filters.get("page_size"),
        sort_by=filters.get("sort_by"),
        sort_order=filters.get("sort_order", "asc"),
        allowed_sort_fields=allowed_sort_fields,
    )


def _permission_denied(permission: str):
    """Return a consistent permission error response."""
    return error_response(
        "permission_denied",
        f"The '{permission}' permission is required.",
        status=403,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo])
def departments_list_create_view(request):
    """List departments or create one with department-write permission."""
    if request.method == "GET":
        if not has_permission(request.user, "departments:read"):
            return _permission_denied("departments:read")
        filters = _validated_request(DepartmentListQuerySerializer, request.query_params)
        pagination = _pagination(filters, DEPARTMENT_SORT_FIELDS)
        with mongo_database() as database:
            departments, meta = list_departments(
                database,
                search=filters.get("search"),
                is_active=filters.get("is_active"),
                pagination=pagination,
            )
        return success_response({"departments": departments}, meta=meta)

    if not has_permission(request.user, "departments:write"):
        return _permission_denied("departments:write")
    values = _validated_request(DepartmentCreateSerializer, request.data)
    with mongo_database() as database:
        department = create_department(database, values=values)
    return success_response({"department": department}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def department_detail_view(request, department_id: str):
    """Read or partially update one department."""
    if request.method == "GET":
        if not has_permission(request.user, "departments:read"):
            return _permission_denied("departments:read")
        parsed_id = parse_object_id(department_id)
        with mongo_database() as database:
            department = get_department(database, parsed_id)
        return success_response({"department": department})

    if not has_permission(request.user, "departments:write"):
        return _permission_denied("departments:write")
    parsed_id = parse_object_id(department_id)
    values = _validated_request(DepartmentPatchSerializer, request.data)
    with mongo_database() as database:
        department = update_department(database, parsed_id, values=values)
    return success_response({"department": department})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo, require("departments:read")])
def department_employees_view(request, department_id: str):
    """List employees assigned to one department."""
    parsed_id = parse_object_id(department_id)
    filters = _validated_request(
        DepartmentEmployeesQuerySerializer,
        request.query_params,
    )
    pagination = _pagination(filters, EMPLOYEE_SORT_FIELDS)
    with mongo_database() as database:
        employees, meta = list_department_employees(
            database,
            parsed_id,
            search=filters.get("search"),
            pagination=pagination,
        )
    return success_response({"employees": employees}, meta=meta)
