"""Product catalogue business rules and response serialization."""

from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.exceptions import ConflictError, NotFoundError, ValidationFailed
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from inventory.repository import (
    count_products,
    create_product as insert_product,
    find_active_product,
    find_product_by_id,
    find_product_by_sku,
    list_product_categories,
    list_products as list_product_records,
    public_product_fields,
    update_product as update_product_record,
)


def _public_product(document: dict[str, Any]) -> dict[str, Any]:
    """Return only the public product fields as JSON-safe values."""
    fields = public_product_fields(document)
    return serialize_document(
        {
            "id": fields["_id"],
            **{key: value for key, value in fields.items() if key != "_id"},
        }
    )


def create_product(
    database: Database[Any],
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Create a product after checking normalized SKU uniqueness."""
    if find_product_by_sku(database, values["sku"]) is not None:
        raise ConflictError(
            "Product SKU already exists.",
            details={"sku": "Must be unique."},
        )
    return _public_product(insert_product(database, **values))


def get_product(
    database: Database[Any],
    product_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one product or a safe not-found error."""
    product = find_product_by_id(database, product_id)
    if product is None:
        raise NotFoundError("Product was not found.")
    return _public_product(product)


def list_products(
    database: Database[Any],
    *,
    search: str | None,
    category: str | None,
    is_active: bool | None,
    low_stock: bool | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List matching products with validated sorting and pagination."""
    products = list_product_records(
        database,
        search=search,
        category=category,
        is_active=is_active,
        low_stock=low_stock,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_products(
        database,
        search=search,
        category=category,
        is_active=is_active,
        low_stock=low_stock,
    )
    return [_public_product(product) for product in products], (
        pagination.build_meta(total)
    )


def list_categories(database: Database[Any]) -> list[str]:
    """Return distinct product categories for catalogue filters."""
    return list_product_categories(database)


def update_product(
    database: Database[Any],
    product_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update editable product details without changing its SKU or stock."""
    parsed_id = parse_object_id(product_id)
    if find_product_by_id(database, parsed_id) is None:
        raise NotFoundError("Product was not found.")
    updated = update_product_record(database, parsed_id, values)
    if updated is None:
        raise NotFoundError("Product was not found.")
    return _public_product(updated)


def get_active_product_for_order(
    database: Database[Any],
    product_id: ObjectId | str,
) -> dict[str, Any]:
    """Reject new-order references to missing or deactivated products."""
    product = find_active_product(database, product_id)
    if product is None:
        raise ValidationFailed(
            "Inactive products cannot be used on new orders.",
            details={"product_id": "Product is missing or inactive."},
        )
    return _public_product(product)
