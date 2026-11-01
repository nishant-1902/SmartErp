"""Purchase-order business rules, totals, and status transitions."""

from collections.abc import Mapping
from datetime import datetime
from decimal import Decimal
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo.client_session import ClientSession
from pymongo.database import Database

from common.exceptions import (
    ConflictError,
    InvalidStateTransition,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailed,
)
from common.idempotency import execute_idempotent, normalize_idempotency_key
from common.money import line_total, quantize_money, to_decimal
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.permissions import has_permission
from common.serialization import serialize_document
from common.time import utc_now
from accounts.repository import write_audit_log
from inventory.services import apply_stock_change, get_active_product_for_order
from purchases.repository import (
    allocate_receipt_reference,
    count_purchase_orders,
    find_purchase_order_by_id,
    increment_received_quantity,
    insert_purchase_order,
    insert_purchase_receipt,
    list_purchase_orders as list_purchase_order_records,
    public_purchase_order,
    transition_purchase_order as transition_purchase_order_record,
    update_draft_purchase_order,
    update_received_purchase_order_status,
)
from suppliers.services import require_active_supplier

TRANSITIONS: dict[str, dict[str, str]] = {
    "draft": {
        "submit": "pending_approval",
        "cancel": "cancelled",
    },
    "pending_approval": {
        "approve": "approved",
        "reject": "rejected",
        "cancel": "cancelled",
    },
    "approved": {},
    "rejected": {},
    "partially_received": {},
    "received": {},
    "cancelled": {},
}


