"""PyMongo data access for product catalogue records."""

from collections.abc import Mapping
from datetime import datetime
import re
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

from common.exceptions import InsufficientStock
from common.mongo import count_query_matches
from common.money import to_decimal128
from common.object_id import parse_object_id
from common.time import utc_now

PRODUCT_SORT_FIELDS = frozenset(
    {
        "sku",
        "name",
        "category",
        "unit",
        "cost_price",
        "selling_price",
        "quantity_on_hand",
        "reserved_quantity",
        "min_stock_level",
        "is_active",
        "created_at",
        "updated_at",
    }
)
_PRODUCT_UPDATE_FIELDS = frozenset(
    {
        "name",
        "description",
        "category",
        "unit",
        "cost_price",
        "selling_price",
        "min_stock_level",
        "is_active",
    }
)
_PRODUCT_RESPONSE_FIELDS = (
    "sku",
    "name",
    "description",
    "category",
    "unit",
    "cost_price",
    "selling_price",
    "quantity_on_hand",
    "reserved_quantity",
    "min_stock_level",
    "is_active",
    "created_at",
    "updated_at",
)


def normalize_sku(sku: str) -> str:
    """Normalize SKUs for case-insensitive uniqueness."""
    normalized = sku.strip().upper()
    if not normalized:
        raise ValueError("SKU must not be empty.")
    return normalized


def normalize_product_name(name: str) -> str:
    """Create a stable, case-insensitive product-name search value."""
    normalized = name.strip().casefold()
    if not normalized:
        raise ValueError("Product name must not be empty.")
    return normalized


