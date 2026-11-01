"""API, calculation, permission, and concurrency tests for purchase orders."""

from concurrent.futures import ThreadPoolExecutor
from datetime import timezone
from threading import Barrier, Lock
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.exceptions import InvalidStateTransition
from common.time import utc_now
from purchases.repository import allocate_po_number
from purchases.services import TRANSITIONS, transition_purchase_order
from tests.accounts.fakes import FakeDatabase

_ACTIONS = ("submit", "approve", "reject", "cancel")


@pytest.fixture
def purchase_api(monkeypatch):
    """Route authentication and purchase requests to an isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "purchase-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "purchase-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "purchase-test-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")

    class FakeMongoClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def __getitem__(self, database_name):
            assert database_name == "smarterp_test"
            return database

    factory = lambda *args, **kwargs: FakeMongoClient()
    monkeypatch.setattr("accounts.authentication.MongoClient", factory)
    monkeypatch.setattr("purchases.views.MongoClient", factory)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role):
    """Insert a test identity for the requested permission-matrix role."""
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Purchase Test User",
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
    return {
        "HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}",
    }


def insert_supplier(database, *, status="active"):
    """Insert a supplier document used by PO API tests."""
    now = utc_now()
    supplier = {
        "_id": ObjectId(),
        "code": f"SUP-{uuid4().hex[:8].upper()}",
        "name": "Northwind Supply",
        "name_search": "northwind supply",
        "contact_person": None,
        "email": "orders@example.test",
        "phone": None,
        "address": None,
        "status": status,
        "payment_terms": None,
        "created_at": now,
        "updated_at": now,
    }
    database["suppliers"].insert_one(supplier)
    return supplier


def insert_product(database, *, status=True):
    """Insert a product document used by PO API tests."""
    now = utc_now()
    product = {
        "_id": ObjectId(),
        "sku": f"CHAIR-{uuid4().hex[:6].upper()}",
        "name": "Office Chair",
        "name_search": "office chair",
        "description": None,
        "category": "Furniture",
        "unit": "each",
        "cost_price": Decimal128("10.00"),
        "selling_price": Decimal128("20.00"),
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "min_stock_level": 0,
        "is_active": status,
        "created_at": now,
        "updated_at": now,
    }
    database["products"].insert_one(product)
    return product


def create_order(client, user, supplier, product, **fields):
    """Create a PO through the public API with overridable request fields."""
    payload = {
        "supplier_id": str(supplier["_id"]),
        "items": [
            {
                "product_id": str(product["_id"]),
                "quantity_ordered": 3,
                "unit_cost": "12.34",
            }
        ],
        "tax_rate": "7.50",
        **fields,
    }
    return client.post(
        "/api/purchase-orders/",
        payload,
        format="json",
        **auth_headers(user),
    )


def update_status(database, order, status):
    """Set up a workflow state for an isolated transition test."""
    database["purchase_orders"].update_one(
        {"_id": order["_id"]},
        {"$set": {"status": status}},
    )


def action_request(client, action, order_id, user):
    """Issue a workflow request with its required body."""
    payload = (
        {"reason": "Supplier quote was not accepted."}
        if action == "reject"
        else {}
    )
    return client.post(
        f"/api/purchase-orders/{order_id}/{action}/",
        payload,
        format="json",
        **auth_headers(user),
    )


def test_create_calculates_decimal_totals_and_ignores_client_totals(
    client,
    purchase_api,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)

    response = create_order(
        client,
        manager,
        supplier,
        product,
        subtotal="999999.99",
        tax_total="888888.88",
        grand_total="777777.77",
        items=[
            {
                "product_id": str(product["_id"]),
                "quantity_ordered": 3,
                "unit_cost": "12.34",
                "line_total": "123456.78",
            }
        ],
    )

    assert response.status_code == 201
    order = response.json()["data"]["purchase_order"]
    assert order["po_number"].startswith("PO-")
    assert order["supplier_snapshot"]["name"] == supplier["name"]
    assert order["items"][0]["sku"] == product["sku"]
    assert order["items"][0]["name"] == product["name"]
    assert order["items"][0]["quantity_received"] == 0
    assert order["items"][0]["line_total"] == "37.02"
    assert order["subtotal"] == "37.02"
    assert order["tax_rate"] == "7.50"
    assert order["tax_total"] == "2.78"
    assert order["grand_total"] == "39.80"
    assert order["status"] == "draft"
    assert order["status_history"][0]["status"] == "draft"
    stored = purchase_api["purchase_orders"].find_one({"_id": ObjectId(order["id"])})
    assert isinstance(stored["subtotal"], Decimal128)
    assert isinstance(stored["tax_rate"], Decimal128)
    assert stored["created_at"].tzinfo == timezone.utc
    assert order["subtotal"] != "999999.99"


def test_decimal_tax_rounding_and_draft_patch_recalculate(
    client,
    purchase_api,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, manager, supplier, product, tax_rate="7.50")
    order_id = created.json()["data"]["purchase_order"]["id"]

    response = client.patch(
        f"/api/purchase-orders/{order_id}/",
        {"tax_rate": "7.50", "subtotal": "500.00"},
        format="json",
        **auth_headers(manager),
    )

    assert response.status_code == 200
    order = response.json()["data"]["purchase_order"]
    assert order["subtotal"] == "37.02"
    assert order["tax_total"] == "2.78"
    assert order["grand_total"] == "39.80"
    assert order["tax_rate"] == "7.50"


def test_duplicate_product_ids_are_rejected(client, purchase_api):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    items = [
        {
            "product_id": str(product["_id"]),
            "quantity_ordered": 1,
            "unit_cost": "1.00",
        }
    ] * 2

    response = create_order(client, manager, supplier, product, items=items)

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert purchase_api["purchase_orders"].count_documents({}) == 0


@pytest.mark.parametrize(
    ("supplier_status", "product_active"),
    [("inactive", True), ("active", False)],
)
def test_inactive_supplier_or_product_cannot_be_used(
    client,
    purchase_api,
    supplier_status,
    product_active,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api, status=supplier_status)
    product = insert_product(purchase_api, status=product_active)

    response = create_order(client, manager, supplier, product)

    assert response.status_code == 400
    assert purchase_api["purchase_orders"].count_documents({}) == 0


@pytest.mark.parametrize("missing_record", ("supplier", "product"))
def test_missing_supplier_or_product_cannot_be_used(
    client,
    purchase_api,
    missing_record,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    if missing_record == "supplier":
        supplier = {**supplier, "_id": ObjectId()}
        expected_status = 404
    else:
        product = {**product, "_id": ObjectId()}
        expected_status = 400

    response = create_order(client, manager, supplier, product)

    assert response.status_code == expected_status
    assert purchase_api["purchase_orders"].count_documents({}) == 0


@pytest.mark.parametrize("inactive_record", ("supplier", "product"))
def test_submit_rechecks_supplier_and_product_active_state(
    client,
    purchase_api,
    inactive_record,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, manager, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]
    collection_name = "suppliers" if inactive_record == "supplier" else "products"
    identity = supplier["_id"] if inactive_record == "supplier" else product["_id"]
    active_field = "status" if inactive_record == "supplier" else "is_active"
    inactive_value = "inactive" if inactive_record == "supplier" else False
    purchase_api[collection_name].update_one(
        {"_id": identity},
        {"$set": {active_field: inactive_value}},
    )

    response = action_request(client, "submit", order_id, manager)

    assert response.status_code == 400
    assert purchase_api["purchase_orders"].find_one(
        {"_id": ObjectId(order_id)}
    )["status"] == "draft"


@pytest.mark.parametrize(
    "fields",
    [
        {"tax_rate": "100.01"},
        {"tax_rate": "-0.01"},
        {"tax_rate": 7.5},
        {
            "items": [
                {"product_id": "bad-id", "quantity_ordered": 1, "unit_cost": "1.00"}
            ]
        },
        {
            "items": [
                {
                    "product_id": "000000000000000000000001",
                    "quantity_ordered": True,
                    "unit_cost": "1.00",
                }
            ]
        },
        {
            "items": [
                {
                    "product_id": "000000000000000000000001",
                    "quantity_ordered": 1.5,
                    "unit_cost": "1.00",
                }
            ]
        },
        {
            "items": [
                {
                    "product_id": "000000000000000000000001",
                    "quantity_ordered": 1,
                    "unit_cost": 1.25,
                }
            ]
        },
        {"$where": "true"},
        {"supplier_id.extra": "unsafe"},
        {"unknown": "value"},
    ],
)
def test_create_rejects_invalid_or_unsafe_request_fields(
    client,
    purchase_api,
    fields,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)

    response = create_order(client, manager, supplier, product, **fields)

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert purchase_api["purchase_orders"].count_documents({}) == 0


def test_generated_po_numbers_use_atomic_yearly_counter(purchase_api):
    with ThreadPoolExecutor(max_workers=8) as executor:
        numbers = list(
            executor.map(
                lambda _: allocate_po_number(purchase_api),
                range(20),
            )
        )

    year = utc_now().year
    assert sorted(numbers) == [
        f"PO-{year}-{counter:06d}" for counter in range(1, 21)
    ]


@pytest.mark.parametrize(
    ("source_status", "action", "expected_status"),
    [
        ("draft", "submit", "pending_approval"),
        ("draft", "cancel", "cancelled"),
        ("pending_approval", "approve", "approved"),
        ("pending_approval", "reject", "rejected"),
        ("pending_approval", "cancel", "cancelled"),
    ],
)
def test_every_valid_transition(
    client,
    purchase_api,
    source_status,
    action,
    expected_status,
):
    manager = insert_user(purchase_api, "purchase_manager")
    creator = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, creator, supplier, product)
    order = created.json()["data"]["purchase_order"]
    if source_status == "pending_approval":
        submitted = action_request(client, "submit", order["id"], creator)
        assert submitted.status_code == 200

    response = action_request(client, action, order["id"], manager)

    assert response.status_code == 200
    result = response.json()["data"]["purchase_order"]
    assert result["status"] == expected_status
    assert result["status_history"][-1]["status"] == expected_status
    if action == "reject":
        assert result["status_history"][-1]["note"] == "Supplier quote was not accepted."
    if action == "approve":
        assert result["approved_by"] == str(manager["_id"])


@pytest.mark.parametrize(
    ("status", "action"),
    [
        (status, action)
        for status, allowed in TRANSITIONS.items()
        for action in _ACTIONS
        if action not in allowed
    ],
)
def test_every_invalid_transition_returns_conflict_without_mutation(
    client,
    purchase_api,
    status,
    action,
):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    response = create_order(client, manager, supplier, product)
    order = response.json()["data"]["purchase_order"]
    update_status(purchase_api, {"_id": ObjectId(order["id"])}, status)
    before = purchase_api["purchase_orders"].find_one({"_id": ObjectId(order["id"])})

    result = action_request(client, action, order["id"], manager)

    after = purchase_api["purchase_orders"].find_one({"_id": ObjectId(order["id"])})
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "invalid_state_transition"
    assert after["status"] == before["status"]
    assert after["status_history"] == before["status_history"]


def test_rejection_reason_is_required(client, purchase_api):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, manager, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]
    action_request(client, "submit", order_id, manager)

    response = client.post(
        f"/api/purchase-orders/{order_id}/reject/",
        {},
        format="json",
        **auth_headers(manager),
    )

    assert response.status_code == 400
    assert response.json()["error"]["code"] == "validation_error"


def test_creator_cannot_approve_but_super_admin_can(client, purchase_api):
    creator = insert_user(purchase_api, "purchase_manager")
    admin = insert_user(purchase_api, "super_admin")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, creator, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]
    action_request(client, "submit", order_id, creator)

    denied = action_request(client, "approve", order_id, creator)
    approved = action_request(client, "approve", order_id, admin)

    assert denied.status_code == 403
    assert denied.json()["error"]["code"] == "permission_denied"
    assert approved.status_code == 200
    assert approved.json()["data"]["purchase_order"]["status"] == "approved"


def test_permission_matrix_gates_list_create_patch_and_actions(
    client,
    purchase_api,
):
    employee = insert_user(purchase_api, "employee")
    inventory_manager = insert_user(purchase_api, "inventory_manager")
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)

    denied_list = client.get(
        "/api/purchase-orders/",
        **auth_headers(employee),
    )
    denied_create = create_order(client, employee, supplier, product)
    created = create_order(client, manager, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]
    denied_patch = client.patch(
        f"/api/purchase-orders/{order_id}/",
        {"tax_rate": "0.00"},
        format="json",
        **auth_headers(inventory_manager),
    )
    denied_approve = action_request(client, "approve", order_id, inventory_manager)
    denied_unsafe_action = client.post(
        f"/api/purchase-orders/{order_id}/approve/",
        {"$where": "true"},
        format="json",
        **auth_headers(inventory_manager),
    )

    assert denied_list.status_code == 403
    assert denied_create.status_code == 403
    assert denied_patch.status_code == 403
    assert denied_approve.status_code == 403
    assert denied_unsafe_action.status_code == 403


def test_patch_is_rejected_after_submit(client, purchase_api):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, manager, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]
    action_request(client, "submit", order_id, manager)

    response = client.patch(
        f"/api/purchase-orders/{order_id}/",
        {"tax_rate": "3.00"},
        format="json",
        **auth_headers(manager),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "invalid_state_transition"


def test_double_approve_race_only_allows_one_conditional_update(
    purchase_api,
    monkeypatch,
):
    creator_id = ObjectId()
    order = {
        "_id": ObjectId(),
        "po_number": f"PO-{utc_now().year}-000001",
        "supplier_id": ObjectId(),
        "supplier_snapshot": {"code": "SUP-1", "name": "Supplier", "email": None},
        "items": [],
        "tax_rate": Decimal128("0.00"),
        "subtotal": Decimal128("0.00"),
        "tax_total": Decimal128("0.00"),
        "grand_total": Decimal128("0.00"),
        "status": "pending_approval",
        "created_by": creator_id,
        "approved_by": None,
        "status_history": [
            {
                "status": "pending_approval",
                "by": creator_id,
                "at": utc_now(),
                "note": None,
            }
        ],
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    purchase_api["purchase_orders"].insert_one(order)
    approvers = (ObjectId(), ObjectId())
    collection = purchase_api["purchase_orders"]
    original_find_one = collection.find_one
    read_barrier = Barrier(2)
    read_lock = Lock()
    synchronized_reads = 0

    def synchronized_find_one(query, **kwargs):
        nonlocal synchronized_reads
        document = original_find_one(query, **kwargs)
        with read_lock:
            should_wait = synchronized_reads < 2
            synchronized_reads += 1
        if should_wait:
            read_barrier.wait(timeout=5)
        return document

    monkeypatch.setattr(collection, "find_one", synchronized_find_one)

    def approve(actor_id):
        return transition_purchase_order(
            purchase_api,
            order["_id"],
            action="approve",
            actor_id=actor_id,
        )

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [executor.submit(approve, actor_id) for actor_id in approvers]
    outcomes = []
    for future in futures:
        try:
            outcomes.append(future.result())
        except InvalidStateTransition:
            outcomes.append(None)

    stored = purchase_api["purchase_orders"].find_one({"_id": order["_id"]})
    assert sum(outcome is not None for outcome in outcomes) == 1
    assert stored["status"] == "approved"
    assert len(stored["status_history"]) == 2
    assert stored["approved_by"] in approvers


def test_get_list_and_invalid_object_id(client, purchase_api):
    manager = insert_user(purchase_api, "purchase_manager")
    supplier = insert_supplier(purchase_api)
    product = insert_product(purchase_api)
    created = create_order(client, manager, supplier, product)
    order_id = created.json()["data"]["purchase_order"]["id"]

    detail = client.get(
        f"/api/purchase-orders/{order_id}/",
        **auth_headers(manager),
    )
    listing = client.get("/api/purchase-orders/?status=draft", **auth_headers(manager))
    invalid = client.get("/api/purchase-orders/not-an-id/", **auth_headers(manager))

    assert detail.status_code == 200
    assert listing.status_code == 200
    assert listing.json()["data"]["purchase_orders"][0]["id"] == order_id
    assert listing.json()["meta"]["total"] == 1
    assert invalid.status_code == 400
