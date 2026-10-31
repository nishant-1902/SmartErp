"""PyMongo data access for product catalogue records."""

from collections.abc import Mapping
import re
from typing import Any

from bson import ObjectId
from pymongo.database import Database

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
        operator = "$lte" if low_stock else "$gt"
        query["$expr"] = {
            operator: [
                {"$subtract": ["$quantity_on_hand", "$reserved_quantity"]},
                "$min_stock_level",
            ]
        }
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
    return database["products"].count_documents(
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

    database["products"].update_one(
        {"_id": parse_object_id(product_id)},
        {"$set": changes},
    )
    return find_product_by_id(database, product_id)


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
