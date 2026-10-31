"""HTTP endpoints for product catalogue operations."""

from contextlib import contextmanager
from typing import Any, Generator

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from rest_framework.decorators import api_view, permission_classes

from common.idempotency import normalize_idempotency_key
from common.object_id import parse_object_id
from common.pagination import Pagination, parse_pagination
from common.permissions import IsAuthenticatedMongo, has_permission
from common.responses import error_response, success_response
from inventory.repository import PRODUCT_SORT_FIELDS
from inventory.serializers import (
    ProductCategoriesQuerySerializer,
    ProductCreateSerializer,
    ProductListQuerySerializer,
    ProductLowStockQuerySerializer,
    ProductPatchSerializer,
    StockAdjustmentSerializer,
    StockMovementsQuerySerializer,
)
from inventory.services import (
    adjust_stock,
    create_product,
    get_product,
    list_categories,
    list_products,
    list_stock_movements,
    update_product,
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


def _pagination(filters: dict[str, Any]) -> Pagination:
    """Build shared pagination from validated product query parameters."""
    return parse_pagination(
        filters.get("page"),
        filters.get("page_size"),
        sort_by=filters.get("sort_by"),
        sort_order=filters.get("sort_order", "asc"),
        allowed_sort_fields=PRODUCT_SORT_FIELDS,
    )


def _permission_denied(permission: str):
    """Return a consistent permission error response."""
    return error_response(
        "permission_denied",
        f"The '{permission}' permission is required.",
        status=403,
    )


def _list_products(request, *, low_stock: bool | None):
    """Validate filters and return a paginated product listing."""
    serializer_class = (
        ProductListQuerySerializer if low_stock is None else ProductLowStockQuerySerializer
    )
    filters = _validated_request(serializer_class, request.query_params)
    pagination = _pagination(filters)
    with mongo_database() as database:
        products, meta = list_products(
            database,
            search=filters.get("search"),
            category=filters.get("category"),
            is_active=filters.get("is_active"),
            low_stock=filters.get("low_stock", low_stock),
            pagination=pagination,
        )
    return success_response({"products": products}, meta=meta)


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo])
def products_list_create_view(request):
    """List products or create one with products:write permission."""
    if request.method == "GET":
        if not has_permission(request.user, "products:read"):
            return _permission_denied("products:read")
        return _list_products(request, low_stock=None)

    if not has_permission(request.user, "products:write"):
        return _permission_denied("products:write")
    values = _validated_request(ProductCreateSerializer, request.data)
    with mongo_database() as database:
        product = create_product(database, values=values)
    return success_response({"product": product}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def product_detail_view(request, product_id: str):
    """Read or partially update one product."""
    if request.method == "GET":
        if not has_permission(request.user, "products:read"):
            return _permission_denied("products:read")
        parsed_id = parse_object_id(product_id)
        with mongo_database() as database:
            product = get_product(database, parsed_id)
        return success_response({"product": product})

    if not has_permission(request.user, "products:write"):
        return _permission_denied("products:write")
    parsed_id = parse_object_id(product_id)
    values = _validated_request(ProductPatchSerializer, request.data)
    with mongo_database() as database:
        product = update_product(database, parsed_id, values=values)
    return success_response({"product": product})


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def low_stock_products_view(request):
    """Return paginated products whose available quantity is low."""
    if not has_permission(request.user, "products:read"):
        return _permission_denied("products:read")
    return _list_products(request, low_stock=True)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def product_categories_view(request):
    """Return the sorted distinct product categories."""
    if not has_permission(request.user, "products:read"):
        return _permission_denied("products:read")
    _validated_request(ProductCategoriesQuerySerializer, request.query_params)
    with mongo_database() as database:
        categories = list_categories(database)
    return success_response({"categories": categories})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def stock_adjustments_view(request):
    """Apply one idempotent on-hand quantity adjustment."""
    if not has_permission(request.user, "stock:adjust"):
        return _permission_denied("stock:adjust")
    values = _validated_request(StockAdjustmentSerializer, request.data)
    key = normalize_idempotency_key(request.headers.get("Idempotency-Key"))
    with mongo_database() as database:
        result = adjust_stock(
            database,
            product_id=values["product_id"],
            quantity_change=values["quantity_change"],
            reason=values["reason"],
            user_id=parse_object_id(request.user.id),
            idempotency_key=key,
        )
    return success_response(result, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def stock_movements_view(request):
    """Return a paginated, newest-first append-only stock movement list."""
    if not has_permission(request.user, "stock:read"):
        return _permission_denied("stock:read")
    filters = _validated_request(
        StockMovementsQuerySerializer,
        request.query_params,
    )
    pagination = parse_pagination(
        filters.get("page"),
        filters.get("page_size"),
    )
    with mongo_database() as database:
        movements, meta = list_stock_movements(
            database,
            product_id=filters.get("product"),
            movement_type=filters.get("type"),
            start_date=filters.get("start_date"),
            end_date=filters.get("end_date"),
            user_id=filters.get("user"),
            pagination=pagination,
        )
    return success_response({"stock_movements": movements}, meta=meta)
