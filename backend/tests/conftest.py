"""Shared pytest fixtures for isolated MongoDB-backed API tests."""

from collections.abc import Callable, Iterator
from copy import deepcopy
from datetime import timedelta
from decimal import Decimal
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit
from uuid import uuid4

import jwt
import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from django.core.management import call_command
from django.test import override_settings
from pymongo import MongoClient
from pymongo.database import Database
from rest_framework.test import APIClient

from common.time import utc_now

TEST_DATABASE_NAME = "smarterp_test"
TEST_DATABASE_USER = "smarterp_test_user"
TEST_JWT_SECRET = "pytest-only-signing-key-not-for-production"
TEST_ROLES = {
    "super_admin",
    "hr_manager",
    "inventory_manager",
    "purchase_manager",
    "sales_manager",
    "employee",
}


def validate_test_mongo_configuration(uri: str, database_name: str) -> None:
    """Reject MongoDB test connections that could target a non-test database."""
    if database_name != TEST_DATABASE_NAME:
        raise pytest.UsageError(
            f"MONGO_TEST_DB_NAME must be exactly {TEST_DATABASE_NAME!r}."
        )
    if not uri:
        raise pytest.UsageError(
            "MONGO_TEST_URI is required for tests that use the MongoDB fixtures."
        )

    try:
        parsed_uri = urlsplit(uri)
        hostname = parsed_uri.hostname
        port = parsed_uri.port
    except ValueError as exc:
        raise pytest.UsageError(
            "MONGO_TEST_URI must contain a valid local MongoDB address."
        ) from exc
    if parsed_uri.scheme != "mongodb":
        raise pytest.UsageError(
            "MONGO_TEST_URI must use the mongodb:// scheme for the local replica set."
        )
    if hostname not in {"localhost", "127.0.0.1"} or port != 27017:
        raise pytest.UsageError(
            "MONGO_TEST_URI must connect to localhost:27017."
        )
    if unquote(parsed_uri.path.lstrip("/")) != TEST_DATABASE_NAME:
        raise pytest.UsageError(
            f"MONGO_TEST_URI must select database {TEST_DATABASE_NAME!r}."
        )
    if unquote(parsed_uri.username or "") != TEST_DATABASE_USER:
        raise pytest.UsageError(
            f"MONGO_TEST_URI must authenticate as {TEST_DATABASE_USER!r}."
        )

    query = parse_qs(parsed_uri.query)
    if query.get("authSource") != [TEST_DATABASE_NAME]:
        raise pytest.UsageError(
            f"MONGO_TEST_URI authSource must be {TEST_DATABASE_NAME!r}."
        )
    if query.get("replicaSet") != ["rs0"]:
        raise pytest.UsageError(
            "MONGO_TEST_URI must include replicaSet=rs0; transaction tests "
            "require the local replica set."
        )


@pytest.fixture(scope="session")
def mongo_test_database() -> Iterator[Database[Any]]:
    """Initialize the fixed test database and clear its data after the session."""
    uri = settings.MONGO_TEST_URI
    database_name = settings.MONGO_TEST_DB_NAME
    validate_test_mongo_configuration(uri, database_name)

    client = MongoClient(uri, serverSelectionTimeoutMS=5000)
    database = client[TEST_DATABASE_NAME]
    initialized = False
    try:
        client.admin.command("ping")
        hello = client.admin.command("hello")
        if hello.get("setName") != "rs0" or not hello.get("isWritablePrimary"):
            raise pytest.UsageError(
                "MONGO_TEST_URI must connect to the writable primary of replica set rs0."
            )
        database.command("ping")
        with override_settings(MONGO_URI=uri, MONGO_DB_NAME=TEST_DATABASE_NAME):
            call_command("init_db", verbosity=0)
        initialized = True
        yield database
    finally:
        try:
            if initialized:
                for collection_name in database.list_collection_names():
                    database[collection_name].delete_many({})
        finally:
            client.close()


@pytest.fixture
def mongo_db(mongo_test_database: Database[Any]) -> Iterator[Database[Any]]:
    """Clear every test collection before and after each database-backed test."""
    for collection_name in mongo_test_database.list_collection_names():
        mongo_test_database[collection_name].delete_many({})
    yield mongo_test_database
    for collection_name in mongo_test_database.list_collection_names():
        mongo_test_database[collection_name].delete_many({})


@pytest.fixture
def api_client() -> APIClient:
    """Return a fresh Django REST Framework API test client."""
    return APIClient()


