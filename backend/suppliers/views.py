"""HTTP endpoints for supplier records and purchase history."""

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
from suppliers.repository import SUPPLIER_SORT_FIELDS
from suppliers.serializers import (
    SupplierCreateSerializer,
    SupplierListQuerySerializer,
    SupplierPatchSerializer,
    SupplierPurchaseOrdersQuerySerializer,
)
from suppliers.services import (
    create_supplier,
    get_supplier,
    list_supplier_purchase_orders,
    list_suppliers,
    update_supplier,
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
def suppliers_list_create_view(request):
    """List suppliers or create one with the matching matrix permission."""
    if request.method == "GET":
        if not has_permission(request.user, "suppliers:read"):
            return _permission_denied("suppliers:read")
        filters = _validated_request(SupplierListQuerySerializer, request.query_params)
        pagination = _pagination(filters, sort_fields=SUPPLIER_SORT_FIELDS)
        with mongo_database() as database:
            suppliers, meta = list_suppliers(
                database,
                search=filters.get("search"),
                status=filters.get("status"),
                pagination=pagination,
            )
        return success_response({"suppliers": suppliers}, meta=meta)

    if not has_permission(request.user, "suppliers:write"):
        return _permission_denied("suppliers:write")
    values = _validated_request(SupplierCreateSerializer, request.data)
    with mongo_database() as database:
        supplier = create_supplier(database, values=values)
    return success_response({"supplier": supplier}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def supplier_detail_view(request, supplier_id: str):
    """Read or update one supplier record."""
    parsed_id = parse_object_id(supplier_id)
    if request.method == "GET":
        if not has_permission(request.user, "suppliers:read"):
            return _permission_denied("suppliers:read")
        with mongo_database() as database:
            supplier = get_supplier(database, parsed_id)
        return success_response({"supplier": supplier})

    if not has_permission(request.user, "suppliers:write"):
        return _permission_denied("suppliers:write")
    values = _validated_request(SupplierPatchSerializer, request.data)
    with mongo_database() as database:
        supplier = update_supplier(database, parsed_id, values=values)
    return success_response({"supplier": supplier})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def supplier_purchase_orders_view(request, supplier_id: str):
    """Return paginated purchase history and outstanding orders for a supplier."""
    if not has_permission(request.user, "purchase:read"):
        return _permission_denied("purchase:read")
    parsed_id = parse_object_id(supplier_id)
    filters = _validated_request(
        SupplierPurchaseOrdersQuerySerializer,
        request.query_params,
    )
    pagination = _pagination(filters)
    with mongo_database() as database:
        history, outstanding, meta = list_supplier_purchase_orders(
            database,
            parsed_id,
            pagination=pagination,
        )
    return success_response(
        {
            "purchase_orders": history,
            "outstanding_purchase_orders": outstanding,
        },
        meta=meta,
    )
