"""PyMongo data access for supplier records and purchase history."""

from collections.abc import Mapping
import re
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from common.object_id import parse_object_id
from common.time import utc_now

SUPPLIER_SORT_FIELDS = frozenset(
    {
        "code",
        "name",
        "contact_person",
        "email",
        "status",
        "created_at",
        "updated_at",
    }
)
SUPPLIER_RESPONSE_FIELDS = (
    "code",
    "name",
    "contact_person",
    "email",
    "phone",
    "address",
    "status",
    "payment_terms",
    "created_at",
    "updated_at",
)
SUPPLIER_UPDATE_FIELDS = frozenset(
    {
        "code",
        "name",
        "contact_person",
        "email",
        "phone",
        "address",
        "status",
        "payment_terms",
    }
)
PURCHASE_ORDER_RESPONSE_FIELDS = (
    "po_number",
    "supplier_id",
    "supplier_snapshot",
    "items",
    "status",
    "tax_rate",
    "subtotal",
    "tax_total",
    "grand_total",
    "created_by",
    "approved_by",
    "status_history",
    "created_at",
    "updated_at",
)
OUTSTANDING_PURCHASE_ORDER_STATUSES = frozenset(
    {"pending_approval", "approved", "partially_received"}
)


def normalize_supplier_code(code: str) -> str:
    """Normalize supplier codes so case variants share one unique value."""
    normalized = code.strip().upper()
    if not normalized:
        raise ValueError("Supplier code must not be empty.")
    return normalized


def allocate_supplier_code(database: Database[Any]) -> str:
    """Atomically allocate the next human-readable supplier code."""
    while True:
        now = utc_now()
        try:
            counter = database["counters"].find_one_and_update(
                {"_id": "supplier_code"},
                {
                    "$inc": {"value": 1},
                    "$set": {"updated_at": now},
                },
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
        except DuplicateKeyError:
            counter = database["counters"].find_one_and_update(
                {"_id": "supplier_code"},
                {
                    "$inc": {"value": 1},
                    "$set": {"updated_at": now},
                },
                return_document=ReturnDocument.AFTER,
            )
        if (
            counter is None
            or not isinstance(counter.get("value"), int)
            or isinstance(counter.get("value"), bool)
        ):
            raise RuntimeError("Supplier code counter did not return a valid value.")
        return f"SUP-{counter['value']:06d}"


def _supplier_list_query(search: str | None, status: str | None) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"code": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
            {"contact_person": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"phone": {"$regex": escaped, "$options": "i"}},
        ]
    if status is not None:
        query["status"] = status
    return query