@pytest.fixture
def create_user(
    mongo_db: Database[Any],
) -> Callable[..., dict[str, Any]]:
    """Return a factory that inserts a valid user for a role."""
    def create(role: str = "employee", **overrides: Any) -> dict[str, Any]:
        if role not in TEST_ROLES:
            raise ValueError(f"Unknown test role: {role}")

        now = utc_now()
        document: dict[str, Any] = {
            "email": f"{uuid4().hex}@example.test",
            "password_hash": "test-only-password-hash",
            "full_name": "Pytest User",
            "role": role,
            "is_active": True,
            "token_version": 0,
            "employee_id": None,
            "created_at": now,
            "updated_at": now,
            "last_login_at": None,
        }
        document.update(deepcopy(overrides))
        document["email"] = document["email"].strip().lower()
        mongo_db.users.insert_one(document)
        return document

    return create


@pytest.fixture
def auth_headers(
    create_user: Callable[..., dict[str, Any]],
    monkeypatch: pytest.MonkeyPatch,
) -> Callable[[str], dict[str, str]]:
    """Return a factory for test-only JWT Authorization headers by role."""
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", TEST_JWT_SECRET)
    monkeypatch.setattr(settings, "JWT_ISSUER", "smarterp-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "smarterp-test-client")

    def build(role: str) -> dict[str, str]:
        user = create_user(role)
        now = utc_now()
        payload = {
            "sub": str(user["_id"]),
            "role": role,
            "token_version": user["token_version"],
            "jti": uuid4().hex,
            "iat": now,
            "exp": now + timedelta(minutes=5),
            "iss": settings.JWT_ISSUER,
            "aud": settings.JWT_AUDIENCE,
            "type": "access",
        }
        token = jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")
        return {"HTTP_AUTHORIZATION": f"Bearer {token}"}

    return build


def _insert_seed(
    collection_name: str,
    document: dict[str, Any],
    database: Database[Any],
    overrides: dict[str, Any],
) -> dict[str, Any]:
    seeded = deepcopy(document)
    seeded.update(deepcopy(overrides))
    database[collection_name].insert_one(seeded)
    return seeded


@pytest.fixture
def seed_department(
    mongo_db: Database[Any],
) -> Callable[..., dict[str, Any]]:
    """Return a factory that inserts an active department."""
    def create(**overrides: Any) -> dict[str, Any]:
        now = utc_now()
        return _insert_seed(
            "departments",
            {
                "code": f"DEPT-{uuid4().hex[:8].upper()}",
                "name": "Operations",
                "name_search": "operations",
                "description": None,
                "manager_employee_id": None,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            mongo_db,
            overrides,
        )

    return create


@pytest.fixture
def seed_product(
    mongo_db: Database[Any],
) -> Callable[..., dict[str, Any]]:
    """Return a factory that inserts an active product with zero stock."""
    def create(**overrides: Any) -> dict[str, Any]:
        now = utc_now()
        suffix = uuid4().hex[:8].upper()
        return _insert_seed(
            "products",
            {
                "sku": f"TEST-{suffix}",
                "name": "Test Product",
                "name_search": "test product",
                "description": None,
                "category": "Testing",
                "unit": "each",
                "cost_price": Decimal128(Decimal("1.00")),
                "selling_price": Decimal128(Decimal("2.00")),
                "quantity_on_hand": 0,
                "reserved_quantity": 0,
                "min_stock_level": 0,
                "is_active": True,
                "created_at": now,
                "updated_at": now,
            },
            mongo_db,
            overrides,
        )

    return create


@pytest.fixture
def seed_supplier(
    mongo_db: Database[Any],
) -> Callable[..., dict[str, Any]]:
    """Return a factory that inserts an active supplier."""
    def create(**overrides: Any) -> dict[str, Any]:
        now = utc_now()
        return _insert_seed(
            "suppliers",
            {
                "code": f"SUP-{uuid4().hex[:8].upper()}",
                "name": "Test Supplier",
                "name_search": "test supplier",
                "email": None,
                "phone": None,
                "contact_person": None,
                "address": None,
                "payment_terms": None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            mongo_db,
            overrides,
        )

    return create


@pytest.fixture
def seed_customer(
    mongo_db: Database[Any],
) -> Callable[..., dict[str, Any]]:
    """Return a factory that inserts an active customer."""
    def create(**overrides: Any) -> dict[str, Any]:
        now = utc_now()
        return _insert_seed(
            "customers",
            {
                "code": f"CUST-{uuid4().hex[:8].upper()}",
                "name": "Test Customer",
                "name_search": "test customer",
                "email": None,
                "phone": None,
                "tax_id": None,
                "billing_address": None,
                "shipping_address": None,
                "credit_limit": None,
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            mongo_db,
            overrides,
        )

    return create
