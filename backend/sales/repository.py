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
    "paid_total",
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


def allocate_document_number(
    database: Database[Any],
    session: Any,
    *,
    counter_name: str,
    prefix: str,
    year: int,
) -> str:
    """Allocate a transaction-scoped yearly invoice or credit-note number."""
    counter_id = f"{counter_name}:{year}"
    while True:
        try:
            counter = database["counters"].find_one_and_update(
                {"_id": counter_id},
                {"$inc": {"value": 1}, "$set": {"updated_at": utc_now()}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
                session=session,
            )
        except DuplicateKeyError:
            counter = database["counters"].find_one_and_update(
                {"_id": counter_id},
                {"$inc": {"value": 1}, "$set": {"updated_at": utc_now()}},
                return_document=ReturnDocument.AFTER,
                session=session,
            )
        if (
            counter is None
            or not isinstance(counter.get("value"), int)
            or isinstance(counter.get("value"), bool)
        ):
            raise RuntimeError("Document counter did not return a valid value.")
        return f"{prefix}-{year}-{counter['value']:06d}"


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
        "paid_total": to_decimal128("0.00"),
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
    payment_status: str | None,
    customer_id: ObjectId | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one newest-first page of validated sales-order filters."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if payment_status is not None:
        query["payment_status"] = payment_status
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
    payment_status: str | None,
    customer_id: ObjectId | None,
) -> int:
    """Count orders matching the list filters."""
    query: dict[str, Any] = {}
    if status is not None:
        query["status"] = status
    if payment_status is not None:
        query["payment_status"] = payment_status
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
    fulfilled_at: Any = None,
) -> Any:
    """Conditionally change order status and append history in one update."""
    now = utc_now()
    changes: dict[str, Any] = {"status": next_status, "updated_at": now}
    if next_status == "fulfilled":
        changes["fulfilled_at"] = fulfilled_at or now
    return database["sales_orders"].update_one(
        {"_id": sales_order_id, "status": expected_status},
        {
            "$set": changes,
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


def insert_invoice(
    database: Database[Any],
    session: Any,
    *,
    invoice_id: ObjectId,
    invoice_number: str,
    order: Mapping[str, Any],
    issued_at: Any,
    due_date: Any,
) -> dict[str, Any]:
    """Insert an immutable invoice snapshot inside the fulfillment transaction."""
    document = {
        "_id": invoice_id,
        "invoice_number": invoice_number,
        "sales_order_id": order["_id"],
        "customer_id": order["customer_id"],
        "customer_snapshot": order["customer_snapshot"],
        "items": [
            {
                key: item[key]
                for key in (
                    "product_id",
                    "sku",
                    "name",
                    "quantity",
                    "unit_price",
                    "discount_percent",
                    "tax_percent",
                    "line_subtotal",
                    "line_tax",
                    "line_total",
                )
                if key in item
            }
            for item in order["items"]
        ],
        "subtotal": order["subtotal"],
        "discount_total": order["discount_total"],
        "tax_total": order["tax_total"],
        "grand_total": order["grand_total"],
        "issued_at": issued_at,
        "due_date": due_date,
        "created_at": issued_at,
    }
    database["invoices"].insert_one(document, session=session)
    return document


def find_invoice_by_id(
    database: Database[Any],
    invoice_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find an invoice by a validated ObjectId."""
    return database["invoices"].find_one({"_id": parse_object_id(invoice_id)})


def list_invoices(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one newest-first invoice page."""
    query: dict[str, Any] = {}
    if customer_id is not None:
        query["customer_id"] = customer_id
    if sales_order_id is not None:
        query["sales_order_id"] = sales_order_id
    return list(
        database["invoices"]
        .find(query)
        .sort([("issued_at", -1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )


def count_invoices(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
) -> int:
    """Count invoices matching the supplied validated filters."""
    query: dict[str, Any] = {}
    if customer_id is not None:
        query["customer_id"] = customer_id
    if sales_order_id is not None:
        query["sales_order_id"] = sales_order_id
    return database["invoices"].count_documents(query)


def insert_payment(
    database: Database[Any],
    session: Any,
    *,
    payment_id: ObjectId,
    order: Mapping[str, Any],
    amount: Any,
    method: str,
    reference: str | None,
    actor_id: ObjectId,
    now: Any,
) -> dict[str, Any]:
    """Insert a completed payment within the order-payment transaction."""
    document = {
        "_id": payment_id,
        "sales_order_id": order["_id"],
        "customer_id": order["customer_id"],
        "payment_reference": reference,
        "amount": to_decimal128(amount),
        "method": method,
        "status": "completed",
        "received_at": now,
        "created_by": actor_id,
        "created_at": now,
    }
    database["payments"].insert_one(document, session=session)
    return document


def update_paid_total(
    database: Database[Any],
    session: Any,
    *,
    order_id: ObjectId,
    expected_paid_total: Any,
    paid_total: Any,
    payment_status: str,
    now: Any,
) -> Any:
    """Compare-and-set the paid total and derived payment status."""
    expected = to_decimal128(expected_paid_total)
    query: dict[str, Any] = {"_id": order_id, "status": "fulfilled"}
    if expected_paid_total is None:
        query["paid_total"] = {"$exists": False}
    else:
        query["paid_total"] = expected
    return database["sales_orders"].update_one(
        query,
        {
            "$set": {
                "paid_total": to_decimal128(paid_total),
                "payment_status": payment_status,
                "updated_at": now,
            }
        },
        session=session,
    )


def list_payments(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
    method: str | None,
    status: str | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return a newest-first page of validated payment filters."""
    query: dict[str, Any] = {}
    if customer_id is not None:
        query["customer_id"] = customer_id
    if sales_order_id is not None:
        query["sales_order_id"] = sales_order_id
    if method is not None:
        query["method"] = method
    if status is not None:
        query["status"] = status
    return list(
        database["payments"]
        .find(query)
        .sort([("received_at", -1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )


def count_payments(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
    method: str | None,
    status: str | None,
) -> int:
    """Count payments matching the same validated filters."""
    query: dict[str, Any] = {}
    if customer_id is not None:
        query["customer_id"] = customer_id
    if sales_order_id is not None:
        query["sales_order_id"] = sales_order_id
    if method is not None:
        query["method"] = method
    if status is not None:
        query["status"] = status
    return database["payments"].count_documents(query)


def insert_sales_return(
    database: Database[Any],
    session: Any,
    *,
    return_id: ObjectId,
    credit_note_number: str,
    order: Mapping[str, Any],
    items: list[dict[str, Any]],
    reason: str,
    subtotal: Any,
    discount_total: Any,
    tax_total: Any,
    total: Any,
    actor_id: ObjectId,
    now: Any,
) -> dict[str, Any]:
    """Insert an auditable return and credit note in the stock transaction."""
    document = {
        "_id": return_id,
        "credit_note_number": credit_note_number,
        "sales_order_id": order["_id"],
        "customer_id": order["customer_id"],
        "customer_snapshot": order["customer_snapshot"],
        "items": [
            {
                **item,
                "unit_price": to_decimal128(item["unit_price"]),
                "discount_percent": to_decimal128(item["discount_percent"]),
                "tax_percent": to_decimal128(item["tax_percent"]),
                "line_subtotal": to_decimal128(item["line_subtotal"]),
                "line_discount": to_decimal128(item["line_discount"]),
                "line_tax": to_decimal128(item["line_tax"]),
                "line_total": to_decimal128(item["line_total"]),
            }
            for item in items
        ],
        "subtotal": to_decimal128(subtotal),
        "discount_total": to_decimal128(discount_total),
        "tax_total": to_decimal128(tax_total),
        "total": to_decimal128(total),
        "reason": reason,
        "created_by": actor_id,
        "created_at": now,
    }
    database["sales_returns"].insert_one(document, session=session)
    return document


def increment_returned_quantity(
    database: Database[Any],
    session: Any,
    *,
    order_id: ObjectId,
    product_id: ObjectId,
    quantity: int,
    max_returned_quantity: int,
) -> Any:
    """Increment one order line only if the return stays within fulfilled quantity."""
    return database["sales_orders"].update_one(
        {
            "_id": order_id,
            "status": "fulfilled",
            "items": {
                "$elemMatch": {
                    "product_id": product_id,
                    "returned_quantity": {
                        "$lte": max_returned_quantity
                    },
                }
            },
        },
        {"$inc": {"items.$.returned_quantity": quantity}},
        session=session,
    )


def initialize_returned_quantities(
    database: Database[Any],
    session: Any,
    order: Mapping[str, Any],
) -> bool:
    """Backfill return counters on legacy order lines before a fulfillment/return."""
    items = [
        {**item, "returned_quantity": item.get("returned_quantity", 0)}
        for item in order["items"]
    ]
    if items == order["items"]:
        return True
    result = database["sales_orders"].update_one(
        {"_id": order["_id"], "status": order["status"]},
        {"$set": {"items": items}},
        session=session,
    )
    return result.modified_count == 1


def update_return_status(
    database: Database[Any],
    session: Any,
    *,
    order_id: ObjectId,
    expected_status: str,
    return_status: str,
    now: Any,
) -> Any:
    """Update return status while preserving the Fulfilled order status."""
    return database["sales_orders"].update_one(
        {"_id": order_id, "status": expected_status},
        {"$set": {"return_status": return_status, "updated_at": now}},
        session=session,
    )


def public_invoice(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project public invoice data with its stable identifier."""
    return {
        "id": document["_id"],
        **{
            field: document[field]
            for field in (
                "invoice_number",
                "sales_order_id",
                "customer_id",
                "customer_snapshot",
                "items",
                "subtotal",
                "discount_total",
                "tax_total",
                "grand_total",
                "issued_at",
                "due_date",
                "created_at",
            )
            if field in document
        },
    }


def public_payment(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project public payment data with its stable identifier."""
    return {
        "id": document["_id"],
        **{
            field: document[field]
            for field in (
                "sales_order_id",
                "customer_id",
                "payment_reference",
                "amount",
                "method",
                "status",
                "received_at",
                "created_by",
                "created_at",
            )
            if field in document
        },
    }


def public_sales_return(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project public return and credit-note data."""
    return {
        "id": document["_id"],
        **{
            field: document[field]
            for field in (
                "credit_note_number",
                "sales_order_id",
                "customer_id",
                "customer_snapshot",
                "items",
                "subtotal",
                "discount_total",
                "tax_total",
                "total",
                "reason",
                "created_by",
                "created_at",
            )
            if field in document
        },
    }


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
