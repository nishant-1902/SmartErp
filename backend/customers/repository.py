"""PyMongo data access for customer records and sales-order history."""

from collections.abc import Mapping
import re
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.money import to_decimal128
from common.mongo import count_query_matches
from common.object_id import parse_object_id
from common.time import utc_now

CUSTOMER_SORT_FIELDS = frozenset(
    {"code", "name", "email", "phone", "status", "created_at", "updated_at"}
)
CUSTOMER_RESPONSE_FIELDS = (
    "code",
    "name",
    "email",
    "phone",
    "billing_address",
    "shipping_address",
    "tax_id",
    "status",
    "credit_limit",
    "created_at",
    "updated_at",
)
CUSTOMER_UPDATE_FIELDS = frozenset(CUSTOMER_RESPONSE_FIELDS) - {
    "created_at",
    "updated_at",
}
SALES_ORDER_RESPONSE_FIELDS = (
    "order_number",
    "customer_id",
    "customer_snapshot",
    "items",
    "status",
    "return_status",
    "payment_status",
    "subtotal",
    "discount_total",
    "tax_total",
    "grand_total",
    "created_by",
    "created_at",
    "updated_at",
    "fulfilled_at",
    "status_history",
)


def normalize_customer_code(code: str) -> str:
    """Normalize customer codes so case variants share one unique value."""
    normalized = code.strip().upper()
    if not normalized:
        raise ValueError("Customer code must not be empty.")
    return normalized


def _customer_list_query(search: str | None, status: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"code": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"phone": {"$regex": escaped, "$options": "i"}},
            {"tax_id": {"$regex": escaped, "$options": "i"}},
        ]
    if status is not None:
        query["status"] = status
    return query


def create_customer(
    database: Database[Any],
    *,
    code: str,
    name: str,
    email: str | None,
    phone: str | None,
    billing_address: dict[str, Any] | None,
    shipping_address: dict[str, Any] | None,
    tax_id: str | None,
    status: str,
    credit_limit: Any,
) -> dict[str, Any]:
    """Insert a normalized customer with UTC timestamps and BSON money."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Customer name must not be empty.")
    if status not in {"active", "inactive"}:
        raise ValueError("Customer status is not supported.")
    now = utc_now()
    document: dict[str, Any] = {
        "code": normalize_customer_code(code),
        "name": normalized_name,
        "name_search": normalized_name.casefold(),
        "email": email.strip().lower() or None if email is not None else None,
        "phone": phone,
        "billing_address": billing_address,
        "shipping_address": shipping_address,
        "tax_id": tax_id.strip().upper() or None if tax_id is not None else None,
        "status": status,
        "credit_limit": (
            to_decimal128(credit_limit) if credit_limit is not None else None
        ),
        "created_at": now,
        "updated_at": now,
    }
    result = database["customers"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_customer_by_id(
    database: Database[Any],
    customer_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a customer by a validated ObjectId."""
    return database["customers"].find_one({"_id": parse_object_id(customer_id)})


def find_customer_by_code(database: Database[Any], code: str) -> dict[str, Any] | None:
    """Find a customer by normalized code."""
    return database["customers"].find_one({"code": normalize_customer_code(code)})


def find_customer_by_tax_id(
    database: Database[Any],
    tax_id: str,
) -> dict[str, Any] | None:
    """Find a customer by normalized tax identifier."""
    return database["customers"].find_one({"tax_id": tax_id.strip().upper()})


def list_customers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one safe page of matching customers."""
    if sort_by is not None and sort_by not in CUSTOMER_SORT_FIELDS:
        raise ValueError("Customer sort field is not allowed.")
    sort_field = "name_search" if sort_by == "name" else sort_by
    sort_fields = (
        [(sort_field, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if sort_field is not None
        else [("created_at", -1), ("_id", 1)]
    )
    cursor = (
        database["customers"]
        .find(_customer_list_query(search, status))
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )
    return [_customer_projection(document) for document in cursor]


def count_customers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
) -> int:
    """Count customers matching the same validated list filters."""
    return count_query_matches(
        database["customers"],
        _customer_list_query(search, status),
    )


def update_customer(
    database: Database[Any],
    customer_id: ObjectId | str,
    updates: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Update an allowlisted customer field set and return the updated record."""
    if not updates or any(
        not isinstance(field, str)
        or field.startswith("$")
        or "." in field
        or field not in CUSTOMER_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Customer update contains an unsupported field.")

    changes = dict(updates)
    if "code" in changes:
        changes["code"] = normalize_customer_code(changes["code"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise ValueError("Customer name must not be empty.")
        changes["name_search"] = changes["name"].casefold()
    if "email" in changes and changes["email"] is not None:
        changes["email"] = changes["email"].strip().lower() or None
    if "tax_id" in changes and changes["tax_id"] is not None:
        changes["tax_id"] = changes["tax_id"].strip().upper() or None
    if "credit_limit" in changes:
        changes["credit_limit"] = (
            to_decimal128(changes["credit_limit"])
            if changes["credit_limit"] is not None
            else None
        )
    changes["updated_at"] = utc_now()
    database["customers"].update_one(
        {"_id": parse_object_id(customer_id)},
        {"$set": changes},
    )
    return find_customer_by_id(database, customer_id)


def list_customer_sales_orders(
    database: Database[Any],
    customer_id: ObjectId | str,
    *,
    status: str | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one page of a customer's sales-order history."""
    query: dict[str, Any] = {"customer_id": parse_object_id(customer_id)}
    if status is not None:
        query["status"] = status
    cursor = (
        database["sales_orders"]
        .find(query)
        .sort([("created_at", -1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )
    return [_sales_order_projection(order) for order in cursor]


def count_customer_sales_orders(
    database: Database[Any],
    customer_id: ObjectId | str,
    *,
    status: str | None,
) -> int:
    """Count a customer's sales orders using the same filter as the list query."""
    query: dict[str, Any] = {"customer_id": parse_object_id(customer_id)}
    if status is not None:
        query["status"] = status
    return count_query_matches(database["sales_orders"], query)


def _customer_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project only public customer fields and the stable public ID."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in CUSTOMER_RESPONSE_FIELDS
            if field in document
        },
    }


def public_customer(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return only public fields for one customer."""
    return _customer_projection(document)


def _sales_order_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project the documented sales-order fields for customer history."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in SALES_ORDER_RESPONSE_FIELDS
            if field in document
        },
    }
