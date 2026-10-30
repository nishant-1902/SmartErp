"""HTTP endpoints for employee administration and self-service profiles."""

from contextlib import contextmanager
from typing import Any, Generator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.decorators import api_view, permission_classes

from common.object_id import parse_object_id
from common.pagination import Pagination, parse_pagination
from common.permissions import IsAuthenticatedMongo, has_permission
from common.responses import error_response, success_response
from employees.repository import EMPLOYEE_SORT_FIELDS
from employees.serializers import (
    EmptyActionSerializer,
    EmployeeCreateSerializer,
    EmployeeListQuerySerializer,
    EmployeePatchSerializer,
)
from employees.services import (
    create_employee,
    deactivate_employee,
    get_current_employee,
    get_employee,
    list_designations,
    list_employees,
    update_employee,
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


def _validated_request(serializer_class: Any, data: Any) -> dict[str, Any]:
    """Validate request data and raise the standard DRF validation exception."""
    serializer = serializer_class(data=data)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data


def _has_full_read_access(user: Any) -> bool:
    """Employees may read their own profile, but not the employee directory."""
    return getattr(user, "role", None) != "employee" and has_permission(
        user,
        "employees:read",
    )


def _permission_denied(permission: str):
    """Build the standard permission-denied response."""
    return error_response(
        "permission_denied",
        f"The '{permission}' permission is required.",
        status=403,
    )


def _pagination(filters: dict[str, Any]) -> Pagination:
    """Build pagination and sorting from validated query parameters."""
    return parse_pagination(
        filters.get("page"),
        filters.get("page_size"),
        sort_by=filters.get("sort_by"),
        sort_order=filters.get("sort_order", "asc"),
        allowed_sort_fields=EMPLOYEE_SORT_FIELDS,
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo])
def employees_list_create_view(request):
    """List employees or create an employee with the matching matrix permission."""
    if request.method == "GET":
        if not _has_full_read_access(request.user):
            return _permission_denied("employees:read")
        filters = _validated_request(EmployeeListQuerySerializer, request.query_params)
        pagination = _pagination(filters)
        with mongo_database() as database:
            employees, meta = list_employees(
                database,
                search=filters.get("search"),
                department_id=filters.get("department_id"),
                status=filters.get("status"),
                pagination=pagination,
            )
        return success_response({"employees": employees}, meta=meta)

    if not has_permission(request.user, "employees:write"):
        return _permission_denied("employees:write")
    values = _validated_request(EmployeeCreateSerializer, request.data)
    with mongo_database() as database:
        employee = create_employee(
            database,
            values=values,
            actor_id=request.user.id,
        )
    return success_response({"employee": employee}, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def employee_me_view(request):
    """Return the employee profile linked to the authenticated Employee account."""
    if getattr(request.user, "role", None) != "employee":
        return _permission_denied("employee:self-read")
    with mongo_database() as database:
        employee = get_current_employee(database, request.user.id)
    return success_response({"employee": employee})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def employee_designations_view(request):
    """Return distinct designations for employee forms and dropdowns."""
    if not _has_full_read_access(request.user):
        return _permission_denied("employees:read")
    with mongo_database() as database:
        designations = list_designations(database)
    return success_response({"designations": designations})


@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticatedMongo])
def employee_detail_view(request, employee_id: str):
    """Read, update, or deactivate one employee."""
    parsed_id = parse_object_id(employee_id)
    if request.method == "GET":
        if getattr(request.user, "role", None) == "employee":
            with mongo_database() as database:
                own_employee = get_current_employee(database, request.user.id)
            if own_employee["id"] != str(parsed_id):
                return _permission_denied("employee:self-read")
            return success_response({"employee": own_employee})
        if not has_permission(request.user, "employees:read"):
            return _permission_denied("employees:read")
        with mongo_database() as database:
            employee = get_employee(database, parsed_id)
        return success_response({"employee": employee})

    if not has_permission(request.user, "employees:write"):
        return _permission_denied("employees:write")

    if request.method == "PATCH":
        values = _validated_request(EmployeePatchSerializer, request.data)
        with mongo_database() as database:
            employee = update_employee(
                database,
                parsed_id,
                values=values,
                actor_id=request.user.id,
            )
        return success_response({"employee": employee})

    _validated_request(EmptyActionSerializer, request.data)
    with mongo_database() as database:
        employee = deactivate_employee(
            database,
            parsed_id,
            actor_id=request.user.id,
        )
    return success_response({"employee": employee})
