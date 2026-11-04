"""Sales-order API, total calculation, and stock reservation tests."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import timezone
from threading import Barrier, RLock
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from inventory.services import adjust_stock
from tests.accounts.fakes import FakeDatabase


class FakeMongoSession:
    """Provide transaction rollback and serialization for sales API tests."""

    def __init__(self, client):
        self.client = client

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def with_transaction(self, callback, **kwargs):
        assert kwargs["read_concern"].level == "snapshot"
        assert kwargs["write_concern"].document["w"] == "majority"
        with self.client.transaction_lock:
            snapshot = {
                name: deepcopy(collection.documents)
                for name, collection in self.client.database.collections.items()
            }
            try:
                return callback(self)
            except Exception:
                for name in tuple(self.client.database.collections):
                    if name not in snapshot:
                        del self.client.database.collections[name]
                    else:
                        self.client.database.collections[name].documents = snapshot[name]
                raise


class FakeMongoClient:
    """Provide the database and sessions used by sales services."""

    def __init__(self, database):
        self.database = database
        self.transaction_lock = RLock()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def __getitem__(self, database_name):
        assert database_name == "smarterp_test"
        return self.database

    def start_session(self):
        return FakeMongoSession(self)


@pytest.fixture
def sales_api(monkeypatch):
    """Route authentication and sales requests to a transactional fake database."""
    database = FakeDatabase()
    client = FakeMongoClient(database)
    database.client = client
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "sales-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "sales-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "sales-test-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")
    monkeypatch.setattr("accounts.authentication.MongoClient", lambda *a, **k: client)
    monkeypatch.setattr("sales.views.MongoClient", lambda *a, **k: client)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role="sales_manager"):
    """Insert a test identity for the requested permission-matrix role."""
    now = utc_now()
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Sales Test User",
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    database["users"].insert_one(user)
    return user


def auth_headers(user):
    """Build bearer-token headers for a test user."""
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


def insert_customer(database, *, status="active"):
    """Insert a customer for sales-order tests."""
    now = utc_now()
    customer = {
        "_id": ObjectId(),
        "code": f"CUS-{uuid4().hex[:8].upper()}",
        "name": "Acme Stores",
        "name_search": "acme stores",
        "email": "accounts@example.test",
        "phone": None,
        "billing_address": None,
        "shipping_address": None,
        "tax_id": None,
        "status": status,
        "credit_limit": None,
        "created_at": now,
        "updated_at": now,
    }
    database["customers"].insert_one(customer)
    return customer


def insert_product(database, *, price="20.00", quantity=10, reserved=0, active=True):
    """Insert a product with a known server-owned selling price and stock."""
    now = utc_now()
    product = {
        "_id": ObjectId(),
        "sku": f"SKU-{uuid4().hex[:8].upper()}",
        "name": "Office Chair",
        "name_search": "office chair",
        "description": None,
        "category": "Furniture",
        "unit": "each",
        "cost_price": Decimal128("10.00"),
        "selling_price": Decimal128(price),
        "quantity_on_hand": quantity,
        "reserved_quantity": reserved,
        "min_stock_level": 0,
        "is_active": active,
        "created_at": now,
        "updated_at": now,
    }
    database["products"].insert_one(product)
    return product


def create_order(client, user, customer, items, **extra):
    """Create a sales order through the API with intentionally overridable fields."""
    return client.post(
        "/api/sales-orders/",
        {"customer_id": str(customer["_id"]), "items": items, **extra},
        format="json",
        **auth_headers(user),
    )


def order_item(product, *, quantity=1, discount="0.00", tax="0.00", **extra):
    """Build an item request using only client-editable fields by default."""
    return {
        "product_id": str(product["_id"]),
        "quantity": quantity,
        "discount_percent": discount,
        "tax_percent": tax,
        **extra,
    }


def confirm_order(client, user, order_id):
    """Confirm an order through the API."""
    return client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )


def fulfill_order(client, user, order_id, *, key=None):
    """Fulfil an order with the required idempotency key."""
    return client.post(
        f"/api/sales-orders/{order_id}/fulfill/",
        {},
        format="json",
        HTTP_IDEMPOTENCY_KEY=key or str(uuid4()),
        **auth_headers(user),
    )


def test_create_calculates_each_line_and_ignores_client_prices_and_totals(
    client,
    sales_api,
):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    first = insert_product(sales_api, price="10.00")
    second = insert_product(sales_api, price="19.99")

    response = create_order(
        client,
        user,
        customer,
        [
            order_item(
                first,
                quantity=3,
                discount="10.00",
                tax="8.00",
                unit_price="0.01",
                line_subtotal="0.01",
                line_tax="0.01",
                line_total="0.01",
            ),
            order_item(
                second,
                quantity=2,
                discount="12.50",
                tax="5.00",
                unit_price="999999.99",
            ),
        ],
        subtotal="0.01",
        discount_total="0.00",
        tax_total="0.00",
        grand_total="0.01",
    )

    assert response.status_code == 201
    order = response.json()["data"]["sales_order"]
    assert order["order_number"] == f"SO-{utc_now().year}-000001"
    assert order["status"] == "draft"
    assert order["subtotal"] == "69.98"
    assert order["discount_total"] == "8.00"
    assert order["tax_total"] == "3.91"
    assert order["grand_total"] == "65.89"
    assert [
        (
            item["unit_price"],
            item["line_subtotal"],
            item["line_tax"],
            item["line_total"],
        )
        for item in order["items"]
    ] == [
        ("10.00", "30.00", "2.16", "29.16"),
        ("19.99", "39.98", "1.75", "36.73"),
    ]

    stored = sales_api["sales_orders"].find_one({"_id": ObjectId(order["id"])})
    assert isinstance(stored["items"][0]["unit_price"], Decimal128)
    assert isinstance(stored["items"][0]["discount_percent"], Decimal128)
    assert isinstance(stored["subtotal"], Decimal128)
    assert stored["created_at"].tzinfo == timezone.utc
    assert stored["status_history"][0]["status"] == "draft"


@pytest.mark.parametrize(
    ("quantity", "discount", "tax", "expected_subtotal", "expected_discount",
     "expected_tax", "expected_total"),
    [
        (1, "0.00", "0.00", "12.35", "0.00", "0.00", "12.35"),
        (3, "10.00", "8.00", "37.05", "3.70", "2.67", "36.02"),
        (2, "25.00", "5.50", "24.70", "6.17", "1.02", "19.55"),
    ],
)
def test_decimal_rounding_for_discount_and_tax_combinations(
    client,
    sales_api,
    quantity,
    discount,
    tax,
    expected_subtotal,
    expected_discount,
    expected_tax,
    expected_total,
):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="12.35")

    response = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=quantity, discount=discount, tax=tax)],
    )

    assert response.status_code == 201
    order = response.json()["data"]["sales_order"]
    assert order["subtotal"] == expected_subtotal
    assert order["discount_total"] == expected_discount
    assert order["tax_total"] == expected_tax
    assert order["grand_total"] == expected_total


@pytest.mark.parametrize(
    "items",
    [
        [],
        [{"product_id": "invalid", "quantity": 1}],
        [{"product_id": str(ObjectId()), "quantity": 0}],
        [{"product_id": str(ObjectId()), "quantity": True}],
        [{"product_id": str(ObjectId()), "quantity": 1, "tax_percent": 1.5}],
        [{"product_id": str(ObjectId()), "quantity": 1, "discount_percent": 101}],
        [
            {"product_id": str(ObjectId()), "quantity": 1},
            {"product_id": str(ObjectId()), "quantity": 2},
        ],
        [{"product_id": str(ObjectId()), "quantity": 1, "unknown": "value"}],
        [{"product_id": str(ObjectId()), "quantity": 1, "$where": "true"}],
    ],
)
def test_create_rejects_invalid_or_unsafe_item_input(client, sales_api, items):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)

    response = create_order(client, user, customer, items)

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert sales_api["sales_orders"].count_documents({}) == 0


def test_inactive_customer_or_product_cannot_be_used(client, sales_api):
    user = insert_user(sales_api)
    inactive_customer = insert_customer(sales_api, status="inactive")
    product = insert_product(sales_api)

    customer_response = create_order(
        client,
        user,
        inactive_customer,
        [order_item(product)],
    )
    active_customer = insert_customer(sales_api)
    inactive_product = insert_product(sales_api, active=False)
    product_response = create_order(
        client,
        user,
        active_customer,
        [order_item(inactive_product)],
    )

    assert customer_response.status_code == 400
    assert product_response.status_code == 400
    assert sales_api["sales_orders"].count_documents({}) == 0


def test_list_detail_and_draft_patch(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    other_customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="10.00")
    other_product = insert_product(sales_api, price="25.00")
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    listing = client.get(
        f"/api/sales-orders/?status=draft&customer_id={customer['_id']}"
        "&payment_status=unpaid"
        "&page=1&page_size=1",
        **auth_headers(user),
    )
    detail = client.get(f"/api/sales-orders/{order_id}/", **auth_headers(user))
    patched = client.patch(
        f"/api/sales-orders/{order_id}/",
        {
            "items": [order_item(other_product, quantity=2, discount="5.00")],
            "subtotal": "0.01",
        },
        format="json",
        **auth_headers(user),
    )
    assert created.status_code == 201
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["data"]["sales_order"]["customer_id"] == str(customer["_id"])
    assert patched.status_code == 200
    assert patched.json()["data"]["sales_order"]["items"][0]["unit_price"] == "25.00"
    assert patched.json()["data"]["sales_order"]["grand_total"] == "47.50"

    invalid = client.get(
        "/api/sales-orders/?customer_id=not-an-object-id",
        **auth_headers(user),
    )
    invalid_payment_status = client.get(
        "/api/sales-orders/?payment_status=overdue",
        **auth_headers(user),
    )
    assert invalid.status_code == 400
    assert invalid_payment_status.status_code == 400


def test_inventory_manager_can_read_orders_to_fulfil(client, sales_api):
    sales_manager = insert_user(sales_api)
    inventory_manager = insert_user(sales_api, "inventory_manager")
    customer = insert_customer(sales_api)
    product = insert_product(sales_api)
    created = create_order(
        client,
        sales_manager,
        customer,
        [order_item(product)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    listing = client.get("/api/sales-orders/", **auth_headers(inventory_manager))
    detail = client.get(
        f"/api/sales-orders/{order_id}/",
        **auth_headers(inventory_manager),
    )

    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 1
    assert detail.status_code == 200
    assert detail.json()["data"]["sales_order"]["id"] == order_id


def test_confirm_reserves_stock_without_deducting_on_hand(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=5, reserved=1)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=3)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    response = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )

    stored_product = sales_api["products"].find_one({"_id": product["_id"]})
    movement = sales_api["stock_movements"].find_one({"reference_id": ObjectId(order_id)})
    assert response.status_code == 200
    assert response.json()["data"]["sales_order"]["status"] == "confirmed"
    assert stored_product["quantity_on_hand"] == 5
    assert stored_product["reserved_quantity"] == 4
    assert movement["movement_type"] == "reservation"
    assert movement["quantity_change"] == 0
    assert movement["reserved_change"] == 3


def test_confirm_insufficient_stock_returns_product_details_and_rolls_back(
    client,
    sales_api,
):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=2, reserved=1)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    response = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert response.json()["error"]["details"]["product"] == {
        "id": str(product["_id"]),
        "sku": product["sku"],
        "name": product["name"],
        "requested_quantity": 2,
        "available_quantity": 1,
    }
    assert sales_api["products"].find_one({"_id": product["_id"]})[
        "reserved_quantity"
    ] == 1
    assert sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})[
        "status"
    ] == "draft"
    assert sales_api["stock_movements"].count_documents({}) == 0


def test_confirm_requires_product_to_remain_active(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=5)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]
    sales_api["products"].update_one(
        {"_id": product["_id"]},
        {"$set": {"is_active": False}},
    )

    response = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 409
    assert sales_api["products"].find_one({"_id": product["_id"]})[
        "reserved_quantity"
    ] == 0
    assert sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})[
        "status"
    ] == "draft"
    assert sales_api["stock_movements"].count_documents({}) == 0


def test_confirm_rolls_back_prior_line_reservations_when_later_line_fails(
    client,
    sales_api,
):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    first = insert_product(sales_api, quantity=5)
    last = insert_product(sales_api, quantity=1)
    created = create_order(
        client,
        user,
        customer,
        [order_item(first, quantity=2), order_item(last, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    response = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )

    assert response.status_code == 409
    assert sales_api["products"].find_one({"_id": first["_id"]})[
        "reserved_quantity"
    ] == 0
    assert sales_api["products"].find_one({"_id": last["_id"]})[
        "reserved_quantity"
    ] == 0
    assert sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})[
        "status"
    ] == "draft"
    assert sales_api["stock_movements"].count_documents({}) == 0


def test_parallel_confirmations_for_the_last_unit_allow_only_one_winner(
    client,
    sales_api,
):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=1)
    order_ids = [
        create_order(
            client,
            user,
            customer,
            [order_item(product)],
        ).json()["data"]["sales_order"]["id"]
        for _ in range(2)
    ]
    barrier = Barrier(2)

    def confirm(order_id):
        api_client = APIClient()
        barrier.wait()
        return api_client.post(
            f"/api/sales-orders/{order_id}/confirm/",
            {},
            format="json",
            **auth_headers(user),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(confirm, order_ids))

    assert sorted(response.status_code for response in responses) == [200, 409]
    product_after = sales_api["products"].find_one({"_id": product["_id"]})
    assert product_after["quantity_on_hand"] == 1
    assert product_after["reserved_quantity"] == 1
    assert sales_api["stock_movements"].count_documents(
        {"movement_type": "reservation"}
    ) == 1
    statuses = {
        sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})["status"]
        for order_id in order_ids
    }
    assert statuses == {"draft", "confirmed"}


def test_cancel_confirmed_releases_reservation_and_keeps_on_hand(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=7, reserved=1)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=3)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]
    confirmed = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )

    cancelled = client.post(
        f"/api/sales-orders/{order_id}/cancel/",
        {},
        format="json",
        **auth_headers(user),
    )

    stored_product = sales_api["products"].find_one({"_id": product["_id"]})
    release = sales_api["stock_movements"].find_one(
        {"reference_id": ObjectId(order_id), "movement_type": "reservation_release"}
    )
    assert confirmed.status_code == 200
    assert cancelled.status_code == 200
    assert cancelled.json()["data"]["sales_order"]["status"] == "cancelled"
    assert stored_product["quantity_on_hand"] == 7
    assert stored_product["reserved_quantity"] == 1
    assert release["quantity_change"] == 0
    assert release["reserved_change"] == -3


def test_invalid_transitions_and_draft_cancel_have_no_stock_effect(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=3)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    cancelled = client.post(
        f"/api/sales-orders/{order_id}/cancel/",
        {},
        format="json",
        **auth_headers(user),
    )
    confirm_cancelled = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )
    cancel_again = client.post(
        f"/api/sales-orders/{order_id}/cancel/",
        {},
        format="json",
        **auth_headers(user),
    )

    assert cancelled.status_code == 200
    assert confirm_cancelled.status_code == 409
    assert cancel_again.status_code == 409
    assert sales_api["products"].find_one({"_id": product["_id"]})[
        "reserved_quantity"
    ] == 0
    assert sales_api["stock_movements"].count_documents({}) == 0


def test_confirmed_order_cannot_be_confirmed_again_or_edited(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, quantity=3)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]
    first_confirm = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )
    second_confirm = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(user),
    )
    patch = client.patch(
        f"/api/sales-orders/{order_id}/",
        {"items": [order_item(product, quantity=2)]},
        format="json",
        **auth_headers(user),
    )

    assert first_confirm.status_code == 200
    assert second_confirm.status_code == 409
    assert patch.status_code == 409
    assert sales_api["products"].find_one({"_id": product["_id"]})[
        "reserved_quantity"
    ] == 1
    assert sales_api["stock_movements"].count_documents({}) == 1


def test_confirmation_and_cancel_permissions_are_enforced(client, sales_api):
    sales_manager = insert_user(sales_api, "sales_manager")
    employee = insert_user(sales_api, "employee")
    customer = insert_customer(sales_api)
    product = insert_product(sales_api)
    created = create_order(
        client,
        sales_manager,
        customer,
        [order_item(product)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    forbidden_confirm = client.post(
        f"/api/sales-orders/{order_id}/confirm/",
        {},
        format="json",
        **auth_headers(employee),
    )
    forbidden_cancel = client.post(
        f"/api/sales-orders/{order_id}/cancel/",
        {},
        format="json",
        **auth_headers(employee),
    )

    assert forbidden_confirm.status_code == 403
    assert forbidden_cancel.status_code == 403
    assert sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})[
        "status"
    ] == "draft"


def test_fulfillment_requires_confirmation_key_and_is_idempotent(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="12.50", quantity=4)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    missing_key = client.post(
        f"/api/sales-orders/{order_id}/fulfill/",
        {},
        format="json",
        **auth_headers(user),
    )
    unconfirmed = fulfill_order(client, user, order_id)
    assert missing_key.status_code == 400
    assert unconfirmed.status_code == 409

    assert confirm_order(client, user, order_id).status_code == 200
    key = str(uuid4())
    fulfilled = fulfill_order(client, user, order_id, key=key)
    replay = fulfill_order(client, user, order_id, key=key)
    new_key_retry = fulfill_order(client, user, order_id)

    stored_product = sales_api["products"].find_one({"_id": product["_id"]})
    order = sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})
    invoice = sales_api["invoices"].find_one({"sales_order_id": ObjectId(order_id)})
    movements = sales_api["stock_movements"].find(
        {"reference_id": ObjectId(order_id)}
    )
    assert fulfilled.status_code == 200
    assert fulfilled.json()["data"]["sales_order"]["status"] == "fulfilled"
    assert fulfilled.json()["data"]["invoice"]["invoice_number"].startswith("INV-")
    assert replay.status_code == 200
    assert replay.json() == fulfilled.json()
    assert new_key_retry.status_code == 409
    assert stored_product["quantity_on_hand"] == 2
    assert stored_product["reserved_quantity"] == 0
    assert order["fulfilled_at"] is not None
    assert invoice["due_date"] > invoice["issued_at"]
    assert len(list(movements)) == 2
    assert sales_api["audit_logs"].count_documents(
        {"action": "sales_order.fulfilled"}
    ) == 1


def test_payment_partial_full_and_overpayment(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="25.00")
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2)],
    )
    order_id = created.json()["data"]["sales_order"]["id"]
    assert confirm_order(client, user, order_id).status_code == 200
    assert fulfill_order(client, user, order_id).status_code == 200

    def pay(amount, reference=None, key=None):
        body = {"amount": amount, "method": "bank_transfer"}
        if reference is not None:
            body["reference"] = reference
        return client.post(
            f"/api/sales-orders/{order_id}/payments/",
            body,
            format="json",
            HTTP_IDEMPOTENCY_KEY=key or str(uuid4()),
            **auth_headers(user),
        )

    payment_key = str(uuid4())
    partial = pay("20.00", "PAY-001", key=payment_key)
    replay = pay("20.00", "PAY-001", key=payment_key)
    overpay = pay("30.01", "PAY-002")
    final = pay("30.00", "PAY-003")
    listing = client.get("/api/payments/?page=1&page_size=10", **auth_headers(user))

    stored = sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})
    assert partial.status_code == 201
    assert replay.status_code == 201
    assert replay.json() == partial.json()
    assert partial.json()["data"]["sales_order"]["payment_status"] == "partial"
    assert overpay.status_code == 409
    assert final.status_code == 201
    assert final.json()["data"]["sales_order"]["payment_status"] == "paid"
    assert listing.status_code == 200
    assert listing.json()["meta"]["total"] == 2
    assert stored["paid_total"] == Decimal128("50.00")
    assert sales_api["payments"].count_documents({}) == 2


def test_return_restock_credit_note_and_return_limit(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="20.00", quantity=5)
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2, discount="10.00", tax="5.00")],
    )
    order_id = created.json()["data"]["sales_order"]["id"]
    assert confirm_order(client, user, order_id).status_code == 200
    assert fulfill_order(client, user, order_id).status_code == 200

    def return_item(quantity):
        return client.post(
            f"/api/sales-orders/{order_id}/returns/",
            {
                "items": [{"product_id": str(product["_id"]), "quantity": quantity}],
                "reason": "Damaged packaging",
            },
            format="json",
            **auth_headers(user),
        )

    partial = return_item(1)
    full = return_item(1)
    excessive = return_item(1)

    stored_product = sales_api["products"].find_one({"_id": product["_id"]})
    order = sales_api["sales_orders"].find_one({"_id": ObjectId(order_id)})
    credit_note = sales_api["sales_returns"].find_one(
        {"sales_order_id": ObjectId(order_id)}
    )
    return_movements = list(
        sales_api["stock_movements"].find(
            {
                "reference_id": ObjectId(order_id),
                "movement_type": "sale_return",
            }
        )
    )
    assert partial.status_code == 201
    assert partial.json()["data"]["sales_order"]["status"] == "fulfilled"
    assert partial.json()["data"]["sales_order"]["return_status"] == "partial"
    assert full.status_code == 201
    assert full.json()["data"]["sales_order"]["return_status"] == "full"
    assert full.json()["data"]["sales_return"]["credit_note_number"].startswith("CN-")
    assert excessive.status_code == 409
    assert stored_product["quantity_on_hand"] == 5
    assert stored_product["reserved_quantity"] == 0
    assert order["items"][0]["returned_quantity"] == 2
    assert len(return_movements) == 2
    assert credit_note["total"] == Decimal128("18.90")
    assert sales_api["audit_logs"].count_documents(
        {"action": "sales_order.returned"}
    ) == 2


def test_invoice_list_detail_and_full_sales_lifecycle(client, sales_api):
    user = insert_user(sales_api)
    customer = insert_customer(sales_api)
    product = insert_product(sales_api, price="20.00", quantity=0)
    adjust_stock(
        sales_api,
        product_id=product["_id"],
        quantity_change=4,
        reason="Opening inventory for integration test",
        user_id=user["_id"],
        idempotency_key=str(uuid4()),
    )
    created = create_order(
        client,
        user,
        customer,
        [order_item(product, quantity=2, discount="10.00", tax="5.00")],
    )
    order_id = created.json()["data"]["sales_order"]["id"]

    assert confirm_order(client, user, order_id).status_code == 200
    fulfilled = fulfill_order(client, user, order_id)
    invoice_id = fulfilled.json()["data"]["invoice"]["id"]
    invoice_list = client.get("/api/invoices/?page=1&page_size=10", **auth_headers(user))
    invoice_detail = client.get(
        f"/api/invoices/{invoice_id}/",
        **auth_headers(user),
    )
    payment = client.post(
        f"/api/sales-orders/{order_id}/payments/",
        {"amount": "37.80", "method": "cash"},
        format="json",
        HTTP_IDEMPOTENCY_KEY=str(uuid4()),
        **auth_headers(user),
    )
    returned = client.post(
        f"/api/sales-orders/{order_id}/returns/",
        {
            "items": [{"product_id": str(product["_id"]), "quantity": 1}],
            "reason": "Customer changed their mind",
        },
        format="json",
        **auth_headers(user),
    )

    assert fulfilled.status_code == 200
    assert invoice_list.status_code == 200
    assert invoice_list.json()["meta"]["total"] == 1
    assert invoice_detail.status_code == 200
    assert invoice_detail.json()["data"]["invoice"]["id"] == invoice_id
    assert payment.status_code == 201
    assert payment.json()["data"]["sales_order"]["payment_status"] == "paid"
    assert returned.status_code == 201
    assert returned.json()["data"]["sales_order"]["return_status"] == "partial"
    stored_product = sales_api["products"].find_one({"_id": product["_id"]})
    ledger_total = sum(
        movement["quantity_change"]
        for movement in sales_api["stock_movements"].find(
            {"product_id": product["_id"]}
        )
    )
    assert ledger_total == stored_product["quantity_on_hand"] == 3
