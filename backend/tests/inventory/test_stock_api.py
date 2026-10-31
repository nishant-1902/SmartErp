"""Stock transaction, idempotency, and movement API tests."""

from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import RLock
from urllib.parse import urlencode
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.exceptions import InsufficientStock, ValidationFailed
from common.time import utc_now
from inventory.services import adjust_stock, apply_stock_change
from tests.accounts.fakes import FakeDatabase


class FakeMongoSession:
    """Provide transaction behavior with rollback and thread serialization."""

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
    """Provide the database and session methods used by the stock services."""

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
def stock_api(monkeypatch):
    """Route stock API requests to an isolated transactional fake database."""
    database = FakeDatabase()
    client = FakeMongoClient(database)
    database.client = client
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "stock-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "stock-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "stock-test-client")
    monkeypatch.setattr(settings, "MONGO_URI", "mongodb://localhost:27017")
    monkeypatch.setattr(settings, "MONGO_DB_NAME", "smarterp_test")
    monkeypatch.setattr("accounts.authentication.MongoClient", lambda *a, **k: client)
    monkeypatch.setattr("inventory.views.MongoClient", lambda *a, **k: client)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role="inventory_manager"):
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Stock Test User",
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
    token = create_access_token(user)
    return {"HTTP_AUTHORIZATION": f"Bearer {token}"}


