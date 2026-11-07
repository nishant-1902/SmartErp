"""API and business-rule tests for product catalogue endpoints."""

from decimal import Decimal
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.exceptions import ValidationFailed
from common.time import utc_now
from inventory.services import get_active_product_for_order
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def products_api(monkeypatch):
    """Route product requests and authentication to an isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "product-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "product-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "product-test-client")
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
    monkeypatch.setattr("inventory.views.MongoClient", factory)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role):
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Product Test User",
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


def create_product(client, user, **fields):
    body = {
        "sku": "PART-001",
        "name": "Widget",
        "category": "Hardware",
        "unit": "each",
        "cost_price": "1.25",
        "selling_price": "2.50",
        "min_stock_level": 5,
        **fields,
    }
    return client.post(
        "/api/products/",
        body,
        format="json",
        **auth_headers(user),
    )


def insert_product(database, **overrides):
    now = utc_now()
    product = {
        "_id": ObjectId(),
        "sku": f"PART-{uuid4().hex[:8].upper()}",
        "name": "Test widget",
        "name_search": "test widget",
        "description": None,
        "category": "Hardware",
        "unit": "each",
        "cost_price": Decimal128("1.25"),
        "selling_price": Decimal128("2.50"),
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "min_stock_level": 5,
        "available_quantity": 0,
        "is_low_stock": True,
        "is_active": True,
        "created_at": now,
        "updated_at": now,
    }
    product.update(overrides)
    product["available_quantity"] = (
        product["quantity_on_hand"] - product["reserved_quantity"]
    )
    product["is_low_stock"] = (
        product["available_quantity"] <= product["min_stock_level"]
    )
    database["products"].insert_one(product)
    return product


def test_inventory_manager_can_create_and_read_product(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")

    created = create_product(
        client,
        inventory_manager,
        sku=" part-001 ",
        description="A test component",
    )

    assert created.status_code == 201
    product = created.json()["data"]["product"]
    assert product["sku"] == "PART-001"
    assert product["name"] == "Widget"
    assert product["description"] == "A test component"
    assert product["cost_price"] == "1.25"
    assert product["selling_price"] == "2.50"
    assert product["quantity_on_hand"] == 0
    assert product["reserved_quantity"] == 0
    assert product["min_stock_level"] == 5
    assert product["is_active"] is True
    assert "name_search" not in product
    assert product["created_at"].endswith("+00:00")

    detail = client.get(
        f"/api/products/{product['id']}/",
        **auth_headers(inventory_manager),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["product"]["id"] == product["id"]


@pytest.mark.parametrize(
    "body",
    [
        {"quantity_on_hand": 4},
        {"reserved_quantity": 2},
    ],
)
def test_create_rejects_client_supplied_stock_values(client, products_api, body):
    inventory_manager = insert_user(products_api, "inventory_manager")

    response = create_product(client, inventory_manager, **body)

    assert response.status_code == 400
    assert response.json()["success"] is False


@pytest.mark.parametrize("price_field", ["cost_price", "selling_price"])
@pytest.mark.parametrize("price", ["0", "-1.00"])
def test_create_requires_positive_prices(
    client,
    products_api,
    price_field,
    price,
):
    inventory_manager = insert_user(products_api, "inventory_manager")

    response = create_product(
        client,
        inventory_manager,
        **{price_field: price},
    )

    assert response.status_code == 400


def test_duplicate_sku_is_case_insensitive_conflict(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")
    assert create_product(client, inventory_manager, sku="part-001").status_code == 201

    duplicate = create_product(client, inventory_manager, sku="PART-001")

    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


def test_roles_follow_product_read_and_write_permissions(client, products_api):
    hr_manager = insert_user(products_api, "hr_manager")
    inventory_manager = insert_user(products_api, "inventory_manager")
    employee = insert_user(products_api, "employee")

    assert create_product(client, hr_manager).status_code == 403
    assert create_product(client, inventory_manager).status_code == 201
    assert client.get("/api/products/", **auth_headers(hr_manager)).status_code == 200
    assert client.get("/api/products/", **auth_headers(employee)).status_code == 403


def test_patch_rejects_stock_changes_and_sku_edits_with_clear_errors(
    client,
    products_api,
):
    inventory_manager = insert_user(products_api, "inventory_manager")
    product = create_product(client, inventory_manager).json()["data"]["product"]

    stock_change = client.patch(
        f"/api/products/{product['id']}/",
        {"quantity_on_hand": 10},
        format="json",
        **auth_headers(inventory_manager),
    )
    reserved_change = client.patch(
        f"/api/products/{product['id']}/",
        {"reserved_quantity": 2},
        format="json",
        **auth_headers(inventory_manager),
    )
    sku_change = client.patch(
        f"/api/products/{product['id']}/",
        {"sku": "PART-002"},
        format="json",
        **auth_headers(inventory_manager),
    )

    assert stock_change.status_code == 400
    assert "stock operations" in stock_change.json()["error"]["details"]["fields"]
    assert reserved_change.status_code == 400
    assert "stock operations" in reserved_change.json()["error"]["details"]["fields"]
    assert sku_change.status_code == 400
    assert "SKU is immutable" in sku_change.json()["error"]["details"]["sku"]


def test_patch_updates_editable_fields_and_decimal128_values(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")
    product = create_product(client, inventory_manager).json()["data"]["product"]

    response = client.patch(
        f"/api/products/{product['id']}/",
        {
            "name": "Updated widget",
            "selling_price": "3.75",
            "is_active": False,
        },
        format="json",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 200
    updated = response.json()["data"]["product"]
    assert updated["sku"] == "PART-001"
    assert updated["name"] == "Updated widget"
    assert updated["selling_price"] == "3.75"
    assert updated["is_active"] is False
    stored = products_api["products"].find_one({"_id": ObjectId(updated["id"])})
    assert isinstance(stored["selling_price"], Decimal128)
    assert stored["selling_price"].to_decimal() == Decimal("3.75")
    assert stored["quantity_on_hand"] == 0


def test_patch_recalculates_materialized_low_stock_value(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")
    product = insert_product(
        products_api,
        quantity_on_hand=8,
        reserved_quantity=1,
        min_stock_level=3,
    )

    response = client.patch(
        f"/api/products/{product['_id']}/",
        {"min_stock_level": 7},
        format="json",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 200
    stored = products_api["products"].find_one({"_id": product["_id"]})
    assert stored["available_quantity"] == 7
    assert stored["is_low_stock"] is True


def test_product_search_filters_sorting_and_pagination(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")
    insert_product(
        products_api,
        sku="GEAR-01",
        name="Blue gear",
        name_search="blue gear",
        category="Hardware",
    )
    insert_product(
        products_api,
        sku="CABLE-02",
        name="Blue cable",
        name_search="blue cable",
        category="Hardware",
    )
    insert_product(
        products_api,
        sku="PAPER-03",
        name="Blue paper",
        name_search="blue paper",
        category="Office",
        is_active=False,
    )

    response = client.get(
        "/api/products/?search=blue&category=Hardware&is_active=true"
        "&page=2&page_size=1&sort_by=sku&sort_order=asc",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 200
    data = response.json()["data"]["products"]
    assert [product["sku"] for product in data] == ["GEAR-01"]
    assert response.json()["meta"] == {
        "page": 2,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }


def test_low_stock_uses_available_quantity_and_supports_list_filter(
    client,
    products_api,
):
    inventory_manager = insert_user(products_api, "inventory_manager")
    low = insert_product(
        products_api,
        sku="LOW-01",
        quantity_on_hand=5,
        reserved_quantity=2,
        min_stock_level=3,
    )
    insert_product(
        products_api,
        sku="OK-01",
        quantity_on_hand=7,
        reserved_quantity=1,
        min_stock_level=5,
    )

    low_stock_response = client.get(
        "/api/products/low-stock/",
        **auth_headers(inventory_manager),
    )
    filtered_response = client.get(
        "/api/products/?low_stock=true",
        **auth_headers(inventory_manager),
    )

    assert low_stock_response.status_code == 200
    assert [item["sku"] for item in low_stock_response.json()["data"]["products"]] == [
        low["sku"]
    ]
    assert [item["sku"] for item in filtered_response.json()["data"]["products"]] == [
        low["sku"]
    ]


def test_categories_route_precedes_product_id_route(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")
    insert_product(products_api, category="Tools")
    insert_product(products_api, category="Hardware")
    insert_product(products_api, category="Tools")

    response = client.get(
        "/api/products/categories/",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 200
    assert response.json()["data"]["categories"] == ["Hardware", "Tools"]


def test_invalid_product_id_and_unsafe_filters_are_rejected(client, products_api):
    inventory_manager = insert_user(products_api, "inventory_manager")

    invalid_id = client.get(
        "/api/products/not-an-object-id/",
        **auth_headers(inventory_manager),
    )
    unsafe_filter = client.get(
        "/api/products/?$where=true",
        **auth_headers(inventory_manager),
    )

    assert invalid_id.status_code == 400
    assert unsafe_filter.status_code == 400


def test_inactive_products_are_rejected_for_new_order_references(
    client,
    products_api,
):
    inventory_manager = insert_user(products_api, "inventory_manager")
    product = create_product(client, inventory_manager).json()["data"]["product"]

    active = get_active_product_for_order(
        products_api,
        ObjectId(product["id"]),
    )
    assert active["id"] == product["id"]

    client.patch(
        f"/api/products/{product['id']}/",
        {"is_active": False},
        format="json",
        **auth_headers(inventory_manager),
    )
    with pytest.raises(ValidationFailed, match="Inactive products"):
        get_active_product_for_order(products_api, ObjectId(product["id"]))
