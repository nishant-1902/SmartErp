"""API and business-rule tests for supplier records and purchase history."""

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.exceptions import NotFoundError, ValidationFailed
from common.time import utc_now
from suppliers.services import require_active_supplier
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def supplier_api(monkeypatch):
    """Route authentication and supplier requests to one isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "supplier-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "supplier-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "supplier-test-client")
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
    monkeypatch.setattr("suppliers.views.MongoClient", factory)
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
        "full_name": "Supplier Test User",
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


def create_supplier(client, user, **fields):
    """Create a supplier through the public API."""
    return client.post(
        "/api/suppliers/",
        {"name": "Northwind Supply", **fields},
        format="json",
        **auth_headers(user),
    )


def insert_supplier(database, *, status="active", code="SUP-EXISTING"):
    """Insert a supplier document for focused history and guard tests."""
    now = utc_now()
    supplier = {
        "_id": ObjectId(),
        "code": code,
        "name": "Existing Supply",
        "name_search": "existing supply",
        "contact_person": None,
        "email": None,
        "phone": None,
        "address": None,
        "status": status,
        "payment_terms": None,
        "created_at": now,
        "updated_at": now,
    }
    database["suppliers"].insert_one(supplier)
    return supplier


def insert_purchase_order(database, supplier, *, status, created_at=None):
    """Insert a schema-shaped order for supplier history tests."""
    now = created_at or utc_now()
    order = {
        "_id": ObjectId(),
        "po_number": f"PO-{uuid4().hex[:8].upper()}",
        "supplier_id": supplier["_id"],
        "supplier_snapshot": {
            "code": supplier["code"],
            "name": supplier["name"],
            "email": supplier["email"],
        },
        "items": [
            {
                "product_id": ObjectId(),
                "sku": "CHAIR-01",
                "name": "Office Chair",
                "quantity_ordered": 5,
                "quantity_received": 2,
                "unit_cost": Decimal128("10.00"),
                "line_total": Decimal128("50.00"),
            }
        ],
        "status": status,
        "subtotal": Decimal128("50.00"),
        "tax_total": Decimal128("5.00"),
        "grand_total": Decimal128("55.00"),
        "created_by": ObjectId(),
        "approved_by": None,
        "status_history": [
            {
                "status": status,
                "by": ObjectId(),
                "at": now,
                "note": None,
            }
        ],
        "created_at": now,
        "updated_at": now,
    }
    database["purchase_orders"].insert_one(order)
    return order


def test_purchase_manager_can_create_supplier_with_generated_code(client, supplier_api):
    purchase_manager = insert_user(supplier_api, "purchase_manager")

    response = create_supplier(
        client,
        purchase_manager,
        contact_person="  Ada Lovelace ",
        email=" BUYING@Example.Test ",
        phone="+1 (415) 555-0123",
        payment_terms=" Net 30 ",
    )

    assert response.status_code == 201
    supplier = response.json()["data"]["supplier"]
    stored = supplier_api["suppliers"].find_one({"_id": ObjectId(supplier["id"])})
    assert supplier["code"] == "SUP-000001"
    assert supplier["name"] == "Northwind Supply"
    assert supplier["contact_person"] == "Ada Lovelace"
    assert supplier["email"] == "buying@example.test"
    assert supplier["phone"] == "+14155550123"
    assert supplier["status"] == "active"
    assert supplier["payment_terms"] == "Net 30"
    assert stored["created_at"].tzinfo == timezone.utc
    assert "name_search" not in supplier
    assert supplier_api["counters"].find_one({"_id": "supplier_code"})["value"] == 1


def test_supplier_code_can_be_supplied_and_is_case_insensitively_unique(
    client,
    supplier_api,
):
    purchase_manager = insert_user(supplier_api, "purchase_manager")

    created = create_supplier(client, purchase_manager, code=" vendor-42 ")
    duplicate = create_supplier(client, purchase_manager, code="VENDOR-42")

    assert created.status_code == 201
    assert created.json()["data"]["supplier"]["code"] == "VENDOR-42"
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "conflict"


@pytest.mark.parametrize(
    ("fields", "expected_status"),
    [
        ({"email": "not-an-email"}, 400),
        ({"phone": "555-ABCD"}, 400),
        ({"phone": "+123"}, 400),
        ({"status": "pending"}, 400),
        ({"name": " "}, 400),
        ({"$where": "true"}, 400),
        ({"unknown": "value"}, 400),
        (
            {
                "address": {
                    "line1": "1 Main St",
                    "city": "London",
                    "country": "UK",
                    "$ne": "bad",
                }
            },
            400,
        ),
    ],
)
def test_supplier_create_rejects_invalid_or_unsafe_input(
    client,
    supplier_api,
    fields,
    expected_status,
):
    purchase_manager = insert_user(supplier_api, "purchase_manager")

    response = create_supplier(client, purchase_manager, **fields)

    assert response.status_code == expected_status
    assert response.json()["success"] is False
    assert supplier_api["suppliers"].count_documents({}) == 0


@pytest.mark.parametrize(
    ("role", "can_read", "can_write"),
    [
        ("super_admin", True, True),
        ("purchase_manager", True, True),
        ("inventory_manager", True, False),
        ("sales_manager", False, False),
        ("employee", False, False),
    ],
)
def test_supplier_read_and_write_permissions_follow_role_matrix(
    client,
    supplier_api,
    role,
    can_read,
    can_write,
):
    user = insert_user(supplier_api, role)

    listing = client.get("/api/suppliers/", **auth_headers(user))
    creation = create_supplier(client, user)

    assert listing.status_code == (200 if can_read else 403)
    assert creation.status_code == (201 if can_write else 403)


def test_supplier_list_search_filter_and_pagination(client, supplier_api):
    purchase_manager = insert_user(supplier_api, "purchase_manager")
    create_supplier(
        client,
        purchase_manager,
        code="VEND-A",
        name="Northwind Parts",
        status="active",
    )
    create_supplier(
        client,
        purchase_manager,
        code="VEND-B",
        name="Southwind Parts",
        status="inactive",
    )
    create_supplier(
        client,
        purchase_manager,
        code="VEND-C",
        name="Northwind Tools",
        status="active",
    )

    response = client.get(
        "/api/suppliers/?search=Northwind&status=active&page=2&page_size=1",
        **auth_headers(purchase_manager),
    )

    assert response.status_code == 200
    assert len(response.json()["data"]["suppliers"]) == 1
    assert response.json()["meta"] == {
        "page": 2,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }


@pytest.mark.parametrize(
    "query",
    [
        "unknown=value",
        "status=deleted",
        "sort_by=name_search",
        "page=0",
        "page_size=101",
        "%24where=true",
    ],
)
def test_supplier_list_rejects_invalid_query_parameters(client, supplier_api, query):
    purchase_manager = insert_user(supplier_api, "purchase_manager")

    response = client.get(
        f"/api/suppliers/?{query}",
        **auth_headers(purchase_manager),
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_supplier_detail_patch_and_object_id_validation(client, supplier_api):
    purchase_manager = insert_user(supplier_api, "purchase_manager")
    created = create_supplier(client, purchase_manager, code="PATCH-ME")
    supplier = created.json()["data"]["supplier"]

    detail = client.get(
        f"/api/suppliers/{supplier['id']}/",
        **auth_headers(purchase_manager),
    )
    updated = client.patch(
        f"/api/suppliers/{supplier['id']}/",
        {"name": "Updated Name", "status": "inactive"},
        format="json",
        **auth_headers(purchase_manager),
    )
    invalid_id = client.get(
        "/api/suppliers/not-an-object-id/",
        **auth_headers(purchase_manager),
    )

    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["supplier"]["name"] == "Updated Name"
    assert updated.json()["data"]["supplier"]["status"] == "inactive"
    assert invalid_id.status_code == 400


def test_supplier_patch_rejects_empty_and_unknown_fields(client, supplier_api):
    purchase_manager = insert_user(supplier_api, "purchase_manager")
    supplier_id = create_supplier(
        client,
        purchase_manager,
        code="PATCH-VALIDATE",
    ).json()["data"]["supplier"]["id"]

    empty = client.patch(
        f"/api/suppliers/{supplier_id}/",
        {},
        format="json",
        **auth_headers(purchase_manager),
    )
    unknown = client.patch(
        f"/api/suppliers/{supplier_id}/",
        {"created_at": "2020-01-01"},
        format="json",
        **auth_headers(purchase_manager),
    )

    assert empty.status_code == 400
    assert unknown.status_code == 400


def test_history_returns_paginated_purchase_orders_and_open_orders(
    client,
    supplier_api,
):
    inventory_manager = insert_user(supplier_api, "inventory_manager")
    supplier = insert_supplier(supplier_api)
    other_supplier = insert_supplier(supplier_api, code="SUP-OTHER")
    statuses = (
        "draft",
        "pending_approval",
        "approved",
        "partially_received",
        "received",
        "rejected",
        "cancelled",
    )
    for index, status in enumerate(statuses):
        insert_purchase_order(
            supplier_api,
            supplier,
            status=status,
            created_at=datetime(2026, 1, index + 1, tzinfo=timezone.utc),
        )
    insert_purchase_order(supplier_api, other_supplier, status="approved")

    response = client.get(
        f"/api/suppliers/{supplier['_id']}/purchase-orders/?page=1&page_size=2",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 200
    data = response.json()["data"]
    assert len(data["purchase_orders"]) == 2
    assert [order["status"] for order in data["outstanding_purchase_orders"]] == [
        "partially_received",
        "approved",
    ]
    assert all(
        item["quantity_outstanding"] == 3
        for order in data["outstanding_purchase_orders"]
        for item in order["items"]
    )
    assert response.json()["meta"] == {
        "purchase_orders": {
            "page": 1,
            "page_size": 2,
            "total": 7,
            "total_pages": 4,
        },
        "outstanding_purchase_orders": {
            "page": 1,
            "page_size": 2,
            "total": 3,
            "total_pages": 2,
        },
    }
    assert data["purchase_orders"][0]["grand_total"] == str(Decimal("55.00"))


def test_purchase_history_requires_purchase_read_permission(client, supplier_api):
    hr_manager = insert_user(supplier_api, "hr_manager")
    supplier = insert_supplier(supplier_api)

    response = client.get(
        f"/api/suppliers/{supplier['_id']}/purchase-orders/",
        **auth_headers(hr_manager),
    )

    assert response.status_code == 403


def test_active_supplier_guard_rejects_inactive_and_missing_suppliers(supplier_api):
    active = insert_supplier(supplier_api)
    inactive = insert_supplier(supplier_api, status="inactive", code="SUP-INACTIVE")

    assert require_active_supplier(supplier_api, active["_id"])["_id"] == active["_id"]
    with pytest.raises(ValidationFailed):
        require_active_supplier(supplier_api, inactive["_id"])
    with pytest.raises(NotFoundError):
        require_active_supplier(supplier_api, ObjectId())