def create_supplier(
    database: Database[Any],
    *,
    code: str | None,
    name: str,
    contact_person: str | None,
    email: str | None,
    phone: str | None,
    address: dict[str, Any] | None,
    status: str,
    payment_terms: str | None,
) -> dict[str, Any]:
    """Insert a normalized supplier with UTC timestamps."""
    normalized_name = name.strip()
    if not normalized_name:
        raise ValueError("Supplier name must not be empty.")
    if status not in {"active", "inactive"}:
        raise ValueError("Supplier status is not supported.")

    normalized_code = normalize_supplier_code(code) if code is not None else None
    if normalized_code is None:
        normalized_code = allocate_supplier_code(database)
        while find_supplier_by_code(database, normalized_code) is not None:
            normalized_code = allocate_supplier_code(database)

    now = utc_now()
    document: dict[str, Any] = {
        "code": normalized_code,
        "name": normalized_name,
        "name_search": normalized_name.casefold(),
        "contact_person": (
            contact_person.strip() or None if contact_person is not None else None
        ),
        "email": email.strip().lower() or None if email is not None else None,
        "phone": phone,
        "address": address,
        "status": status,
        "payment_terms": (
            payment_terms.strip() or None if payment_terms is not None else None
        ),
        "created_at": now,
        "updated_at": now,
    }
    result = database["suppliers"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_supplier_by_id(
    database: Database[Any],
    supplier_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a supplier by a validated ObjectId."""
    return database["suppliers"].find_one({"_id": parse_object_id(supplier_id)})


def find_active_supplier_by_id(
    database: Database[Any],
    supplier_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a supplier only when its status is active."""
    return database["suppliers"].find_one(
        {"_id": parse_object_id(supplier_id), "status": "active"}
    )


def find_supplier_by_code(database: Database[Any], code: str) -> dict[str, Any] | None:
    """Find a supplier by its normalized unique code."""
    return database["suppliers"].find_one({"code": normalize_supplier_code(code)})


def list_suppliers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one safe page of suppliers matching validated filters."""
    if sort_by is not None and sort_by not in SUPPLIER_SORT_FIELDS:
        raise ValueError("Supplier sort field is not allowed.")
    sort_field = "name_search" if sort_by == "name" else sort_by
    sort_fields = (
        [(sort_field, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if sort_field is not None
        else [("created_at", -1), ("_id", 1)]
    )
    cursor = (
        database["suppliers"]
        .find(_supplier_list_query(search, status))
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )
    return [_supplier_projection(document) for document in cursor]


def count_suppliers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
) -> int:
    """Count suppliers matching the same validated list filters."""
    return database["suppliers"].count_documents(_supplier_list_query(search, status))


def update_supplier(
    database: Database[Any],
    supplier_id: ObjectId | str,
    updates: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Update an allowlisted supplier field set and return the updated record."""
    if not updates or any(
        not isinstance(field, str)
        or field.startswith("$")
        or "." in field
        or field not in SUPPLIER_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Supplier update contains an unsupported field.")

    changes = dict(updates)
    if "code" in changes:
        changes["code"] = normalize_supplier_code(changes["code"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        if not changes["name"]:
            raise ValueError("Supplier name must not be empty.")
        changes["name_search"] = changes["name"].casefold()
    if "email" in changes and changes["email"] is not None:
        changes["email"] = changes["email"].strip().lower() or None
    for field in ("contact_person", "payment_terms"):
        if field in changes and changes[field] is not None:
            changes[field] = changes[field].strip() or None
    changes["updated_at"] = utc_now()
    database["suppliers"].update_one(
        {"_id": parse_object_id(supplier_id)},
        {"$set": changes},
    )
    return find_supplier_by_id(database, supplier_id)


def _supplier_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project only public supplier fields and the stable public ID."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in SUPPLIER_RESPONSE_FIELDS
            if field in document
        },
    }


def public_supplier(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return the public fields for one supplier record."""
    return _supplier_projection(document)


def list_supplier_purchase_orders(
    database: Database[Any],
    supplier_id: ObjectId | str,
    *,
    outstanding_only: bool,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return a paginated purchase-order history or its open subset."""
    query: dict[str, Any] = {"supplier_id": parse_object_id(supplier_id)}
    if outstanding_only:
        query["status"] = {"$in": sorted(OUTSTANDING_PURCHASE_ORDER_STATUSES)}
    cursor = (
        database["purchase_orders"]
        .find(query)
        .sort([("created_at", -1), ("_id", 1)])
        .skip(skip)
        .limit(limit)
    )
    return [_purchase_order_projection(document) for document in cursor]


def count_supplier_purchase_orders(
    database: Database[Any],
    supplier_id: ObjectId | str,
    *,
    outstanding_only: bool,
) -> int:
    """Count a supplier's history or outstanding purchase orders."""
    query: dict[str, Any] = {"supplier_id": parse_object_id(supplier_id)}
    if outstanding_only:
        query["status"] = {"$in": sorted(OUTSTANDING_PURCHASE_ORDER_STATUSES)}
    return database["purchase_orders"].count_documents(query)


def _purchase_order_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project safe purchase-order fields and calculate remaining quantities."""
    order = {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in PURCHASE_ORDER_RESPONSE_FIELDS
            if field in document
        },
    }
    order["items"] = [
        {
            **item,
            "quantity_outstanding": (
                item["quantity_ordered"] - item["quantity_received"]
            ),
        }
        for item in order.get("items", [])
    ]
    return order
