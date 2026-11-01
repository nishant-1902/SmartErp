"""Supplier business rules and response serialization."""

from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.exceptions import ConflictError, NotFoundError, ValidationFailed
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from suppliers.repository import (
    count_supplier_purchase_orders,
    count_suppliers,
    create_supplier as insert_supplier,
    find_active_supplier_by_id,
    find_supplier_by_code,
    find_supplier_by_id,
    list_supplier_purchase_orders as list_purchase_order_records,
    list_suppliers as list_supplier_records,
    public_supplier,
    update_supplier as update_supplier_record,
)


def _public_supplier(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a supplier record to its JSON-safe public representation."""
    supplier = public_supplier(document)
    supplier["id"] = supplier.pop("_id")
    return serialize_document(supplier)


def _check_unique_code(
    database: Database[Any],
    code: str,
    *,
    exclude_id: ObjectId | None = None,
) -> None:
    """Reject a supplier code already assigned to another supplier."""
    existing = find_supplier_by_code(database, code)
    if existing is not None and existing.get("_id") != exclude_id:
        raise ConflictError(
            "Supplier code already exists.",
            details={"code": "Must be unique."},
        )


def create_supplier(
    database: Database[Any],
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Create a supplier with a generated code when the caller omits one."""
    if values.get("code") is not None:
        _check_unique_code(database, values["code"])
    else:
        values["code"] = None
    supplier = insert_supplier(database, **values)
    return _public_supplier(supplier)


def get_supplier(
    database: Database[Any],
    supplier_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one supplier or raise a safe not-found error."""
    supplier = find_supplier_by_id(database, supplier_id)
    if supplier is None:
        raise NotFoundError("Supplier was not found.")
    return _public_supplier(supplier)


def list_suppliers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List matching suppliers with validated pagination metadata."""
    suppliers = list_supplier_records(
        database,
        search=search,
        status=status,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_suppliers(database, search=search, status=status)
    return (
        [_public_supplier(supplier) for supplier in suppliers],
        pagination.build_meta(total),
    )


def update_supplier(
    database: Database[Any],
    supplier_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update supplier fields after checking identity and unique code."""
    parsed_id = parse_object_id(supplier_id)
    if find_supplier_by_id(database, parsed_id) is None:
        raise NotFoundError("Supplier was not found.")
    if "code" in values:
        _check_unique_code(database, values["code"], exclude_id=parsed_id)
    supplier = update_supplier_record(database, parsed_id, values)
    if supplier is None:
        raise NotFoundError("Supplier was not found.")
    return _public_supplier(supplier)


def require_active_supplier(
    database: Database[Any],
    supplier_id: ObjectId | str,
) -> dict[str, Any]:
    """Require a supplier to exist and be active before creating a purchase order."""
    parsed_id = parse_object_id(supplier_id)
    supplier = find_active_supplier_by_id(database, parsed_id)
    if supplier is not None:
        return supplier
    if find_supplier_by_id(database, parsed_id) is None:
        raise NotFoundError("Supplier was not found.")
    raise ValidationFailed(
        "Inactive suppliers cannot be used for new purchase orders.",
        details={"supplier_id": "Supplier is inactive."},
    )


def list_supplier_purchase_orders(
    database: Database[Any],
    supplier_id: ObjectId | str,
    *,
    pagination: Pagination,
) -> tuple[
    list[dict[str, Any]],
    list[dict[str, Any]],
    dict[str, dict[str, int]],
]:
    """Return paginated purchase history and outstanding orders for a supplier."""
    parsed_id = parse_object_id(supplier_id)
    if find_supplier_by_id(database, parsed_id) is None:
        raise NotFoundError("Supplier was not found.")

    history = list_purchase_order_records(
        database,
        parsed_id,
        outstanding_only=False,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    outstanding = list_purchase_order_records(
        database,
        parsed_id,
        outstanding_only=True,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    history_meta = pagination.build_meta(
        count_supplier_purchase_orders(
            database,
            parsed_id,
            outstanding_only=False,
        )
    )
    outstanding_meta = pagination.build_meta(
        count_supplier_purchase_orders(
            database,
            parsed_id,
            outstanding_only=True,
        )
    )
    history_records = [
        serialize_document({"id": order.pop("_id"), **order})
        for order in history
    ]
    outstanding_records = [
        serialize_document({"id": order.pop("_id"), **order})
        for order in outstanding
    ]
    return (
        history_records,
        outstanding_records,
        {
            "purchase_orders": history_meta,
            "outstanding_purchase_orders": outstanding_meta,
        },
    )
