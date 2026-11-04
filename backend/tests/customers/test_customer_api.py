"""API and business-rule tests for customer records and sales history."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def customer_api(monkeypatch):
    """Route customer requests and JWT lookups to an isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "customer-test-secret-at-least-32-bytes")
    monkeypatch.setattr(settings, "JWT_ISSUER", "customer-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "customer-test-client")
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
    monkeypatch.setattr("customers.views.MongoClient", factory)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role):
    """Insert a test identity for the requested permission-matrix role."""
    now = utc_now()
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Customer Test User",
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
    return {
        "HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}",
    }


def create_customer(client, user, **fields):
    """Create a customer through the public API."""
    return client.post(
        "/api/customers/",
        {"code": "CUS-001", "name": "Acme Stores", **fields},
        format="json",
        **auth_headers(user),
    )


def insert_customer(database, *, code="CUS-001", status="active"):
    """Insert a customer record for focused history tests."""
    now = utc_now()
    customer = {
        "_id": ObjectId(),
        "code": code,
        "name": "Acme Stores",
        "name_search": "acme stores",
        "email": "ap@acme.example",
        "phone": "+15551231111",
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


def insert_sales_order(database, customer, *, status, created_at=None):
    """Insert a schema-shaped order for customer history tests."""
    now = created_at or utc_now()
    order = {
        "_id": ObjectId(),
        "order_number": f"SO-{uuid4().hex[:8].upper()}",
        "customer_id": customer["_id"],
        "customer_snapshot": {"code": customer["code"], "name": customer["name"]},
        "items": [],
        "status": status,
        "return_status": "none",
        "payment_status": "unpaid",
        "subtotal": Decimal128("12.00"),
        "discount_total": Decimal128("0.00"),
        "tax_total": Decimal128("0.00"),
        "grand_total": Decimal128("12.00"),
        "created_by": ObjectId(),
        "created_at": now,
        "updated_at": now,
        "fulfilled_at": None,
        "status_history": [],
    }
    database["sales_orders"].insert_one(order)
    return order


def test_sales_manager_can_create_customer_and_store_decimal128(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    response = create_customer(
        client,
        sales_manager,
        email=" AP@ACME.EXAMPLE ",
        phone="+1 (555) 123-1111",
        tax_id=" tax-123 ",
        credit_limit="1250.50",
        billing_address={
            "line1": "10 Main Street",
            "city": "Austin",
            "postal_code": "78701",
            "country": "US",
        },
    )

    assert response.status_code == 201
    result = response.json()["data"]["customer"]
    stored = customer_api["customers"].find_one({"_id": ObjectId(result["id"])})
    assert result["code"] == "CUS-001"
    assert result["email"] == "ap@acme.example"
    assert result["phone"] == "+15551231111"
    assert result["tax_id"] == "TAX-123"
    assert result["credit_limit"] == "1250.50"
    assert isinstance(stored["credit_limit"], Decimal128)
    assert stored["created_at"].tzinfo == timezone.utc
    assert "name_search" not in result


def test_customer_code_and_tax_id_are_case_insensitively_unique(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    first = create_customer(
        client,
        sales_manager,
        tax_id="TAX-123",
    )
    duplicate_code = create_customer(
        client,
        sales_manager,
        code="cus-001",
        tax_id="TAX-OTHER",
    )
    duplicate_tax_id = create_customer(
        client,
        sales_manager,
        code="CUS-002",
        tax_id="tax-123",
    )

    assert first.status_code == 201
    assert duplicate_code.status_code == 409
    assert duplicate_tax_id.status_code == 409
    assert customer_api["customers"].count_documents({}) == 1


@pytest.mark.parametrize(
    "fields",
    [
        {"email": "not-an-email"},
        {"phone": "+123"},
        {"status": "pending"},
        {"name": " "},
        {"code": " "},
        {"credit_limit": -1},
        {"credit_limit": 12.5},
        {"$where": "true"},
        {"unknown": "value"},
        {
            "billing_address": {
                "line1": "1 Main St",
                "city": "Austin",
                "country": "US",
                "$ne": "bad",
            }
        },
    ],
)
def test_customer_create_rejects_invalid_or_unsafe_input(
    client,
    customer_api,
    fields,
):
    sales_manager = insert_user(customer_api, "sales_manager")

    response = create_customer(client, sales_manager, **fields)

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert customer_api["customers"].count_documents({}) == 0


@pytest.mark.parametrize(
    ("role", "can_read", "can_write"),
    [
        ("super_admin", True, True),
        ("sales_manager", True, True),
        ("inventory_manager", False, False),
        ("employee", False, False),
    ],
)
def test_customer_permissions_follow_role_matrix(
    client,
    customer_api,
    role,
    can_read,
    can_write,
):
    user = insert_user(customer_api, role)

    listing = client.get("/api/customers/", **auth_headers(user))
    creation = create_customer(client, user)

    assert listing.status_code == (200 if can_read else 403)
    assert creation.status_code == (201 if can_write else 403)


def test_customer_list_search_status_filter_and_pagination(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    create_customer(client, sales_manager, code="CUS-A", name="Northwind Parts")
    create_customer(
        client,
        sales_manager,
        code="CUS-B",
        name="Northwind Tools",
        status="inactive",
    )
    create_customer(client, sales_manager, code="CUS-C", name="Southwind Parts")

    response = client.get(
        "/api/customers/?search=Northwind&status=active&page=1&page_size=1"
        "&sort_by=name&sort_order=asc",
        **auth_headers(sales_manager),
    )

    assert response.status_code == 200
    assert len(response.json()["data"]["customers"]) == 1
    assert response.json()["data"]["customers"][0]["code"] == "CUS-A"
    assert response.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 1,
        "total_pages": 1,
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
def test_customer_list_rejects_invalid_query_parameters(client, customer_api, query):
    sales_manager = insert_user(customer_api, "sales_manager")

    response = client.get(
        f"/api/customers/?{query}",
        **auth_headers(sales_manager),
    )

    assert response.status_code == 400
    assert response.json()["success"] is False


def test_customer_detail_patch_and_object_id_validation(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    created = create_customer(client, sales_manager, credit_limit="500.00")
    customer_id = created.json()["data"]["customer"]["id"]

    detail = client.get(
        f"/api/customers/{customer_id}/",
        **auth_headers(sales_manager),
    )
    updated = client.patch(
        f"/api/customers/{customer_id}/",
        {"name": "Updated Acme", "credit_limit": "750.00"},
        format="json",
        **auth_headers(sales_manager),
    )
    invalid_id = client.get(
        "/api/customers/not-an-object-id/",
        **auth_headers(sales_manager),
    )

    assert detail.status_code == 200
    assert updated.status_code == 200
    assert updated.json()["data"]["customer"]["name"] == "Updated Acme"
    assert updated.json()["data"]["customer"]["credit_limit"] == "750.00"
    assert invalid_id.status_code == 400


def test_customer_patch_rejects_empty_and_server_owned_fields(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    customer_id = create_customer(client, sales_manager).json()["data"]["customer"]["id"]

    empty = client.patch(
        f"/api/customers/{customer_id}/",
        {},
        format="json",
        **auth_headers(sales_manager),
    )
    forbidden = client.patch(
        f"/api/customers/{customer_id}/",
        {"created_at": "2020-01-01"},
        format="json",
        **auth_headers(sales_manager),
    )

    assert empty.status_code == 400
    assert forbidden.status_code == 400


def test_customer_sales_order_history_is_paginated_and_filtered(client, customer_api):
    sales_manager = insert_user(customer_api, "sales_manager")
    customer = insert_customer(customer_api)
    other_customer = insert_customer(customer_api, code="CUS-002")
    insert_sales_order(
        customer_api,
        customer,
        status="draft",
        created_at=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    insert_sales_order(
        customer_api,
        customer,
        status="confirmed",
        created_at=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    insert_sales_order(
        customer_api,
        customer,
        status="fulfilled",
        created_at=datetime(2026, 1, 3, tzinfo=timezone.utc),
    )
    insert_sales_order(customer_api, other_customer, status="confirmed")

    response = client.get(
        f"/api/customers/{customer['_id']}/sales-orders/?status=confirmed"
        "&page=1&page_size=1",
        **auth_headers(sales_manager),
    )

    assert response.status_code == 200
    orders = response.json()["data"]["sales_orders"]
    assert len(orders) == 1
    assert orders[0]["status"] == "confirmed"
    assert orders[0]["grand_total"] == "12.00"
    assert response.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 1,
        "total_pages": 1,
    }


def test_customer_sales_order_history_requires_sales_read(client, customer_api):
    inventory_manager = insert_user(customer_api, "inventory_manager")
    customer = insert_customer(customer_api)

    response = client.get(
        f"/api/customers/{customer['_id']}/sales-orders/",
        **auth_headers(inventory_manager),
    )

    assert response.status_code == 403