def _public_order(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a PO to its public, JSON-safe response representation."""
    return serialize_document(public_purchase_order(document))


def _build_items(
    database: Database[Any],
    values: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Decimal]:
    """Build trusted product snapshots and calculate the line-item subtotal."""
    items: list[dict[str, Any]] = []
    seen_product_ids: set[ObjectId] = set()
    subtotal = Decimal("0.00")
    for value in values:
        product_id = parse_object_id(value["product_id"])
        if product_id in seen_product_ids:
            raise ValidationFailed(
                "A product may appear only once in a purchase order.",
                details={"items": "Duplicate product IDs are not allowed."},
            )
        seen_product_ids.add(product_id)
        product = get_active_product_for_order(database, product_id)
        unit_cost = to_decimal(value["unit_cost"])
        quantity = value["quantity_ordered"]
        total = line_total(unit_cost, quantity)
        items.append(
            {
                "product_id": product_id,
                "sku": product["sku"],
                "name": product["name"],
                "quantity_ordered": quantity,
                "quantity_received": 0,
                "unit_cost": unit_cost,
                "line_total": total,
            }
        )
        subtotal += total
    return items, quantize_money(subtotal)


def _prepare_values(
    database: Database[Any],
    *,
    supplier_id: ObjectId,
    items: list[dict[str, Any]],
    tax_rate: Decimal,
) -> tuple[dict[str, Any], list[dict[str, Any]], Decimal, Decimal, Decimal]:
    """Validate master records and calculate all order totals."""
    supplier = require_active_supplier(database, supplier_id)
    built_items, subtotal = _build_items(database, items)
    tax_total = quantize_money(subtotal * tax_rate / Decimal("100"))
    grand_total = quantize_money(subtotal + tax_total)
    return supplier, built_items, subtotal, tax_total, grand_total


def create_purchase_order(
    database: Database[Any],
    *,
    values: dict[str, Any],
    created_by: ObjectId | str,
) -> dict[str, Any]:
    """Create a Draft PO with active master records and server-calculated totals."""
    actor_id = parse_object_id(created_by)
    supplier, items, subtotal, tax_total, grand_total = _prepare_values(
        database,
        supplier_id=values["supplier_id"],
        items=values["items"],
        tax_rate=values["tax_rate"],
    )
    order = insert_purchase_order(
        database,
        supplier=supplier,
        items=items,
        subtotal=subtotal,
        tax_rate=values["tax_rate"],
        tax_total=tax_total,
        grand_total=grand_total,
        created_by=actor_id,
    )
    return _public_order(order)


def get_purchase_order(
    database: Database[Any],
    purchase_order_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one purchase order or raise a safe not-found error."""
    order = find_purchase_order_by_id(database, purchase_order_id)
    if order is None:
        raise NotFoundError("Purchase order was not found.")
    return _public_order(order)


def list_purchase_orders(
    database: Database[Any],
    *,
    status: str | None,
    supplier_id: ObjectId | None,
    start_date: datetime | None,
    end_date: datetime | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return a paginated purchase-order list and metadata."""
    orders = list_purchase_order_records(
        database,
        status=status,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_purchase_orders(
        database,
        status=status,
        supplier_id=supplier_id,
        start_date=start_date,
        end_date=end_date,
    )
    return [_public_order(order) for order in orders], pagination.build_meta(total)


def update_purchase_order(
    database: Database[Any],
    purchase_order_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Edit a Draft PO and recalculate totals from its final values."""
    parsed_id = parse_object_id(purchase_order_id)
    current = find_purchase_order_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Purchase order was not found.")
    if current["status"] != "draft":
        raise InvalidStateTransition("Only Draft purchase orders may be edited.")

    supplier_id = values.get("supplier_id", current["supplier_id"])
    current_items = [
        {
            "product_id": item["product_id"],
            "quantity_ordered": item["quantity_ordered"],
            "unit_cost": item["unit_cost"],
        }
        for item in current["items"]
    ]
    items_input = values.get("items", current_items)
    tax_rate = to_decimal(
        values.get("tax_rate", current.get("tax_rate", Decimal128("0.00")))
    )
    supplier, items, subtotal, tax_total, grand_total = _prepare_values(
        database,
        supplier_id=supplier_id,
        items=items_input,
        tax_rate=tax_rate,
    )
    updated = update_draft_purchase_order(
        database,
        parsed_id,
        supplier=supplier,
        items=items,
        subtotal=subtotal,
        tax_rate=tax_rate,
        tax_total=tax_total,
        grand_total=grand_total,
    )
    if updated is None:
        raise InvalidStateTransition("Only Draft purchase orders may be edited.")
    return _public_order(updated)


def transition_purchase_order(
    database: Database[Any],
    purchase_order_id: ObjectId | str,
    *,
    action: str,
    actor_id: ObjectId | str,
    reason: str | None = None,
    is_super_admin: bool = False,
) -> dict[str, Any]:
    """Apply one allowed transition using a conditional atomic status update."""
    parsed_id = parse_object_id(purchase_order_id)
    actor = parse_object_id(actor_id)
    current = find_purchase_order_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Purchase order was not found.")

    expected_status = current["status"]
    next_status = TRANSITIONS.get(expected_status, {}).get(action)
    if next_status is None:
        raise InvalidStateTransition()
    if action == "submit":
        _prepare_values(
            database,
            supplier_id=current["supplier_id"],
            items=[
                {
                    "product_id": item["product_id"],
                    "quantity_ordered": item["quantity_ordered"],
                    "unit_cost": item["unit_cost"],
                }
                for item in current["items"]
            ],
            tax_rate=to_decimal(current["tax_rate"]),
        )
    if (
        action == "approve"
        and current["created_by"] == actor
        and not is_super_admin
    ):
        raise PermissionDeniedError(
            "The purchase-order creator cannot approve their own order."
        )
    if action == "reject" and (reason is None or not reason.strip()):
        raise ValidationFailed(
            "A rejection reason is required.",
            details={"reason": "This field is required."},
        )

    updated = transition_purchase_order_record(
        database,
        parsed_id,
        expected_status=expected_status,
        next_status=next_status,
        actor_id=actor,
        note=reason.strip() if reason is not None else None,
    )
    if updated is None:
        raise InvalidStateTransition()
    return _public_order(updated)


def receive_purchase_order(
    database: Database[Any],
    *,
    purchase_order_id: ObjectId | str,
    items: list[dict[str, Any]],
    notes: str | None,
    actor: Any,
    idempotency_key: str,
) -> dict[str, Any]:
    """Receive PO quantities, stock, audit, and idempotency in one transaction."""
    parsed_order_id = parse_object_id(purchase_order_id)
    actor_id = parse_object_id(getattr(actor, "id", None))
    if not has_permission(actor, "purchase:receive"):
        raise PermissionDeniedError("The 'purchase:receive' permission is required.")
    normalized_key = normalize_idempotency_key(idempotency_key)

    normalized_items: list[dict[str, Any]] = []
    seen_product_ids: set[ObjectId] = set()
    for item in items:
        product_id = parse_object_id(item["product_id"])
        quantity = item["quantity_received"]
        if (
            isinstance(quantity, bool)
            or not isinstance(quantity, int)
            or quantity <= 0
        ):
            raise ValidationFailed(
                "Received quantities must be positive integers.",
                details={"quantity_received": "Must be a positive integer."},
            )
        if product_id in seen_product_ids:
            raise ValidationFailed(
                "A product may appear only once in a receipt.",
                details={"items": "Duplicate product IDs are not allowed."},
            )
        seen_product_ids.add(product_id)
        normalized_items.append(
            {"product_id": product_id, "quantity_received": quantity}
        )

    request_body = {
        "purchase_order_id": parsed_order_id,
        "items": normalized_items,
        "notes": notes,
    }

    def operation(
        session: ClientSession,
        receipt_id: ObjectId,
    ) -> dict[str, Any]:
        order = find_purchase_order_by_id(
            database,
            parsed_order_id,
            session=session,
        )
        if order is None:
            raise NotFoundError("Purchase order was not found.")
        if not has_permission(actor, "purchase:receive"):
            raise PermissionDeniedError(
                "The 'purchase:receive' permission is required."
            )
        expected_status = order["status"]
        if expected_status not in {"approved", "partially_received"}:
            raise InvalidStateTransition(
                "Only approved or partially received purchase orders can be received."
            )

        order_items = {item["product_id"]: item for item in order["items"]}
        prepared_items: list[dict[str, Any]] = []
        for requested in normalized_items:
            line = order_items.get(requested["product_id"])
            if line is None:
                raise ValidationFailed(
                    "A receipt product is not on this purchase order.",
                    details={"product_id": str(requested["product_id"])},
                )
            remaining = line["quantity_ordered"] - line["quantity_received"]
            if requested["quantity_received"] > remaining:
                raise ValidationFailed(
                    "Received quantity exceeds the remaining ordered quantity.",
                    details={
                        "product_id": str(requested["product_id"]),
                        "remaining_quantity": remaining,
                    },
                )
            prepared_items.append(
                {
                    "product_id": requested["product_id"],
                    "quantity_received": requested["quantity_received"],
                    "ordered_quantity": line["quantity_ordered"],
                }
            )

        receipt_reference = allocate_receipt_reference(database, session)
        receipt = insert_purchase_receipt(
            database,
            session,
            receipt_id=receipt_id,
            receipt_reference=receipt_reference,
            purchase_order=order,
            items=[
                {
                    "product_id": item["product_id"],
                    "quantity_received": item["quantity_received"],
                }
                for item in prepared_items
            ],
            received_by=actor_id,
            idempotency_key=normalized_key,
            notes=notes,
        )

        movement_reason = notes or f"Purchase receipt {receipt_reference}"
        for item in prepared_items:
            apply_stock_change(
                session,
                item["product_id"],
                item["quantity_received"],
                0,
                "purchase_receipt",
                movement_reason,
                "purchase_receipt",
                receipt_id,
                actor_id,
            )

        received_by_product = {
            item["product_id"]: item["quantity_received"]
            for item in prepared_items
        }
        for item in prepared_items:
            result = increment_received_quantity(
                database,
                session,
                purchase_order_id=parsed_order_id,
                product_id=item["product_id"],
                ordered_quantity=item["ordered_quantity"],
                received_quantity=item["quantity_received"],
            )
            if result.modified_count != 1:
                raise ConflictError(
                    "Purchase-order quantities changed while processing this receipt."
                )

        all_received = all(
            item["quantity_received"]
            + received_by_product.get(item["product_id"], 0)
            == item["quantity_ordered"]
            for item in order["items"]
        )
        next_status = "received" if all_received else "partially_received"
        status_result = update_received_purchase_order_status(
            database,
            session,
            purchase_order_id=parsed_order_id,
            expected_status=expected_status,
            next_status=next_status,
            actor_id=actor_id,
            note=notes,
        )
        if status_result.modified_count != 1:
            raise ConflictError(
                "Purchase-order status changed while processing this receipt."
            )

        write_audit_log(
            database,
            actor_id=actor_id,
            action="purchase_order.received",
            resource="purchase_order",
            resource_id=parsed_order_id,
            outcome="success",
            session=session,
            now=utc_now(),
        )
        return {
            "purchase_receipt": serialize_document(
                {
                    "id": receipt["_id"],
                    **{
                        key: value
                        for key, value in receipt.items()
                        if key != "_id"
                    },
                }
            )
        }

    return execute_idempotent(
        database,
        user_id=actor_id,
        endpoint=f"/api/purchase-orders/{parsed_order_id}/receive/",
        key=normalized_key,
        request_body=request_body,
        operation=operation,
    )