def insert_product(database, *, quantity=10, reserved=0):
    now = utc_now()
    product = {
        "_id": ObjectId(),
        "sku": f"STOCK-{uuid4().hex[:8].upper()}",
        "name": "Stock test item",
        "name_search": "stock test item",
        "description": None,
        "category": "Testing",
        "unit": "each",
        "cost_price": Decimal128(Decimal("1.00")),
        "selling_price": Decimal128(Decimal("2.00")),
        "quantity_on_hand": quantity,
        "reserved_quantity": reserved,
        "min_stock_level": 0,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    database["products"].insert_one(product)
    return product


def post_adjustment(client, user, product_id, quantity_change, key, reason="Cycle count"):
    return client.post(
        "/api/stock-adjustments/",
        {
            "product_id": str(product_id),
            "quantity_change": quantity_change,
            "reason": reason,
        },
        format="json",
        HTTP_IDEMPOTENCY_KEY=key,
        **auth_headers(user),
    )


def test_adjustment_up_and_down_record_movements(client, stock_api):
    user = insert_user(stock_api)
    product = insert_product(stock_api, quantity=10, reserved=2)

    increase = post_adjustment(
        client,
        user,
        product["_id"],
        5,
        str(uuid4()),
    )
    decrease = post_adjustment(
        client,
        user,
        product["_id"],
        -4,
        str(uuid4()),
        reason="Damaged stock",
    )

    assert increase.status_code == 201
    assert decrease.status_code == 201
    stored_product = stock_api["products"].find_one({"_id": product["_id"]})
    assert stored_product["quantity_on_hand"] == 11
    movements = list(stock_api["stock_movements"].documents.values())
    assert len(movements) == 2
    assert sorted(
        (movement["quantity_before"], movement["quantity_change"], movement["quantity_after"])
        for movement in movements
    ) == [(10, 5, 15), (15, -4, 11)]
    for movement in movements:
        assert movement["quantity_before"] + movement["quantity_change"] == (
            movement["quantity_after"]
        )
        assert movement["reserved_change"] == 0
        assert movement["reference_type"] == "stock_adjustment"
        assert movement["performed_by"] == user["_id"]


def test_reduction_cannot_consume_reserved_stock(client, stock_api):
    user = insert_user(stock_api)
    product = insert_product(stock_api, quantity=10, reserved=6)

    response = post_adjustment(
        client,
        user,
        product["_id"],
        -5,
        str(uuid4()),
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "insufficient_stock"
    assert stock_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 10
    assert stock_api["stock_movements"].count_documents({}) == 0
    assert stock_api["idempotency_keys"].count_documents({}) == 0


def test_same_idempotency_key_replays_response_without_second_adjustment(
    client,
    stock_api,
):
    user = insert_user(stock_api)
    product = insert_product(stock_api)
    key = str(uuid4())

    first = post_adjustment(client, user, product["_id"], 3, key)
    replay = post_adjustment(client, user, product["_id"], 3, key)

    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert stock_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 13
    assert stock_api["stock_movements"].count_documents({}) == 1
    assert stock_api["idempotency_keys"].count_documents({}) == 1


def test_same_key_with_different_body_returns_422(client, stock_api):
    user = insert_user(stock_api)
    product = insert_product(stock_api)
    key = str(uuid4())
    assert post_adjustment(client, user, product["_id"], 3, key).status_code == 201

    response = post_adjustment(client, user, product["_id"], 4, key)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "idempotency_key_reused"
    assert stock_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 13
    assert stock_api["stock_movements"].count_documents({}) == 1


def test_concurrent_reductions_cannot_oversell(stock_api):
    user = insert_user(stock_api)
    product = insert_product(stock_api, quantity=10)

    def decrease(index):
        try:
            return adjust_stock(
                stock_api,
                product_id=product["_id"],
                quantity_change=-7,
                reason="Concurrent count",
                user_id=user["_id"],
                idempotency_key=str(uuid4()),
            )
        except InsufficientStock:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(decrease, range(2)))

    assert sum(result is not None for result in results) == 1
    assert stock_api["products"].find_one({"_id": product["_id"]})[
        "quantity_on_hand"
    ] == 3
    movements = list(stock_api["stock_movements"].documents.values())
    assert len(movements) == 1
    assert movements[0]["quantity_before"] == 10
    assert movements[0]["quantity_change"] == -7
    assert movements[0]["quantity_after"] == 3


def test_stock_movement_list_filters_and_paginates_newest_first(
    client,
    stock_api,
):
    inventory_manager = insert_user(stock_api)
    hr_manager = insert_user(stock_api, role="hr_manager")
    product = insert_product(stock_api)
    older_key = str(uuid4())
    newer_key = str(uuid4())
    post_adjustment(client, inventory_manager, product["_id"], 2, older_key)
    post_adjustment(client, inventory_manager, product["_id"], 1, newer_key)

    response = client.get(
        "/api/stock-movements/"
        f"?product={product['_id']}&type=adjustment&user={inventory_manager['_id']}"
        "&page=1&page_size=1",
        **auth_headers(hr_manager),
    )

    assert response.status_code == 200
    movements = response.json()["data"]["stock_movements"]
    assert len(movements) == 1
    assert movements[0]["quantity_change"] == 1
    assert response.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    recent = max(
        stock_api["stock_movements"].documents.values(),
        key=lambda movement: movement["created_at"],
    )
    date_query = urlencode(
        {
            "start_date": recent["created_at"].isoformat(),
            "end_date": recent["created_at"].isoformat(),
        }
    )
    date_range = client.get(
        f"/api/stock-movements/?{date_query}",
        **auth_headers(hr_manager),
    )
    assert date_range.status_code == 200
    assert date_range.json()["meta"]["total"] == 1


def test_adjustment_requires_uuid_and_stock_adjust_permission(client, stock_api):
    inventory_manager = insert_user(stock_api)
    employee = insert_user(stock_api, role="employee")
    product = insert_product(stock_api)

    missing_key = client.post(
        "/api/stock-adjustments/",
        {
            "product_id": str(product["_id"]),
            "quantity_change": 1,
            "reason": "Audit count",
        },
        format="json",
        **auth_headers(inventory_manager),
    )
    invalid_key = post_adjustment(
        client,
        inventory_manager,
        product["_id"],
        1,
        "not-a-uuid",
    )
    denied = post_adjustment(
        client,
        employee,
        product["_id"],
        1,
        str(uuid4()),
    )

    assert missing_key.status_code == 400
    assert invalid_key.status_code == 400
    assert denied.status_code == 403


@pytest.mark.parametrize(
    ("quantity_change", "reason"),
    [(0, "Count"), (1, "ab")],
)
def test_adjustment_rejects_zero_delta_and_short_reason(
    client,
    stock_api,
    quantity_change,
    reason,
):
    user = insert_user(stock_api)
    product = insert_product(stock_api)

    response = post_adjustment(
        client,
        user,
        product["_id"],
        quantity_change,
        str(uuid4()),
        reason=reason,
    )

    assert response.status_code == 400


def test_fulfilment_and_reservation_release_require_reserved_quantity(stock_api):
    product = insert_product(stock_api, quantity=10, reserved=3)
    user = insert_user(stock_api)
    session = FakeMongoSession(stock_api.client)

    fulfilment = apply_stock_change(
        session,
        product["_id"],
        -2,
        -2,
        "sale_fulfilment",
        "Fulfil confirmed sale",
        "sales_order",
        ObjectId(),
        user["_id"],
    )
    release = apply_stock_change(
        session,
        product["_id"],
        0,
        -1,
        "reservation_release",
        "Cancel reservation",
        "sales_order",
        ObjectId(),
        user["_id"],
    )

    assert fulfilment["quantity_before"] == 10
    assert fulfilment["quantity_after"] == 8
    assert fulfilment["reserved_change"] == -2
    assert release["quantity_before"] == 8
    assert release["quantity_after"] == 8
    assert release["reserved_change"] == -1
    with pytest.raises(InsufficientStock):
        apply_stock_change(
            session,
            product["_id"],
            -1,
            -1,
            "sale_fulfilment",
            "Over-fulfil",
            "sales_order",
            ObjectId(),
            user["_id"],
        )


def test_invalid_movement_filters_and_unsupported_methods_are_rejected(
    client,
    stock_api,
):
    hr_manager = insert_user(stock_api, role="hr_manager")

    invalid_id = client.get(
        "/api/stock-movements/?product=bad-id",
        **auth_headers(hr_manager),
    )
    invalid_dates = client.get(
        "/api/stock-movements/?start_date=2026-10-31T12:00:00Z"
        "&end_date=2026-10-30T12:00:00Z",
        **auth_headers(hr_manager),
    )
    no_update_route = client.patch(
        "/api/stock-movements/",
        {},
        format="json",
        **auth_headers(hr_manager),
    )

    assert invalid_id.status_code == 400
    assert invalid_dates.status_code == 400
    assert no_update_route.status_code == 405
