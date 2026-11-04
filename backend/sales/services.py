"""Sales-order business rules, totals, and stock-state transitions."""

from collections.abc import Mapping
from datetime import timedelta
from decimal import Decimal
from typing import Any, Callable, TypeVar

from bson import ObjectId
from bson.decimal128 import Decimal128
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from common.exceptions import (
    ConflictError,
    InsufficientStock,
    InvalidStateTransition,
    NotFoundError,
    ValidationFailed,
)
from common.idempotency import execute_idempotent
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
from common.time import utc_now
from accounts.repository import write_audit_log
from customers.repository import find_customer_by_id
from inventory.repository import find_active_product
from inventory.services import apply_stock_change
from sales.repository import (
    allocate_document_number,
    count_invoices,
    count_payments,
    count_sales_orders,
    find_invoice_by_id,
    find_sales_order_by_id,
    increment_returned_quantity,
    insert_invoice,
    insert_payment,
    insert_sales_return,
    insert_sales_order,
    initialize_returned_quantities,
    list_invoices as list_invoice_records,
    list_payments as list_payment_records,
    list_sales_orders as list_sales_order_records,
    public_invoice,
    public_payment,
    public_sales_return,
    public_sales_order,
    transition_sales_order as transition_sales_order_record,
    update_paid_total,
    update_return_status,
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
                "returned_quantity": 0,
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


def _fulfil_order_items(
    session: ClientSession,
    order: Mapping[str, Any],
    actor_id: ObjectId,
) -> None:
    """Deduct each reserved line and record its stock movement."""
    for item in order["items"]:
        quantity = item["quantity"]
        apply_stock_change(
            session,
            item["product_id"],
            -quantity,
            -quantity,
            "sale_fulfilment",
            f"Fulfil sales order {order['order_number']}",
            "sales_order",
            order["_id"],
            actor_id,
        )


def fulfil_sales_order(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    actor_id: ObjectId | str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    """Fulfil a Confirmed order idempotently and create its invoice atomically."""
    parsed_id = parse_object_id(sales_order_id)
    actor = parse_object_id(actor_id)

    def operation(session: ClientSession, _operation_id: ObjectId) -> dict[str, Any]:
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")
        if order["status"] != "confirmed":
            raise InvalidStateTransition(
                "Only Confirmed sales orders may be fulfilled."
            )

        if not initialize_returned_quantities(database, session, order):
            raise InvalidStateTransition()
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")
        _fulfil_order_items(session, order, actor)
        fulfilled_at = utc_now()
        transitioned = transition_sales_order_record(
            database,
            session,
            parsed_id,
            expected_status="confirmed",
            next_status="fulfilled",
            actor_id=actor,
            fulfilled_at=fulfilled_at,
        )
        if transitioned.modified_count != 1:
            raise InvalidStateTransition()

        invoice_number = allocate_document_number(
            database,
            session,
            counter_name="invoice",
            prefix="INV",
            year=fulfilled_at.year,
        )
        invoice = insert_invoice(
            database,
            session,
            invoice_id=ObjectId(),
            invoice_number=invoice_number,
            order=order,
            issued_at=fulfilled_at,
            due_date=fulfilled_at + timedelta(days=30),
        )
        updated_order = find_sales_order_by_id(database, parsed_id, session=session)
        if updated_order is None:
            raise NotFoundError("Sales order was not found.")
        write_audit_log(
            database,
            actor_id=actor,
            action="sales_order.fulfilled",
            resource="sales_order",
            resource_id=parsed_id,
            outcome="success",
            now=fulfilled_at,
            session=session,
        )
        return {
            "sales_order": _public_sales_order(updated_order),
            "invoice": serialize_document(public_invoice(invoice)),
        }

    return execute_idempotent(
        database,
        user_id=actor,
        endpoint=f"sales-orders:{parsed_id}:fulfil",
        key=idempotency_key or "",
        request_body={},
        operation=operation,
    )


def record_payment(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    values: dict[str, Any],
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Record a completed payment without allowing the order to be overpaid."""
    parsed_id = parse_object_id(sales_order_id)
    actor = parse_object_id(actor_id)
    amount = to_decimal(values["amount"])

    def operation(session: ClientSession) -> dict[str, Any]:
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")
        if order["status"] != "fulfilled":
            raise InvalidStateTransition(
                "Payments may be recorded only for fulfilled sales orders."
            )
        current_paid = (
            to_decimal(order["paid_total"])
            if order.get("paid_total") is not None
            else None
        )
        paid_before = current_paid or Decimal("0.00")
        next_paid = quantize_money(paid_before + amount)
        grand_total = to_decimal(order["grand_total"])
        if next_paid > grand_total:
            raise ConflictError(
                "Payment exceeds the sales order's outstanding balance.",
                details={
                    "outstanding_amount": str(quantize_money(grand_total - paid_before))
                },
            )

        now = utc_now()
        payment = insert_payment(
            database,
            session,
            payment_id=ObjectId(),
            order=order,
            amount=amount,
            method=values["method"],
            reference=values.get("reference"),
            actor_id=actor,
            now=now,
        )
        status = "paid" if next_paid == grand_total else "partial"
        updated = update_paid_total(
            database,
            session,
            order_id=parsed_id,
            expected_paid_total=current_paid,
            paid_total=next_paid,
            payment_status=status,
            now=now,
        )
        if updated.modified_count != 1:
            raise ConflictError(
                "The payment balance changed. Please retry the request."
            )
        write_audit_log(
            database,
            actor_id=actor,
            action="payment.recorded",
            resource="payment",
            resource_id=payment["_id"],
            outcome="success",
            now=now,
            session=session,
        )
        updated_order = find_sales_order_by_id(database, parsed_id, session=session)
        if updated_order is None:
            raise NotFoundError("Sales order was not found.")
        return {
            "payment": serialize_document(public_payment(payment)),
            "sales_order": _public_sales_order(updated_order),
        }

    return _run_transaction(database, operation)


def list_payments(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
    method: str | None,
    status: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return one authorized, paginated payment page."""
    values = list_payment_records(
        database,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        method=method,
        status=status,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_payments(
        database,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        method=method,
        status=status,
    )
    return (
        [serialize_document(public_payment(value)) for value in values],
        pagination.build_meta(total),
    )


def list_invoices(
    database: Database[Any],
    *,
    customer_id: ObjectId | None,
    sales_order_id: ObjectId | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return one authorized, paginated invoice page."""
    values = list_invoice_records(
        database,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    total = count_invoices(
        database,
        customer_id=customer_id,
        sales_order_id=sales_order_id,
    )
    return (
        [serialize_document(public_invoice(value)) for value in values],
        pagination.build_meta(total),
    )


def get_invoice(
    database: Database[Any],
    invoice_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one invoice or raise a safe not-found error."""
    invoice = find_invoice_by_id(database, invoice_id)
    if invoice is None:
        raise NotFoundError("Invoice was not found.")
    return serialize_document(public_invoice(invoice))


def _return_line(
    order_item: Mapping[str, Any],
    quantity: int,
) -> dict[str, Any]:
    """Recalculate the prorated line amounts for a returned quantity."""
    unit_price = to_decimal(order_item["unit_price"])
    discount_percent = to_decimal(order_item.get("discount_percent", "0"))
    tax_percent = to_decimal(order_item.get("tax_percent", "0"))
    subtotal = line_total(unit_price, quantity)
    discounted = apply_discount(subtotal, discount_percent)
    discount = quantize_money(subtotal - discounted)
    taxed = apply_tax(discounted, tax_percent)
    tax = quantize_money(taxed - discounted)
    return {
        "product_id": order_item["product_id"],
        "sku": order_item["sku"],
        "name": order_item["name"],
        "quantity": quantity,
        "unit_price": unit_price,
        "discount_percent": discount_percent,
        "tax_percent": tax_percent,
        "line_subtotal": subtotal,
        "line_discount": discount,
        "line_tax": tax,
        "line_total": quantize_money(discounted + tax),
    }


def process_sales_return(
    database: Database[Any],
    sales_order_id: ObjectId | str,
    *,
    values: dict[str, Any],
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Restock a fulfilled order, recording an auditable credit note."""
    parsed_id = parse_object_id(sales_order_id)
    actor = parse_object_id(actor_id)

    def operation(session: ClientSession) -> dict[str, Any]:
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")
        if order["status"] != "fulfilled":
            raise InvalidStateTransition(
                "Only Fulfilled sales orders may be returned."
            )

        if not initialize_returned_quantities(database, session, order):
            raise InvalidStateTransition()
        order = find_sales_order_by_id(database, parsed_id, session=session)
        if order is None:
            raise NotFoundError("Sales order was not found.")
        order_items = {
            item["product_id"]: item
            for item in order["items"]
        }
        returned_lines: list[dict[str, Any]] = []
        subtotal = Decimal("0.00")
        discount_total = Decimal("0.00")
        tax_total = Decimal("0.00")
        total = Decimal("0.00")
        now = utc_now()
        for requested in values["items"]:
            product_id = requested["product_id"]
            order_item = order_items.get(product_id)
            if order_item is None:
                raise ValidationFailed(
                    "A return item must belong to the sales order.",
                    details={"product_id": str(product_id)},
                )
            returned = order_item.get("returned_quantity", 0)
            if requested["quantity"] > order_item["quantity"] - returned:
                raise ConflictError(
                    "Return quantity exceeds the fulfilled quantity not yet returned.",
                    details={
                        "product_id": str(product_id),
                        "returnable_quantity": order_item["quantity"] - returned,
                    },
                )

            changed = increment_returned_quantity(
                database,
                session,
                order_id=parsed_id,
                product_id=product_id,
                quantity=requested["quantity"],
                max_returned_quantity=(
                    order_item["quantity"] - requested["quantity"]
                ),
            )
            if changed.modified_count != 1:
                raise ConflictError(
                    "Returnable quantity changed. Please retry the request.",
                    details={"product_id": str(product_id)},
                )
            line = _return_line(order_item, requested["quantity"])
            returned_lines.append(line)
            subtotal += line["line_subtotal"]
            discount_total += line["line_discount"]
            tax_total += line["line_tax"]
            total += line["line_total"]
            apply_stock_change(
                session,
                product_id,
                requested["quantity"],
                0,
                "sale_return",
                f"Return for sales order {order['order_number']}: "
                f"{values['reason']}"[:500],
                "sales_order",
                parsed_id,
                actor,
            )

        updated_order = find_sales_order_by_id(database, parsed_id, session=session)
        if updated_order is None:
            raise NotFoundError("Sales order was not found.")
        return_status = (
            "full"
            if all(
                item.get("returned_quantity", 0) >= item["quantity"]
                for item in updated_order["items"]
            )
            else "partial"
        )
        status_update = update_return_status(
            database,
            session,
            order_id=parsed_id,
            expected_status="fulfilled",
            return_status=return_status,
            now=now,
        )
        if status_update.modified_count != 1:
            raise InvalidStateTransition()

        credit_note_number = allocate_document_number(
            database,
            session,
            counter_name="credit_note",
            prefix="CN",
            year=now.year,
        )
        sales_return = insert_sales_return(
            database,
            session,
            return_id=ObjectId(),
            credit_note_number=credit_note_number,
            order=order,
            items=returned_lines,
            reason=values["reason"],
            subtotal=quantize_money(subtotal),
            discount_total=quantize_money(discount_total),
            tax_total=quantize_money(tax_total),
            total=quantize_money(total),
            actor_id=actor,
            now=now,
        )
        write_audit_log(
            database,
            actor_id=actor,
            action="sales_order.returned",
            resource="sales_return",
            resource_id=sales_return["_id"],
            outcome="success",
            now=now,
            session=session,
        )
        updated_order = find_sales_order_by_id(database, parsed_id, session=session)
        if updated_order is None:
            raise NotFoundError("Sales order was not found.")
        return {
            "sales_return": serialize_document(public_sales_return(sales_return)),
            "sales_order": _public_sales_order(updated_order),
        }

    return _run_transaction(database, operation)
