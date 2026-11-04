"""Customer business rules and response serialization."""

from typing import Any

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from common.exceptions import ConflictError, NotFoundError
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from customers.repository import (
    count_customer_sales_orders,
    count_customers,
    create_customer as insert_customer,
    find_customer_by_code,
    find_customer_by_id,
    find_customer_by_tax_id,
    list_customer_sales_orders as list_sales_order_records,
    list_customers as list_customer_records,
    public_customer,
    update_customer as update_customer_record,
)


def _public_customer(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a customer record to its JSON-safe public representation."""
    customer = public_customer(document)
    customer["id"] = customer.pop("_id")
    return serialize_document(customer)


def _check_unique_values(
    database: Database[Any],
    *,
    code: str | None = None,
    tax_id: str | None = None,
    exclude_id: ObjectId | None = None,
) -> None:
    """Reject a code or tax ID already assigned to another customer."""
    if code is not None:
        existing = find_customer_by_code(database, code)
        if existing is not None and existing.get("_id") != exclude_id:
            raise ConflictError(
                "Customer code already exists.",
                details={"code": "Must be unique."},
            )
    if tax_id is not None:
        existing = find_customer_by_tax_id(database, tax_id)
        if existing is not None and existing.get("_id") != exclude_id:
            raise ConflictError(
                "Customer tax ID already exists.",
                details={"tax_id": "Must be unique."},
            )


def create_customer(
    database: Database[Any],
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Create a customer after checking its unique identifiers."""
    _check_unique_values(
        database,
        code=values["code"],
        tax_id=values.get("tax_id"),
    )
    try:
        customer = insert_customer(database, **values)
    except DuplicateKeyError as exc:
        raise ConflictError(
            "Customer code or tax ID already exists.",
            details={"identifiers": "Customer code and tax ID must be unique."},
        ) from exc
    return _public_customer(customer)


def get_customer(
    database: Database[Any],
    customer_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one customer or raise a safe not-found error."""
    customer = find_customer_by_id(database, customer_id)
    if customer is None:
        raise NotFoundError("Customer was not found.")
    return _public_customer(customer)


def list_customers(
    database: Database[Any],
    *,
    search: str | None,
    status: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List matching customers with validated pagination metadata."""
    customers = list_customer_records(
        database,
        search=search,
        status=status,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_customers(database, search=search, status=status)
    return (
        [_public_customer(customer) for customer in customers],
        pagination.build_meta(total),
    )


def update_customer(
    database: Database[Any],
    customer_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update customer fields after checking identity and unique values."""
    parsed_id = parse_object_id(customer_id)
    if find_customer_by_id(database, parsed_id) is None:
        raise NotFoundError("Customer was not found.")
    _check_unique_values(
        database,
        code=values.get("code"),
        tax_id=values.get("tax_id"),
        exclude_id=parsed_id,
    )
    try:
        customer = update_customer_record(database, parsed_id, values)
    except DuplicateKeyError as exc:
        raise ConflictError(
            "Customer code or tax ID already exists.",
            details={"identifiers": "Customer code and tax ID must be unique."},
        ) from exc
    if customer is None:
        raise NotFoundError("Customer was not found.")
    return _public_customer(customer)


def list_customer_sales_orders(
    database: Database[Any],
    customer_id: ObjectId | str,
    *,
    status: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return paginated sales-order history for an existing customer."""
    parsed_id = parse_object_id(customer_id)
    if find_customer_by_id(database, parsed_id) is None:
        raise NotFoundError("Customer was not found.")
    orders = list_sales_order_records(
        database,
        parsed_id,
        status=status,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_customer_sales_orders(database, parsed_id, status=status)
    return (
        [
            serialize_document({"id": order.pop("_id"), **order})
            for order in orders
        ],
        pagination.build_meta(total),
    )