def create_product(
    database: Database[Any],
    *,
    sku: str,
    name: str,
    description: str | None,
    category: str,
    unit: str,
    cost_price: Any,
    selling_price: Any,
    min_stock_level: int,
    is_active: bool,
) -> dict[str, Any]:
    """Insert a product with service-owned zero stock and UTC timestamps."""
    now = utc_now()
    document: dict[str, Any] = {
        "sku": normalize_sku(sku),
        "name": name.strip(),
        "name_search": normalize_product_name(name),
        "description": description,
        "category": category.strip(),
        "unit": unit.strip(),
        "cost_price": to_decimal128(cost_price),
        "selling_price": to_decimal128(selling_price),
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "min_stock_level": min_stock_level,
        "available_quantity": 0,
        "is_low_stock": min_stock_level >= 0,
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
    }
    result = database["products"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_product_by_id(
    database: Database[Any],
    product_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a product using a validated ObjectId."""
    return database["products"].find_one(
        {"_id": parse_object_id(product_id)}
    )


def find_product_by_sku(database: Database[Any], sku: str) -> dict[str, Any] | None:
    """Find a product by normalized SKU."""
    return database["products"].find_one({"sku": normalize_sku(sku)})


def find_active_product(
    database: Database[Any],
    product_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a product that may be referenced by a new order."""
    return database["products"].find_one(
        {"_id": parse_object_id(product_id), "is_active": True}
    )


def _product_list_query(
    *,
    search: str | None,
    category: str | None,
    is_active: bool | None,
    low_stock: bool | None,
) -> dict[str, Any]:
    """Build a Mongo query only from validated product list filters."""
    query: dict[str, Any] = {}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"sku": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
        ]
    if category is not None:
        query["category"] = category
    if is_active is not None:
        query["is_active"] = is_active
    if low_stock is not None:
        query["is_low_stock"] = low_stock
    return query


def list_products(
    database: Database[Any],
    *,
    search: str | None,
    category: str | None,
    is_active: bool | None,
    low_stock: bool | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one page of products matching validated filters."""
    if sort_by is not None and sort_by not in PRODUCT_SORT_FIELDS:
        raise ValueError("Product sort field is not allowed.")
    field = "name_search" if sort_by == "name" else sort_by
    sort_fields = (
        [(field, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if field is not None
        else [("created_at", -1), ("_id", 1)]
    )
    return list(
        database["products"]
        .find(
            _product_list_query(
                search=search,
                category=category,
                is_active=is_active,
                low_stock=low_stock,
            )
        )
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )


def count_products(
    database: Database[Any],
    *,
    search: str | None,
    category: str | None,
    is_active: bool | None,
    low_stock: bool | None,
) -> int:
    """Count products matching the same validated filters as the list query."""
    return count_query_matches(
        database["products"],
        _product_list_query(
            search=search,
            category=category,
            is_active=is_active,
            low_stock=low_stock,
        )
    )


def list_product_categories(database: Database[Any]) -> list[str]:
    """Return sorted distinct non-empty product categories."""
    categories = database["products"].distinct("category")
    return sorted(
        category
        for category in categories
        if isinstance(category, str) and category.strip()
    )


def update_product(
    database: Database[Any],
    product_id: ObjectId | str,
    updates: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Update an allowlisted set of product fields, never inventory quantities."""
    if not updates or any(
        not isinstance(field, str)
        or field.startswith("$")
        or "." in field
        or field not in _PRODUCT_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Product update contains an unsupported field.")

    changes = dict(updates)
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        changes["name_search"] = normalize_product_name(changes["name"])
    if "category" in changes:
        changes["category"] = changes["category"].strip()
    if "unit" in changes:
        changes["unit"] = changes["unit"].strip()
    for field in ("cost_price", "selling_price"):
        if field in changes:
            changes[field] = to_decimal128(changes[field])
    changes["updated_at"] = utc_now()

    parsed_id = parse_object_id(product_id)
    while True:
        current = find_product_by_id(database, parsed_id)
        if current is None:
            return None
        available_quantity = (
            current["quantity_on_hand"] - current["reserved_quantity"]
        )
        min_stock_level = changes.get(
            "min_stock_level",
            current["min_stock_level"],
        )
        updated = database["products"].find_one_and_update(
            {
                "_id": parsed_id,
                "quantity_on_hand": current["quantity_on_hand"],
                "reserved_quantity": current["reserved_quantity"],
                "min_stock_level": current["min_stock_level"],
            },
            {
                "$set": {
                    **changes,
                    "available_quantity": available_quantity,
                    "is_low_stock": available_quantity <= min_stock_level,
                }
            },
            return_document=ReturnDocument.AFTER,
        )
        if updated is not None:
            return updated


def public_product_fields(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project a product without its internal normalized search value."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in _PRODUCT_RESPONSE_FIELDS
            if field in document
        },
    }


def apply_stock_update(
    database: Database[Any],
    session: ClientSession,
    *,
    product_id: ObjectId,
    quantity_delta: int,
    reserved_delta: int,
    movement_type: str,
) -> dict[str, Any]:
    """Atomically update product stock using availability-specific conditions."""
    query: dict[str, Any] = {"_id": product_id}
    if movement_type == "sale_fulfilment":
        quantity = abs(quantity_delta)
        query["quantity_on_hand"] = {"$gte": quantity}
        query["reserved_quantity"] = {"$gte": quantity}
    elif movement_type == "reservation_release":
        query["reserved_quantity"] = {"$gte": abs(reserved_delta)}
    else:
        if movement_type == "reservation":
            query["is_active"] = True
        available_required = max(0, -quantity_delta) + max(0, reserved_delta)
        if available_required:
            query["$expr"] = {
                "$gte": [
                    {
                        "$subtract": [
                            "$quantity_on_hand",
                            "$reserved_quantity",
                        ]
                    },
                    available_required,
                ]
            }
        if reserved_delta < 0:
            query["reserved_quantity"] = {"$gte": abs(reserved_delta)}

    updated = database["products"].find_one_and_update(
        query,
        {
            "$inc": {
                "quantity_on_hand": quantity_delta,
                "reserved_quantity": reserved_delta,
            },
            "$set": {"updated_at": utc_now()},
        },
        return_document=ReturnDocument.AFTER,
        session=session,
    )
    if updated is None:
        raise InsufficientStock()
    available_quantity = (
        updated["quantity_on_hand"] - updated["reserved_quantity"]
    )
    updated["available_quantity"] = available_quantity
    updated["is_low_stock"] = available_quantity <= updated["min_stock_level"]
    database["products"].update_one(
        {"_id": product_id},
        {
            "$set": {
                "available_quantity": available_quantity,
                "is_low_stock": updated["is_low_stock"],
            }
        },
        session=session,
    )
    return updated


def insert_stock_movement(
    database: Database[Any],
    session: ClientSession,
    *,
    movement: dict[str, Any],
) -> dict[str, Any]:
    """Insert a stock movement within the stock update's transaction."""
    result = database["stock_movements"].insert_one(movement, session=session)
    return {"_id": result.inserted_id, **movement}


def _stock_movement_query(
    *,
    product_id: ObjectId | None,
    movement_type: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    user_id: ObjectId | None,
) -> dict[str, Any]:
    """Build a stock movement query from serializer-validated filters."""
    query: dict[str, Any] = {}
    if product_id is not None:
        query["product_id"] = product_id
    if movement_type is not None:
        query["movement_type"] = movement_type
    if user_id is not None:
        query["performed_by"] = user_id
    if start_date is not None or end_date is not None:
        created_at: dict[str, Any] = {}
        if start_date is not None:
            created_at["$gte"] = start_date
        if end_date is not None:
            created_at["$lte"] = end_date
        query["created_at"] = created_at
    return query


def list_stock_movements(
    database: Database[Any],
    *,
    product_id: ObjectId | None,
    movement_type: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    user_id: ObjectId | None,
    skip: int,
    limit: int,
) -> list[dict[str, Any]]:
    """Return one newest-first page of matching immutable stock movements."""
    return list(
        database["stock_movements"]
        .find(
            _stock_movement_query(
                product_id=product_id,
                movement_type=movement_type,
                start_date=start_date,
                end_date=end_date,
                user_id=user_id,
            )
        )
        .sort([("created_at", -1), ("_id", -1)])
        .skip(skip)
        .limit(limit)
    )


def count_stock_movements(
    database: Database[Any],
    *,
    product_id: ObjectId | None,
    movement_type: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    user_id: ObjectId | None,
) -> int:
    """Count movements matching the same validated filters as the list query."""
    return count_query_matches(
        database["stock_movements"],
        _stock_movement_query(
            product_id=product_id,
            movement_type=movement_type,
            start_date=start_date,
            end_date=end_date,
            user_id=user_id,
        )
    )
