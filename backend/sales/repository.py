"""PyMongo data access for sales orders and their state transitions."""

from collections.abc import Mapping
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from common.money import to_decimal128
from common.object_id import parse_object_id
from common.time import utc_now

SALES_ORDER_RESPONSE_FIELDS = (
    "order_number",
    "customer_id",
    "customer_snapshot",
    "items",
    "subtotal",
    "discount_total",
    "tax_total",
    "grand_total",
    "status",
    "return_status",
    "status_history",
    "payment_status",
    "created_by",
    "created_at",
    "updated_at",
    "fulfilled_at",
)


def allocate_sales_order_number(
    database: Database[Any],
    *,
    year: int | None = None,
) -> str:
    """Atomically allocate the next yearly sales-order number."""
    number_year = year if year is not None else utc_now().year
    if isinstance(number_year, bool) or not isinstance(number_year, int):
        raise ValueError("Sales-order year must be an integer.")
    counter_id = f"sales_order:{number_year}"
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
            raise RuntimeError("Sales-order counter did not return a valid value.")
        return f"SO-{number_year}-{counter['value']:06d}"


def insert_sales_order(
    database: Database[Any],
    *,
    customer: Mapping[str, Any],
    items: list[dict[str, Any]],
    subtotal: Any,
    discount_total: Any,
    tax_total: Any,
    grand_total: Any,
    created_by: ObjectId,
) -> dict[str, Any]:
    """Insert a Draft order containing server-derived snapshots and totals."""
    now = utc_now()
    document: dict[str, Any] = {
        "order_number": allocate_sales_order_number(database),
        "customer_id": customer["_id"],
        "customer_snapshot": {
            "code": customer["code"],
            "name": customer["name"],
            "email": customer.get("email"),
            "billing_address": customer.get("billing_address"),
            "shipping_address": customer.get("shipping_address"),
        },
        "items": [
            {
                **item,
                "unit_price": to_decimal128(item["unit_price"]),
                "discount_percent": to_decimal128(item["discount_percent"]),
                "tax_percent": to_decimal128(item["tax_percent"]),
                "line_subtotal": to_decimal128(item["line_subtotal"]),
                "line_tax": to_decimal128(item["line_tax"]),
                "line_total": to_decimal128(item["line_total"]),
            }
            for item in items
        ],
        "subtotal": to_decimal128(subtotal),
        "discount_total": to_decimal128(discount_total),
        "tax_total": to_decimal128(tax_total),
        "grand_total": to_decimal128(grand_total),
        "status": "draft",
        "return_status": "none",
        "status_history": [
            {"status": "draft", "by": created_by, "at": now, "note": None}
        ],
        "payment_status": "unpaid",
        "created_by": created_by,
        "created_at": now,
        "updated_at": now,
        "fulfilled_at": None,
    }
    result = database["sales_orders"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_sales_order_by_id(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    session: Any = None,
) -> dict[str, Any] | None:
    """Find one sales order by a validated ObjectId."""
    return database["sales_orders"].find_one(
        {"_id": parse_object_id(sales_order_id)},
        session=session,
    )


def list_sales_orders(
    database: Database[Any],
    *,
    status: str | None,
    customer_id: ObjectId | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one newest-first page of validated sales-order filters."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if customer_id is not None:
        query["customer_id"] = customer_id
    return [
        _sales_order_projection(document)
        for document in (
            database["sales_orders"]
            .find(query)
            .sort([("created_at", -1), ("_id", 1)])
            .skip(skip)
            .limit(limit)
        )
    ]


def count_sales_orders(
    database: Database[Any],
    *,
    status: str | None,
    customer_id: ObjectId | None,
) -> int:
    """Count orders matching the list filters."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if customer_id is not None:
        query["customer_id"] = customer_id
    return database["sales_orders"].count_documents(query)


def update_draft_sales_order(
    database: Database[Any],
    sales_order_id: ObjectId,
    *,
    customer: Mapping[str, Any],
    items: list[dict[str, Any]],
    subtotal: Any,
    discount_total: Any,
    tax_total: Any,
    grand_total: Any,
) -> dict[str, Any] | None:
    """Update an order only while its status remains Draft."""
    changes = {
        "customer_id": customer["_id"],
        "customer_snapshot": {
            "code": customer["code"],
            "name": customer["name"],
            "email": customer.get("email"),
            "billing_address": customer.get("billing_address"),
            "shipping_address": customer.get("shipping_address"),
        },
        "items": [
            {
                **item,
                "unit_price": to_decimal128(item["unit_price"]),
                "discount_percent": to_decimal128(item["discount_percent"]),
                "tax_percent": to_decimal128(item["tax_percent"]),
                "line_subtotal": to_decimal128(item["line_subtotal"]),
                "line_tax": to_decimal128(item["line_tax"]),
                "line_total": to_decimal128(item["line_total"]),
            }
            for item in items
        ],
        "subtotal": to_decimal128(subtotal),
        "discount_total": to_decimal128(discount_total),
        "tax_total": to_decimal128(tax_total),
        "grand_total": to_decimal128(grand_total),
        "updated_at": utc_now(),
    }
    return database["sales_orders"].find_one_and_update(
        {"_id": sales_order_id, "status": "draft"},
        {"$set": changes},
        return_document=ReturnDocument.AFTER,
    )


def transition_sales_order(
    database: Database[Any],
    session: Any,
    sales_order_id: ObjectId,
    *,
    expected_status: str,
    next_status: str,
    actor_id: ObjectId,
) -> Any:
    """Conditionally change order status and append history in one update."""
    now = utc_now()
    return database["sales_orders"].update_one(
        {"_id": sales_order_id, "status": expected_status},
        {
            "$set": {"status": next_status, "updated_at": now},
            "$push": {
                "status_history": {
                    "status": next_status,
                    "by": actor_id,
                    "at": now,
                    "note": None,
                }
            },
        },
        session=session,
    )


def public_sales_order(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project public order fields and its stable identifier."""
    return {
        "id": document["_id"],
        **{
            field: document[field]
            for field in SALES_ORDER_RESPONSE_FIELDS
            if field in document
        },
    }


def _sales_order_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a sales-order collection document for list/detail responses."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in SALES_ORDER_RESPONSE_FIELDS
            if field in document
        },
    }
