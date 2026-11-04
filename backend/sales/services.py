"""Sales-order business rules, totals, and stock-state transitions."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Any, Callable, TypeVar

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from common.exceptions import (
    InsufficientStock,
    InvalidStateTransition,
    NotFoundError,
    ValidationFailed,
)
from common.money import (
    apply_discount,
    apply_tax,
    line_total,
    quantize_money,
    to_decimal,
)
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from customers.repository import find_customer_by_id
from inventory.repository import find_active_product
from inventory.services import apply_stock_change
from sales.repository import (
    count_sales_orders,
    find_sales_order_by_id,
    insert_sales_order,
    list_sales_orders as list_sales_order_records,
    public_sales_order,
    transition_sales_order as transition_sales_order_record,
    update_draft_sales_order,
)

T = TypeVar("T")


def _public_sales_order(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a sales order with BSON values converted for JSON."""
    return serialize_document(public_sales_order(document))


def _active_customer(
    database: Database[Any],
    customer_id: ObjectId | str,
) -> dict[str, Any]:
    """Return an active customer or raise a safe not-found/validation error."""
    parsed_id = parse_object_id(customer_id)
    customer = database["customers"].find_one(
        {"_id": parsed_id, "status": "active"}
    )
    if customer is not None:
        return customer
    if find_customer_by_id(database, parsed_id) is None:
        raise NotFoundError("Customer was not found.")
    raise ValidationFailed(
        "Inactive customers cannot be used for new sales orders.",
        details={"customer_id": "Customer is inactive."},
    )


def _build_items(
    database: Database[Any],
    values: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], Decimal, Decimal, Decimal, Decimal]:
    """Resolve trusted product prices and calculate rounded per-line totals."""
    items: list[dict[str, Any]] = []
    seen_product_ids: set[ObjectId] = set()
    subtotal = Decimal("0.00")
    discount_total = Decimal("0.00")
    tax_total = Decimal("0.00")
    grand_total = Decimal("0.00")

    for value in values:
        product_id = parse_object_id(value["product_id"])
        if product_id in seen_product_ids:
            raise ValidationFailed(
                "A product may appear only once in a sales order.",
                details={"items": "Duplicate product IDs are not allowed."},
            )
        seen_product_ids.add(product_id)
        product = find_active_product(database, product_id)
        if product is None:
            raise ValidationFailed(
                "Inactive products cannot be used on new sales orders.",
                details={"product_id": str(product_id), "product": "Missing or inactive."},
            )

        quantity = value["quantity"]
        unit_price = to_decimal(product["selling_price"])
        discount_percent = to_decimal(value.get("discount_percent", Decimal("0")))
        tax_percent = to_decimal(value.get("tax_percent", Decimal("0")))
        line_subtotal = line_total(unit_price, quantity)
        discounted_subtotal = apply_discount(line_subtotal, discount_percent)
        line_discount = quantize_money(line_subtotal - discounted_subtotal)
        taxed_line_total = apply_tax(discounted_subtotal, tax_percent)
        line_tax = quantize_money(taxed_line_total - discounted_subtotal)
        line_amount = quantize_money(discounted_subtotal + line_tax)

        items.append(
            {
                "product_id": product_id,
                "sku": product["sku"],
                "name": product["name"],
                "quantity": quantity,
                "unit_price": unit_price,
                "discount_percent": discount_percent,
                "tax_percent": tax_percent,
                "line_subtotal": line_subtotal,
                "line_tax": line_tax,
                "line_total": line_amount,
            }
        )
        subtotal += line_subtotal
        discount_total += line_discount
        tax_total += line_tax
        grand_total += line_amount

    return (
        items,
        quantize_money(subtotal),
        quantize_money(discount_total),
        quantize_money(tax_total),
        quantize_money(grand_total),
    )


def _prepare_order_values(
    database: Database[Any],
    *,
    customer_id: ObjectId | str,
    items: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], Decimal, Decimal, Decimal, Decimal]:
    """Validate an active customer and calculate server-owned line/order values."""
    customer = _active_customer(database, customer_id)
    built_items, subtotal, discount_total, tax_total, grand_total = _build_items(
        database,
        items,
    )
    return customer, built_items, subtotal, discount_total, tax_total, grand_total


def create_sales_order(
    database: Database[Any],
    *,
    values: dict[str, Any],
    created_by: ObjectId | str,
) -> dict[str, Any]:
    """Create a Draft order with active records and server-calculated totals."""
    actor_id = parse_object_id(created_by)
    customer, items, subtotal, discount_total, tax_total, grand_total = (
        _prepare_order_values(
            database,
            customer_id=values["customer_id"],
            items=values["items"],
        )
    )
    order = insert_sales_order(
        database,
        customer=customer,
        items=items,
        subtotal=subtotal,
        discount_total=discount_total,
        tax_total=tax_total,
        grand_total=grand_total,
        created_by=actor_id,
    )
    return _public_sales_order(order)


