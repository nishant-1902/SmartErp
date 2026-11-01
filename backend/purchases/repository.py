"""PyMongo data access for purchase orders."""

from collections.abc import Mapping
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from common.money import to_decimal128
from common.object_id import parse_object_id
from common.time import utc_now

PURCHASE_ORDER_RESPONSE_FIELDS = (
    "po_number",
    "supplier_id",
    "supplier_snapshot",
    "items",
    "tax_rate",
    "subtotal",
    "tax_total",
    "grand_total",
    "status",
    "status_history",
    "created_by",
    "approved_by",
    "created_at",
    "updated_at",
)


def allocate_po_number(
    database: Database[Any],
    *,
    year: int | None = None,
) -> str:
    """Atomically allocate the next yearly purchase-order number."""
    number_year = year if year is not None else utc_now().year
    if isinstance(number_year, bool) or not isinstance(number_year, int):
        raise ValueError("Purchase-order year must be an integer.")
    counter_id = f"purchase_order:{number_year}"
    while True:
        now = utc_now()
        try:
            counter = database["counters"].find_one_and_update(
                {"_id": counter_id},
                {"$inc": {"value": 1}, "$set": {"updated_at": now}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            counter = database["counters"].find_one_and_update(
                {"_id": counter_id},
                {"$inc": {"value": 1}, "$set": {"updated_at": now}},
                return_document=ReturnDocument.AFTER,
            )
        if (
            counter is None
            or not isinstance(counter.get("value"), int)
            or isinstance(counter.get("value"), bool)
        ):
            raise RuntimeError("Purchase-order counter did not return a valid value.")
        return f"PO-{number_year}-{counter['value']:06d}"


def insert_purchase_order(
    database: Database[Any],
    *,
    supplier: Mapping[str, Any],
    items: list[dict[str, Any]],
    subtotal: Any,
    tax_rate: Any,
    tax_total: Any,
    grand_total: Any,
    created_by: ObjectId,
) -> dict[str, Any]:
    """Insert a Draft order with server-built snapshots and monetary values."""
    now = utc_now()
    document: dict[str, Any] = {
        "po_number": allocate_po_number(database),
        "supplier_id": supplier["_id"],
        "supplier_snapshot": {
            "code": supplier["code"],
            "name": supplier["name"],
            "email": supplier.get("email"),
        },
        "items": [
            {
                **item,
                "unit_cost": to_decimal128(item["unit_cost"]),
                "line_total": to_decimal128(item["line_total"]),
            }
            for item in items
        ],
        "tax_rate": to_decimal128(tax_rate),
        "subtotal": to_decimal128(subtotal),
        "tax_total": to_decimal128(tax_total),
        "grand_total": to_decimal128(grand_total),
        "status": "draft",
        "status_history": [
            {
                "status": "draft",
                "by": created_by,
                "at": now,
                "note": None,
            }
        ],
        "created_by": created_by,
        "approved_by": None,
        "created_at": now,
        "updated_at": now,
    }
    result = database["purchase_orders"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_purchase_order_by_id(
    database: Database[Any],
    purchase_order_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find one purchase order by a validated ObjectId."""
    return database["purchase_orders"].find_one(
        {"_id": parse_object_id(purchase_order_id)}
    )


def list_purchase_orders(
    database: Database[Any],
    *,
    status: str | None,
    supplier_id: ObjectId | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one newest-first page of purchase orders."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if supplier_id is not None:
        query["supplier_id"] = supplier_id
    return list(
        database["purchase_orders"]
        .find(query)
        .sort([("created_at", -1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )


def count_purchase_orders(
    database: Database[Any],
    *,
    status: str | None,
    supplier_id: ObjectId | None,
) -> int:
    """Count purchase orders matching the validated list filters."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if supplier_id is not None:
        query["supplier_id"] = supplier_id
    return database["purchase_orders"].count_documents(query)


def update_draft_purchase_order(
    database: Database[Any],
    purchase_order_id: ObjectId,
    *,
    supplier: Mapping[str, Any],
    items: list[dict[str, Any]],
    subtotal: Any,
    tax_rate: Any,
    tax_total: Any,
    grand_total: Any,
) -> dict[str, Any] | None:
    """Update an order only if it is still Draft."""
    changes = {
        "supplier_id": supplier["_id"],
        "supplier_snapshot": {
            "code": supplier["code"],
            "name": supplier["name"],
            "email": supplier.get("email"),
        },
        "items": [
            {
                **item,
                "unit_cost": to_decimal128(item["unit_cost"]),
                "line_total": to_decimal128(item["line_total"]),
            }
            for item in items
        ],
        "tax_rate": to_decimal128(tax_rate),
        "subtotal": to_decimal128(subtotal),
        "tax_total": to_decimal128(tax_total),
        "grand_total": to_decimal128(grand_total),
        "updated_at": utc_now(),
    }
    return database["purchase_orders"].find_one_and_update(
        {"_id": purchase_order_id, "status": "draft"},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )


def transition_purchase_order(
    database: Database[Any],
    purchase_order_id: ObjectId,
    *,
    expected_status: str,
    next_status: str,
    actor_id: ObjectId,
    note: str | None = None,
) -> dict[str, Any] | None:
    """Conditionally change status and append history in one MongoDB update."""
    now = utc_now()
    changes: dict[str, Any] = {
        "status": next_status,
        "updated_at": now,
    }
    if next_status == "approved":
        changes["approved_by"] = actor_id
    return database["purchase_orders"].find_one_and_update(
        {"_id": purchase_order_id, "status": expected_status},
        {
            "$set": changes,
            "$push": {
                "status_history": {
                    "status": next_status,
                    "by": actor_id,
                    "at": now,
                    "note": note,
                }
            },
        },
        return_document=ReturnDocument.AFTER,
    )


def public_purchase_order(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project the public purchase-order fields and stable identifier."""
    return {
        "id": document["_id"],
        **{
            field: document[field]
            for field in PURCHASE_ORDER_RESPONSE_FIELDS
            if field in document
        },
    }
