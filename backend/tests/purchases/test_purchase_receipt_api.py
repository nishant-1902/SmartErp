"""Transactional receipt API, idempotency, and stock consistency tests."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import RLock
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from purchases.repository import increment_received_quantity
from tests.accounts.fakes import FakeDatabase


class FakeMongoSession:
    """Provide transaction rollback and serialization for receipt tests."""

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
    """Provide the database and sessions used by the receipt service."""

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
def receipt_api(monkeypatch):
    """Route authenticated receipt requests to a transactional fake database."""
    database = FakeDatabase()
    client = FakeMongoClient(database)
    database.client = client
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "receipt-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "receipt-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "receipt-test-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")
    monkeypatch.setattr("accounts.authentication.MongoClient", lambda *a, **k: client)
    monkeypatch.setattr("purchases.views.MongoClient", lambda *a, **k: client)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role="purchase_manager"):
    """Insert a test identity for the requested permission-matrix role."""
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Receipt Test User",
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": None,
        "last_login_at": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    database["users"].insert_one(user)
    return user


def auth_headers(user):
    """Build bearer-token headers for a test user."""
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


def insert_supplier(database):
    """Insert a supplier for a PO fixture."""
    now = utc_now()
    supplier = {
        "_id": ObjectId(),
        "code": f"SUP-{uuid4().hex[:8].upper()}",
        "name": "Northwind Supply",
        "name_search": "northwind supply",
        "contact_person": None,
        "email": None,
        "phone": None,
        "address": None,
        "status": "active",
        "payment_terms": None,
        "created_at": now,
        "updated_at": now,
    }
    database["suppliers"].insert_one(supplier)
    return supplier


def insert_product(database, name="Office Chair"):
    """Insert an active stock-managed product."""
    now = utc_now()
    product = {
        "_id": ObjectId(),
        "sku": f"CHAIR-{uuid4().hex[:6].upper()}",
        "name": name,
        "name_search": name.casefold(),
        "description": None,
        "category": "Furniture",
        "unit": "each",
        "cost_price": Decimal128("10.00"),
        "selling_price": Decimal128("20.00"),
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "min_stock_level": 0,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    database["products"].insert_one(product)
    return product


def create_approved_order(client, database, creator, approver, quantities):
    """Create and approve a PO from product/quantity pairs."""
    supplier = insert_supplier(database)
    response = client.post(
        "/api/purchase-orders/",
        {
            "supplier_id": str(supplier["_id"]),
            "items": [
                {
                    "product_id": str(product["_id"]),
                    "quantity_ordered": quantity,
                    "unit_cost": "12.00",
                }
                for product, quantity in quantities
            ],
            "tax_rate": "0.00",
        },
        format="json",
        **auth_headers(creator),
    )
    assert response.status_code == 201
    order = response.json()["data"]["purchase_order"]
    submitted = client.post(
        f"/api/purchase-orders/{order['id']}/submit/",
        {},
        format="json",
        **auth_headers(creator),
    )
    assert submitted.status_code == 200
    approved = client.post(
        f"/api/purchase-orders/{order['id']}/approve/",
        {},
        format="json",
        **auth_headers(approver),
    )
    assert approved.status_code == 200
    return ObjectId(order["id"]), supplier


def post_receipt(client, user, order_id, items, key=None, notes=None):
    """Post one receipt with an optional idempotency key."""
    payload = {"items": items}
    if notes is not None:
        payload["notes"] = notes
    headers = auth_headers(user)
    if key is not None:
        headers["HTTP_IDEMPOTENCY_KEY"] = key
    return client.post(
        f"/api/purchase-orders/{order_id}/receive/",
        payload,
        format="json",
        **headers,
    )


def receipt_item(product, quantity):
    """Build a receipt item request."""
    return {
        "product_id": str(product["_id"]),
        "quantity_received": quantity,
    }


def test_full_receipt_updates_order_stock_movement_and_audit(client, receipt_api):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, supplier = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 5)],
    )
    key = str(uuid4())

    response = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 5)],
        key,
        notes="Checked against delivery note.",
    )

    assert response.status_code == 201
    receipt = response.json()["data"]["purchase_receipt"]
    assert receipt["receipt_reference"].startswith(f"RCPT-{utc_now().year}-")
    assert receipt["purchase_order_id"] == str(order_id)
    assert receipt["supplier_id"] == str(supplier["_id"])
    assert receipt["received_by"] == str(approver["_id"])
    assert receipt["idempotency_key"] == key
    assert receipt["notes"] == "Checked against delivery note."
    order = receipt_api["purchase_orders"].find_one({"_id": order_id})
    assert order["status"] == "received"
    assert order["items"][0]["quantity_received"] == 5
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 5
    movement = receipt_api["stock_movements"].find_one(
        {
            "reference_type": "purchase_receipt",
            "reference_id": ObjectId(receipt["id"]),
        }
    )
    assert movement["movement_type"] == "purchase_receipt"
    assert movement["quantity_change"] == 5
    assert movement["performed_by"] == approver["_id"]
    audit = receipt_api["audit_logs"].find_one(
        {"entity_type": "purchase_order", "entity_id": str(order_id)}
    )
    assert audit["action"] == "purchase_order.received"
    assert audit["actor_id"] == approver["_id"]
    assert audit["outcome"] == "success"


def test_partial_then_final_receipt_updates_statuses(client, receipt_api):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 5)],
    )

    partial = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 2)],
        str(uuid4()),
    )
    order_after_partial = receipt_api["purchase_orders"].find_one({"_id": order_id})
    final = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 3)],
        str(uuid4()),
    )

    assert partial.status_code == final.status_code == 201
    assert order_after_partial["status"] == "partially_received"
    assert order_after_partial["items"][0]["quantity_received"] == 2
    order = receipt_api["purchase_orders"].find_one({"_id": order_id})
    assert order["status"] == "received"
    assert order["items"][0]["quantity_received"] == 5
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 5
    assert receipt_api["purchase_receipts"].count_documents({}) == 2
    statuses = [
        row["status"]
        for row in receipt_api["purchase_orders"].find_one({"_id": order_id})[
            "status_history"
        ]
    ]
    assert statuses[-2:] == ["partially_received", "received"]


def test_over_receipt_is_rejected_without_writes(client, receipt_api):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 2)],
    )

    response = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 3)],
        str(uuid4()),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"
    assert receipt_api["purchase_orders"].find_one({"_id": order_id})["items"][0][
        "quantity_received"
    ] == 0
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 0
    assert receipt_api["purchase_receipts"].count_documents({}) == 0
    assert receipt_api["stock_movements"].count_documents({}) == 0
    assert receipt_api["idempotency_keys"].count_documents({}) == 0


def test_receipt_requires_receivable_status_and_permission(client, receipt_api):
    creator = insert_user(receipt_api)
    inventory_manager = insert_user(receipt_api, role="inventory_manager")
    employee = insert_user(receipt_api, role="employee")
    product = insert_product(receipt_api)
    supplier = insert_supplier(receipt_api)
    draft = client.post(
        "/api/purchase-orders/",
        {
            "supplier_id": str(supplier["_id"]),
            "items": [
                {
                    "product_id": str(product["_id"]),
                    "quantity_ordered": 1,
                    "unit_cost": "1.00",
                }
            ],
            "tax_rate": "0.00",
        },
        format="json",
        **auth_headers(creator),
    )
    draft_id = ObjectId(draft.json()["data"]["purchase_order"]["id"])

    wrong_status = post_receipt(
        client,
        inventory_manager,
        draft_id,
        [receipt_item(product, 1)],
        str(uuid4()),
    )
    denied = post_receipt(
        client,
        employee,
        draft_id,
        [receipt_item(product, 1)],
        str(uuid4()),
    )

    assert wrong_status.status_code == 409
    assert wrong_status.json()["error"]["code"] == "invalid_state_transition"
    assert denied.status_code == 403
    assert receipt_api["purchase_receipts"].count_documents({}) == 0


def test_same_idempotency_key_replays_identical_receipt(client, receipt_api):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 2)],
    )
    key = str(uuid4())
    items = [receipt_item(product, 2)]

    first = post_receipt(client, approver, order_id, items, key)
    replay = post_receipt(client, approver, order_id, items, key)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert receipt_api["purchase_receipts"].count_documents({}) == 1
    assert receipt_api["stock_movements"].count_documents({}) == 1
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 2


def test_same_idempotency_key_with_different_body_is_rejected(
    client,
    receipt_api,
):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 3)],
    )
    key = str(uuid4())
    first = post_receipt(client, approver, order_id, [receipt_item(product, 1)], key)

    reused = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 2)],
        key,
    )

    assert first.status_code == 201
    assert reused.status_code == 422
    assert reused.json()["error"]["code"] == "idempotency_key_reused"
    assert receipt_api["purchase_receipts"].count_documents({}) == 1
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 1


@pytest.mark.parametrize("header", (None, "not-a-uuid"))
def test_receipt_requires_uuid_idempotency_header(
    client,
    receipt_api,
    header,
):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 1)],
    )

    response = post_receipt(
        client,
        approver,
        order_id,
        [receipt_item(product, 1)],
        header,
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_failure_on_later_line_rolls_back_all_receipt_stock_and_audit(
    client,
    receipt_api,
):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    first_product = insert_product(receipt_api, "First item")
    second_product = insert_product(receipt_api, "Second item")
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(first_product, 2), (second_product, 2)],
    )
    receipt_api["products"].delete_one({"_id": second_product["_id"]})

    response = post_receipt(
        client,
        approver,
        order_id,
        [
            receipt_item(first_product, 1),
            receipt_item(second_product, 1),
        ],
        str(uuid4()),
    )

    assert response.status_code == 409
    assert receipt_api["products"].find_one({"_id": first_product["_id"]})[
        "quantity_on_hand"
    ] == 0
    assert receipt_api["stock_movements"].count_documents({}) == 0
    assert receipt_api["purchase_receipts"].count_documents({}) == 0
    assert receipt_api["idempotency_keys"].count_documents({}) == 0
    assert receipt_api["audit_logs"].count_documents({}) == 0
    order = receipt_api["purchase_orders"].find_one({"_id": order_id})
    assert order["status"] == "approved"
    assert [item["quantity_received"] for item in order["items"]] == [0, 0]


def test_concurrent_receipts_cannot_exceed_ordered_quantity(client, receipt_api):
    creator = insert_user(receipt_api)
    approver = insert_user(receipt_api)
    product = insert_product(receipt_api)
    order_id, _ = create_approved_order(
        client,
        receipt_api,
        creator,
        approver,
        [(product, 5)],
    )

    def receive_once(_):
        return post_receipt(
            APIClient(),
            approver,
            order_id,
            [receipt_item(product, 4)],
            str(uuid4()),
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(receive_once, range(2)))

    assert sorted(response.status_code for response in responses) == [201, 400]
    order = receipt_api["purchase_orders"].find_one({"_id": order_id})
    assert order["items"][0]["quantity_received"] == 4
    assert order["status"] == "partially_received"
    assert receipt_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 4
    assert receipt_api["purchase_receipts"].count_documents({}) == 1
    assert receipt_api["stock_movements"].count_documents({}) == 1


def test_conditional_po_line_update_rejects_stale_quantity(receipt_api):
    product = insert_product(receipt_api)
    order_id = ObjectId()
    receipt_api["purchase_orders"].insert_one(
        {
            "_id": order_id,
            "items": [
                {
                    "product_id": product["_id"],
                    "quantity_ordered": 5,
                    "quantity_received": 4,
                }
            ],
        }
    )

    result = increment_received_quantity(
        receipt_api,
        FakeMongoSession(receipt_api.client),
        purchase_order_id=order_id,
        product_id=product["_id"],
        ordered_quantity=5,
        received_quantity=2,
    )

    assert result.modified_count == 0
    assert receipt_api["purchase_orders"].find_one({"_id": order_id})["items"][0][
        "quantity_received"
    ] == 4
