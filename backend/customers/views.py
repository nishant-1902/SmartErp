"""HTTP endpoints for customer records and sales-order history."""

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
from customers.repository import CUSTOMER_SORT_FIELDS
from customers.serializers import (
    CustomerCreateSerializer,
    CustomerListQuerySerializer,
    CustomerPatchSerializer,
    CustomerSalesOrdersQuerySerializer,
)
from customers.services import (
    create_customer,
    get_customer,
    list_customer_sales_orders,
    list_customers,
    update_customer,
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


def _permission_denied(permission: str):
    """Build the standard permission-denied response."""
    return error_response(
        "permission_denied",
        f"The '{permission}' permission is required.",
        status=403,
    )


def _pagination(
    filters: dict[str, Any],
    *,
    sort_fields: frozenset[str] | None = None,
) -> Pagination:
    """Build pagination and optional allowlisted sorting from validated values."""
    return parse_pagination(
        filters.get("page"),
        filters.get("page_size"),
        sort_by=filters.get("sort_by"),
        sort_order=filters.get("sort_order", "asc"),
        allowed_sort_fields=sort_fields or (),
    )


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo])
def customers_list_create_view(request):
    """List customers or create one with the matching matrix permission."""
    if request.method == "GET":
        if not has_permission(request.user, "customers:read"):
            return _permission_denied("customers:read")
        filters = _validated_request(CustomerListQuerySerializer, request.query_params)
        pagination = _pagination(filters, sort_fields=CUSTOMER_SORT_FIELDS)
        with mongo_database() as database:
            customers, meta = list_customers(
                database,
                search=filters.get("search"),
                status=filters.get("status"),
                pagination=pagination,
            )
        return success_response({"customers": customers}, meta=meta)

    if not has_permission(request.user, "customers:write"):
        return _permission_denied("customers:write")
    values = _validated_request(CustomerCreateSerializer, request.data)
    with mongo_database() as database:
        customer = create_customer(database, values=values)
    return success_response({"customer": customer}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def customer_detail_view(request, customer_id: str):
    """Read or update one customer record."""
    parsed_id = parse_object_id(customer_id)
    if request.method == "GET":
        if not has_permission(request.user, "customers:read"):
            return _permission_denied("customers:read")
        with mongo_database() as database:
            customer = get_customer(database, parsed_id)
        return success_response({"customer": customer})

    if not has_permission(request.user, "customers:write"):
        return _permission_denied("customers:write")
    values = _validated_request(CustomerPatchSerializer, request.data)
    with mongo_database() as database:
        customer = update_customer(database, parsed_id, values=values)
    return success_response({"customer": customer})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def customer_sales_orders_view(request, customer_id: str):
    """Return paginated sales orders associated with one customer."""
    if not has_permission(request.user, "sales:read"):
        return _permission_denied("sales:read")
    parsed_id = parse_object_id(customer_id)
    filters = _validated_request(
        CustomerSalesOrdersQuerySerializer,
        request.query_params,
    )
    pagination = _pagination(filters)
    with mongo_database() as database:
        orders, meta = list_customer_sales_orders(
            database,
            parsed_id,
            status=filters.get("status"),
            pagination=pagination,
        )
    return success_response({"sales_orders": orders}, meta=meta)
