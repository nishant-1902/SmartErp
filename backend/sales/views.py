"""HTTP endpoints for sales-order CRUD and stock transitions."""

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
from sales.serializers import (
    EmptyActionSerializer,
    InvoiceListQuerySerializer,
    PaymentCreateSerializer,
    PaymentListQuerySerializer,
    SalesReturnCreateSerializer,
    SalesOrderCreateSerializer,
    SalesOrderListQuerySerializer,
    SalesOrderPatchSerializer,
)
from sales.services import (
    create_sales_order,
    fulfil_sales_order,
    get_invoice,
    get_sales_order,
    list_invoices,
    list_payments,
    list_sales_orders,
    process_sales_return,
    record_payment,
    transition_sales_order,
    update_sales_order,
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


def _pagination(filters: dict[str, Any]) -> Pagination:
    """Build pagination from already validated query parameters."""
    return parse_pagination(filters.get("page"), filters.get("page_size"))


@api_view(["GET", "POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_orders_list_create_view(request):
    """List sales orders or create a Draft order."""
    if request.method == "GET":
        if not has_permission(request.user, "sales:read"):
            return _permission_denied("sales:read")
        filters = _validated_request(
            SalesOrderListQuerySerializer,
            request.query_params,
        )
        with mongo_database() as database:
            orders, meta = list_sales_orders(
                database,
                status=filters.get("status"),
                customer_id=filters.get("customer_id"),
                pagination=_pagination(filters),
            )
        return success_response({"sales_orders": orders}, meta=meta)

    if not has_permission(request.user, "sales:create"):
        return _permission_denied("sales:create")
    values = _validated_request(SalesOrderCreateSerializer, request.data)
    with mongo_database() as database:
        order = create_sales_order(
            database,
            values=values,
            created_by=request.user.id,
        )
    return success_response({"sales_order": order}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_detail_view(request, sales_order_id: str):
    """Read or edit one sales order while it remains Draft."""
    parsed_id = parse_object_id(sales_order_id)
    if request.method == "GET":
        if not has_permission(request.user, "sales:read"):
            return _permission_denied("sales:read")
        with mongo_database() as database:
            order = get_sales_order(database, parsed_id)
        return success_response({"sales_order": order})

    if not has_permission(request.user, "sales:create"):
        return _permission_denied("sales:create")
    values = _validated_request(SalesOrderPatchSerializer, request.data)
    with mongo_database() as database:
        order = update_sales_order(database, parsed_id, values=values)
    return success_response({"sales_order": order})


def _transition_response(request, sales_order_id: str, *, action: str):
    """Authorize, validate, and run a stock-aware order state transition."""
    parsed_id = parse_object_id(sales_order_id)
    permission = "sales:confirm" if action == "confirm" else "sales:cancel"
    if not has_permission(request.user, permission):
        return _permission_denied(permission)
    _validated_request(EmptyActionSerializer, request.data)
    with mongo_database() as database:
        order = transition_sales_order(
            database,
            parsed_id,
            action=action,
            actor_id=request.user.id,
        )
    return success_response({"sales_order": order})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_confirm_view(request, sales_order_id: str):
    """Confirm a Draft order and reserve its inventory atomically."""
    return _transition_response(request, sales_order_id, action="confirm")


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_cancel_view(request, sales_order_id: str):
    """Cancel a Draft or Confirmed order, releasing any reservation."""
    return _transition_response(request, sales_order_id, action="cancel")


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_fulfill_view(request, sales_order_id: str):
    """Fulfil a Confirmed order and issue its invoice exactly once."""
    parsed_id = parse_object_id(sales_order_id)
    if not has_permission(request.user, "sales:fulfil"):
        return _permission_denied("sales:fulfil")
    _validated_request(EmptyActionSerializer, request.data)
    with mongo_database() as database:
        result = fulfil_sales_order(
            database,
            parsed_id,
            actor_id=request.user.id,
            idempotency_key=request.headers.get("Idempotency-Key"),
        )
    return success_response(result)


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_payment_view(request, sales_order_id: str):
    """Record a payment against one fulfilled order."""
    parsed_id = parse_object_id(sales_order_id)
    if not has_permission(request.user, "payments:record"):
        return _permission_denied("payments:record")
    values = _validated_request(PaymentCreateSerializer, request.data)
    with mongo_database() as database:
        result = record_payment(
            database,
            parsed_id,
            values=values,
            actor_id=request.user.id,
        )
    return success_response(result, status=201)


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def sales_order_return_view(request, sales_order_id: str):
    """Restock a fulfilled order and create its credit note."""
    parsed_id = parse_object_id(sales_order_id)
    if not has_permission(request.user, "returns:process"):
        return _permission_denied("returns:process")
    values = _validated_request(SalesReturnCreateSerializer, request.data)
    with mongo_database() as database:
        result = process_sales_return(
            database,
            parsed_id,
            values=values,
            actor_id=request.user.id,
        )
    return success_response(result, status=201)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def payments_list_view(request):
    """List payments using validated filters and pagination."""
    if not has_permission(request.user, "payments:read"):
        return _permission_denied("payments:read")
    filters = _validated_request(PaymentListQuerySerializer, request.query_params)
    with mongo_database() as database:
        payments, meta = list_payments(
            database,
            customer_id=filters.get("customer_id"),
            sales_order_id=filters.get("sales_order_id"),
            method=filters.get("method"),
            status=filters.get("status"),
            pagination=_pagination(filters),
        )
    return success_response({"payments": payments}, meta=meta)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def invoices_list_view(request):
    """List invoices using validated filters and pagination."""
    if not has_permission(request.user, "invoices:read"):
        return _permission_denied("invoices:read")
    filters = _validated_request(InvoiceListQuerySerializer, request.query_params)
    with mongo_database() as database:
        invoices, meta = list_invoices(
            database,
            customer_id=filters.get("customer_id"),
            sales_order_id=filters.get("sales_order_id"),
            pagination=_pagination(filters),
        )
    return success_response({"invoices": invoices}, meta=meta)


@api_view(["GET"])
@permission_classes([IsAuthenticatedMongo])
def invoice_detail_view(request, invoice_id: str):
    """Read one invoice snapshot."""
    parsed_id = parse_object_id(invoice_id)
    if not has_permission(request.user, "invoices:read"):
        return _permission_denied("invoices:read")
    with mongo_database() as database:
        invoice = get_invoice(database, parsed_id)
    return success_response({"invoice": invoice})