def get_sales_order(
    database: Database[Any],
    sales_order_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one sales order or raise a safe not-found error."""
    order = find_sales_order_by_id(database, sales_order_id)
    if order is None:
        raise NotFoundError("Sales order was not found.")
    return _public_sales_order(order)


def list_sales_orders(
    database: Database[Any],
    *,
    status: str | None,
    customer_id: ObjectId | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return a paginated sales-order list and metadata."""
    orders = list_sales_order_records(
        database,
        status=status,
        customer_id=customer_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_sales_orders(
        database,
        status=status,
        customer_id=customer_id,
    )
    return [_public_sales_order(order) for order in orders], pagination.build_meta(total)


def update_sales_order(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update an order only while Draft and recalculate all server-owned values."""
    parsed_id = parse_object_id(sales_order_id)
    current = find_sales_order_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Sales order was not found.")
    if current["status"] != "draft":
        raise InvalidStateTransition("Only Draft sales orders may be edited.")

    customer_id = values.get("customer_id", current["customer_id"])
    current_items = [
        {
            "product_id": item["product_id"],
            "quantity": item["quantity"],
            "discount_percent": item.get("discount_percent", Decimal128("0.00")),
            "tax_percent": item.get("tax_percent", Decimal128("0.00")),
        }
        for item in current["items"]
    ]
    items_input = values.get("items", current_items)
    customer, items, subtotal, discount_total, tax_total, grand_total = (
        _prepare_order_values(
            database,
            customer_id=customer_id,
            items=items_input,
        )
    )
    updated = update_draft_sales_order(
        database,
        parsed_id,
        customer=customer,
        items=items,
        subtotal=subtotal,
        discount_total=discount_total,
        tax_total=tax_total,
        grand_total=grand_total,
    )
    if updated is None:
        raise InvalidStateTransition("Only Draft sales orders may be edited.")
    return _public_sales_order(updated)


def _run_transaction(
    database: Database[Any],
    operation: Callable[[ClientSession], T],
) -> T:
    """Execute the given work in a snapshot/majority MongoDB transaction."""
    client = getattr(database, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise ValueError("A MongoDB database client is required for transactions.")
    with client.start_session() as session:
        return session.with_transaction(
            operation,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )


def _reserve_order_items(
    database: Database[Any],
    session: ClientSession,
    order: Mapping[str, Any],
    actor_id: ObjectId,
) -> None:
    """Reserve each order line and report safe product-specific stock failures."""
    for item in order["items"]:
        product_id = item["product_id"]
        quantity = item["quantity"]
        try:
            apply_stock_change(
                session,
                product_id,
                0,
                quantity,
                "reservation",
                f"Reserve sales order {order['order_number']}",
                "sales_order",
                order["_id"],
                actor_id,
            )
        except InsufficientStock as exc:
            product = database["products"].find_one(
                {"_id": product_id},
                session=session,
            )
            available = None
            if product is not None:
                available = max(
                    0,
                    product.get("quantity_on_hand", 0)
                    - product.get("reserved_quantity", 0),
                )
            raise InsufficientStock(
                "There is not enough active stock to confirm this sales order.",
                details={
                    "product": {
                        "id": str(product_id),
                        "sku": item["sku"],
                        "name": item["name"],
                        "requested_quantity": quantity,
                        "available_quantity": available,
                    }
                },
            ) from exc


def _release_order_items(
    session: ClientSession,
    order: Mapping[str, Any],
    actor_id: ObjectId,
) -> None:
    """Release every reserved line without changing on-hand stock."""
    for item in order["items"]:
        apply_stock_change(
            session,
            item["product_id"],
            0,
            -item["quantity"],
            "reservation_release",
            f"Release reservation for sales order {order['order_number']}",
            "sales_order",
            order["_id"],
            actor_id,
        )


def _transition_in_transaction(
    database: Database[Any],
    session: ClientSession,
    order: Mapping[str, Any],
    *,
    next_status: str,
    actor_id: ObjectId,
) -> dict[str, Any]:
    """Conditionally transition the order and return its transaction snapshot."""
    result = transition_sales_order_record(
        database,
        session,
        order["_id"],
        expected_status=order["status"],
        next_status=next_status,
        actor_id=actor_id,
    )
    if result.modified_count != 1:
        raise InvalidStateTransition()
    updated = find_sales_order_by_id(database, order["_id"], session=session)
    if updated is None:
        raise NotFoundError("Sales order was not found.")
    return updated


def transition_sales_order(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    action: str,
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Confirm or cancel an order with stock effects committed atomically."""
    parsed_id = parse_object_id(sales_order_id)
    actor = parse_object_id(actor_id)
    if action not in {"confirm", "cancel"}:
        raise ValueError("Sales-order action is not supported.")

    def operation(session: ClientSession) -> dict[str, Any]:
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")

        if action == "confirm":
            if order["status"] != "draft":
                raise InvalidStateTransition(
                    "Only Draft sales orders may be confirmed."
                )
            _reserve_order_items(database, session, order, actor)
            return _transition_in_transaction(
                database,
                session,
                order,
                next_status="confirmed",
                actor_id=actor,
            )

        if order["status"] not in {"draft", "confirmed"}:
            raise InvalidStateTransition(
                "Only Draft or Confirmed sales orders may be cancelled."
            )
        if order["status"] == "confirmed":
            _release_order_items(session, order, actor)
        return _transition_in_transaction(
            database,
            session,
            order,
            next_status="cancelled",
            actor_id=actor,
        )

    return _public_sales_order(_run_transaction(database, operation))
