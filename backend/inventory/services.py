"""Product catalogue business rules and response serialization."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from bson import ObjectId
from django.conf import settings
from pymongo.client_session import ClientSession
from pymongo.database import Database

from common.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationFailed,
)
from common.idempotency import execute_idempotent
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from common.time import utc_now
from inventory.repository import (
    apply_stock_update,
    count_products,
    count_stock_movements,
    create_product as insert_product,
    find_active_product,
    find_product_by_id,
    find_product_by_sku,
    insert_stock_movement,
    list_product_categories,
    list_stock_movements as list_stock_movement_records,
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


def _public_stock_movement(document: Mapping[str, Any]) -> dict[str, Any]:
    """Convert a movement document to the public JSON-safe response shape."""
    return serialize_document(
        {
            "id": document["_id"],
            **{key: value for key, value in document.items() if key != "_id"},
        }
    )


def apply_stock_change(
    session: ClientSession,
    product_id: ObjectId | str,
    quantity_delta: int,
    reserved_delta: int,
    movement_type: str,
    reason: str,
    reference_type: str,
    reference_id: ObjectId | str,
    user_id: ObjectId | str,
) -> dict[str, Any]:
    """Atomically update product stock and append its movement in one transaction."""
    integer_deltas = (quantity_delta, reserved_delta)
    if any(
        isinstance(delta, bool) or not isinstance(delta, int)
        for delta in integer_deltas
    ):
        raise ValueError("Stock deltas must be integers.")
    if quantity_delta == 0 and reserved_delta == 0:
        raise ValueError("A stock change must include a non-zero delta.")
    if movement_type not in {
        "purchase_receipt",
        "sale_fulfilment",
        "sale_return",
        "adjustment",
        "reservation",
        "reservation_release",
    }:
        raise ValueError("Stock movement type is not supported.")
    if not isinstance(reason, str) or len(reason.strip()) < 3 or len(reason) > 500:
        raise ValueError("Stock movement reason must contain 3 to 500 characters.")
    if not isinstance(reference_type, str) or not reference_type.strip():
        raise ValueError("Stock movement reference type is required.")

    product_object_id = parse_object_id(product_id)
    reference_object_id = parse_object_id(reference_id)
    performer_object_id = parse_object_id(user_id)

    if movement_type == "sale_fulfilment" and (
        quantity_delta >= 0 or reserved_delta != quantity_delta
    ):
        raise ValueError(
            "Sale fulfilment must decrease on-hand and reserved quantities equally."
        )
    if movement_type == "reservation_release" and (
        quantity_delta != 0 or reserved_delta >= 0
    ):
        raise ValueError("Reservation release must only reduce reserved quantity.")
    if movement_type == "reservation" and (
        quantity_delta != 0 or reserved_delta <= 0
    ):
        raise ValueError("Reservation must only increase reserved quantity.")
    if movement_type == "adjustment" and reserved_delta != 0:
        raise ValueError("Stock adjustments cannot change reserved quantity.")
    if movement_type in {"purchase_receipt", "sale_return"} and (
        quantity_delta <= 0 or reserved_delta != 0
    ):
        raise ValueError(
            "Receipts and returns must only increase on-hand quantity."
        )

    database = session.client[settings.MONGO_DB_NAME]
    product = apply_stock_update(
        database,
        session,
        product_id=product_object_id,
        quantity_delta=quantity_delta,
        reserved_delta=reserved_delta,
        movement_type=movement_type,
    )
    quantity_after = product["quantity_on_hand"]
    quantity_before = quantity_after - quantity_delta
    movement = insert_stock_movement(
        database,
        session,
        movement={
            "product_id": product_object_id,
            "movement_type": movement_type,
            "quantity_change": quantity_delta,
            "reserved_change": reserved_delta,
            "quantity_before": quantity_before,
            "quantity_after": quantity_after,
            "reason": reason.strip(),
            "reference_type": reference_type.strip(),
            "reference_id": reference_object_id,
            "performed_by": performer_object_id,
            "created_at": utc_now(),
        },
    )
    return movement


def adjust_stock(
    database: Database[Any],
    *,
    product_id: ObjectId | str,
    quantity_change: int,
    reason: str,
    user_id: ObjectId | str,
    idempotency_key: str,
) -> dict[str, Any]:
    """Apply a stock adjustment and persist its replay response transactionally."""
    parsed_product_id = parse_object_id(product_id)
    parsed_user_id = parse_object_id(user_id)
    if isinstance(quantity_change, bool) or not isinstance(quantity_change, int):
        raise ValidationFailed(
            "quantity_change must be a non-zero integer.",
            details={"quantity_change": "Must be a non-zero integer."},
        )
    if quantity_change == 0:
        raise ValidationFailed(
            "quantity_change must be a non-zero integer.",
            details={"quantity_change": "Must not be zero."},
        )

    request_body = {
        "product_id": parsed_product_id,
        "quantity_change": quantity_change,
        "reason": reason,
    }

    def operation(session: ClientSession, operation_id: ObjectId) -> dict[str, Any]:
        movement = apply_stock_change(
            session,
            parsed_product_id,
            quantity_change,
            0,
            "adjustment",
            reason,
            "stock_adjustment",
            operation_id,
            parsed_user_id,
        )
        return {"stock_movement": _public_stock_movement(movement)}

    return execute_idempotent(
        database,
        user_id=parsed_user_id,
        endpoint="/api/stock-adjustments/",
        key=idempotency_key,
        request_body=request_body,
        operation=operation,
    )


def list_stock_movements(
    database: Database[Any],
    *,
    product_id: ObjectId | None,
    movement_type: str | None,
    start_date: datetime | None,
    end_date: datetime | None,
    user_id: ObjectId | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return a paginated, newest-first stock movement history."""
    filters = {
        "product_id": product_id,
        "movement_type": movement_type,
        "start_date": start_date,
        "end_date": end_date,
        "user_id": user_id,
    }
    movements = list_stock_movement_records(
        database,
        **filters,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_stock_movements(database, **filters)
    return (
        [_public_stock_movement(movement) for movement in movements],
        pagination.build_meta(total),
    )
