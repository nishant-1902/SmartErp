"""HTTP endpoints for purchase-order operations."""

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
from purchases.serializers import (
    EmptyActionSerializer,
    PurchaseOrderCreateSerializer,
    PurchaseOrderListQuerySerializer,
    PurchaseOrderPatchSerializer,
    PurchaseReceiptSerializer,
    RejectPurchaseOrderSerializer,
)
from purchases.services import (
    create_purchase_order,
    get_purchase_order,
    list_purchase_orders,
    receive_purchase_order,
    transition_purchase_order,
    update_purchase_order,
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
def purchase_orders_list_create_view(request):
    """List purchase orders or create a Draft with the matching permission."""
    if request.method == "GET":
        if not has_permission(request.user, "purchase:read"):
            return _permission_denied("purchase:read")
        filters = _validated_request(
            PurchaseOrderListQuerySerializer,
            request.query_params,
        )
        with mongo_database() as database:
            orders, meta = list_purchase_orders(
                database,
                status=filters.get("status"),
                supplier_id=filters.get("supplier_id"),
                pagination=_pagination(filters),
            )
        return success_response({"purchase_orders": orders}, meta=meta)

    if not has_permission(request.user, "purchase:create"):
        return _permission_denied("purchase:create")
    values = _validated_request(PurchaseOrderCreateSerializer, request.data)
    with mongo_database() as database:
        order = create_purchase_order(
            database,
            values=values,
            created_by=request.user.id,
        )
    return success_response({"purchase_order": order}, status=201)


@api_view(["GET", "PATCH"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_detail_view(request, purchase_order_id: str):
    """Read or edit a purchase order while it remains in Draft."""
    parsed_id = parse_object_id(purchase_order_id)
    if request.method == "GET":
        if not has_permission(request.user, "purchase:read"):
            return _permission_denied("purchase:read")
        with mongo_database() as database:
            order = get_purchase_order(database, parsed_id)
        return success_response({"purchase_order": order})

    if not has_permission(request.user, "purchase:create"):
        return _permission_denied("purchase:create")
    values = _validated_request(PurchaseOrderPatchSerializer, request.data)
    with mongo_database() as database:
        order = update_purchase_order(database, parsed_id, values=values)
    return success_response({"purchase_order": order})


def _transition_response(
    request,
    purchase_order_id: str,
    *,
    action: str,
    permission: str,
    request_serializer: Any = EmptyActionSerializer,
):
    """Authorize, validate, and execute one PO state transition."""
    parsed_id = parse_object_id(purchase_order_id)
    if not has_permission(request.user, permission):
        return _permission_denied(permission)
    values = _validated_request(request_serializer, request.data)
    with mongo_database() as database:
        order = transition_purchase_order(
            database,
            parsed_id,
            action=action,
            actor_id=request.user.id,
            reason=values.get("reason"),
            is_super_admin=request.user.role == "super_admin",
        )
    return success_response({"purchase_order": order})


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_submit_view(request, purchase_order_id: str):
    """Submit a Draft purchase order for approval."""
    return _transition_response(
        request,
        purchase_order_id,
        action="submit",
        permission="purchase:submit",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_approve_view(request, purchase_order_id: str):
    """Approve a pending PO subject to separation of duties."""
    return _transition_response(
        request,
        purchase_order_id,
        action="approve",
        permission="purchase:approve",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_reject_view(request, purchase_order_id: str):
    """Reject a pending PO with a required reason."""
    return _transition_response(
        request,
        purchase_order_id,
        action="reject",
        permission="purchase:reject",
        request_serializer=RejectPurchaseOrderSerializer,
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_cancel_view(request, purchase_order_id: str):
    """Cancel a Draft or pending-approval PO."""
    return _transition_response(
        request,
        purchase_order_id,
        action="cancel",
        permission="purchase:cancel",
    )


@api_view(["POST"])
@permission_classes([IsAuthenticatedMongo])
def purchase_order_receive_view(request, purchase_order_id: str):
    """Receive PO quantities through one idempotent MongoDB transaction."""
    parsed_id = parse_object_id(purchase_order_id)
    if not has_permission(request.user, "purchase:receive"):
        return _permission_denied("purchase:receive")
    values = _validated_request(PurchaseReceiptSerializer, request.data)
    with mongo_database() as database:
        receipt = receive_purchase_order(
            database,
            purchase_order_id=parsed_id,
            items=values["items"],
            notes=values.get("notes"),
            actor=request.user,
            idempotency_key=request.headers.get("Idempotency-Key") or "",
        )
    return success_response(receipt, status=201)
