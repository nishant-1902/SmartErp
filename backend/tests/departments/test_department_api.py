"""API and business-rule tests for department endpoints."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def department_api(monkeypatch):
    """Route authentication and department requests to one isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "department-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "department-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "department-test-client")
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
    monkeypatch.setattr("departments.views.MongoClient", factory)
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
        "full_name": "Department Test User",
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
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


def create_department(client, user, *, code="OPS", name="Operations", **fields):
    body = {"code": code, "name": name, **fields}
    return client.post(
        "/api/departments/",
        body,
        format="json",
        **auth_headers(user),
    )


def insert_employee(database, department_id, **overrides):
    employee = {
        "_id": ObjectId(),
        "employee_code": f"EMP-{uuid4().hex[:8].upper()}",
        "first_name": "Alex",
        "last_name": "Worker",
        "name_search": "alex worker",
        "email": f"{uuid4().hex}@example.test",
        "phone": None,
        "department_id": department_id,
        "designation": "Analyst",
        "joining_date": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "status": "active",
        "created_at": utc_now(),
        "updated_at": utc_now(),
        "salary": 123456,
        "password_hash": "must-not-be-returned",
    }
    employee.update(overrides)
    database["employees"].insert_one(employee)
    return employee


def test_hr_can_create_and_read_department(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")

    created = create_department(
        client,
        hr_user,
        code=" ops ",
        name="Operations",
        description="Operations team",
    )

    assert created.status_code == 201
    department = created.json()["data"]["department"]
    assert department["code"] == "OPS"
    assert department["name"] == "Operations"
    assert department["description"] == "Operations team"
    assert department["is_active"] is True
    assert "name_search" not in department
    assert department["id"]
    assert department["created_at"].endswith("+00:00")

    detail = client.get(
        f"/api/departments/{department['id']}/",
        **auth_headers(hr_user),
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["department"]["id"] == department["id"]


@pytest.mark.parametrize(
    ("code", "name"),
    [
        ("FIN", "Operations"),
        ("ops", "Finance"),
    ],
)
def test_duplicate_code_or_name_returns_conflict(
    client,
    department_api,
    code,
    name,
):
    hr_user = insert_user(department_api, "hr_manager")
    assert create_department(client, hr_user).status_code == 201

    response = create_department(client, hr_user, code=code, name=name)

    assert response.status_code == 409
    assert response.json()["success"] is False
    assert response.json()["error"]["code"] == "conflict"


def test_department_write_is_limited_to_hr_and_super_admin(client, department_api):
    inventory_manager = insert_user(department_api, "inventory_manager")
    hr_user = insert_user(department_api, "hr_manager")

    denied = create_department(client, inventory_manager)
    allowed = create_department(client, hr_user, code="HR", name="Human Resources")

    assert denied.status_code == 403
    assert allowed.status_code == 201
    assert (
        client.get("/api/departments/", **auth_headers(inventory_manager)).status_code
        == 200
    )


def test_employee_role_cannot_read_departments(client, department_api):
    employee = insert_user(department_api, "employee")

    response = client.get("/api/departments/", **auth_headers(employee))

    assert response.status_code == 403


def test_manager_must_be_an_existing_active_employee(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")
    inactive_manager = insert_employee(
        department_api,
        ObjectId(),
        status="inactive",
    )

    missing = create_department(
        client,
        hr_user,
        code="MISSING",
        name="Missing Manager",
        manager_employee_id=str(ObjectId()),
    )
    inactive = create_department(
        client,
        hr_user,
        code="INACTIVE",
        name="Inactive Manager",
        manager_employee_id=str(inactive_manager["_id"]),
    )
    invalid_id = create_department(
        client,
        hr_user,
        code="INVALID",
        name="Invalid Manager",
        manager_employee_id="not-an-object-id",
    )

    assert missing.status_code == 400
    assert inactive.status_code == 400
    assert invalid_id.status_code == 400


def test_active_employee_manager_is_accepted(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")
    manager = insert_employee(department_api, ObjectId())

    response = create_department(
        client,
        hr_user,
        manager_employee_id=str(manager["_id"]),
    )

    assert response.status_code == 201
    assert response.json()["data"]["department"]["manager_employee_id"] == str(
        manager["_id"]
    )


def test_patch_manager_requires_active_employee_and_can_clear_reference(
    client,
    department_api,
):
    hr_user = insert_user(department_api, "hr_manager")
    department = create_department(client, hr_user).json()["data"]["department"]
    inactive_manager = insert_employee(
        department_api,
        ObjectId(),
        status="inactive",
    )
    active_manager = insert_employee(department_api, ObjectId())

    rejected = client.patch(
        f"/api/departments/{department['id']}/",
        {"manager_employee_id": str(inactive_manager["_id"])},
        format="json",
        **auth_headers(hr_user),
    )
    assigned = client.patch(
        f"/api/departments/{department['id']}/",
        {"manager_employee_id": str(active_manager["_id"])},
        format="json",
        **auth_headers(hr_user),
    )
    cleared = client.patch(
        f"/api/departments/{department['id']}/",
        {"manager_employee_id": None},
        format="json",
        **auth_headers(hr_user),
    )

    assert rejected.status_code == 400
    assert assigned.status_code == 200
    assert assigned.json()["data"]["department"]["manager_employee_id"] == str(
        active_manager["_id"]
    )
    assert cleared.status_code == 200
    assert cleared.json()["data"]["department"]["manager_employee_id"] is None


def test_patch_is_partial_and_name_is_unique(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")
    first = create_department(client, hr_user).json()["data"]["department"]
    second = create_department(
        client,
        hr_user,
        code="FIN",
        name="Finance",
    ).json()["data"]["department"]

    updated = client.patch(
        f"/api/departments/{first['id']}/",
        {"description": "Updated"},
        format="json",
        **auth_headers(hr_user),
    )
    duplicate = client.patch(
        f"/api/departments/{second['id']}/",
        {"name": "operations"},
        format="json",
        **auth_headers(hr_user),
    )

    assert updated.status_code == 200
    assert updated.json()["data"]["department"]["description"] == "Updated"
    assert updated.json()["data"]["department"]["name"] == "Operations"
    assert duplicate.status_code == 409


def test_input_validation_rejects_unknown_unsafe_and_empty_patch(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")

    unknown = create_department(
        client,
        hr_user,
        password_hash="unexpected",
    )
    unsafe = client.post(
        "/api/departments/",
        {"code": "BAD", "name": "Bad", "$where": "true"},
        format="json",
        **auth_headers(hr_user),
    )
    assert create_department(client, hr_user, code="BLANK", name="  ").status_code == 400

    assert unknown.status_code == 400
    assert unsafe.status_code == 400

    department = create_department(
        client,
        hr_user,
        code="PATCH",
        name="Patch",
    ).json()["data"]["department"]
    empty_patch = client.patch(
        f"/api/departments/{department['id']}/",
        {},
        format="json",
        **auth_headers(hr_user),
    )
    immutable_field = client.patch(
        f"/api/departments/{department['id']}/",
        {"created_at": "2026-01-01T00:00:00Z"},
        format="json",
        **auth_headers(hr_user),
    )
    assert empty_patch.status_code == 400
    assert immutable_field.status_code == 400


def test_list_supports_search_sort_and_bounded_pagination(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")
    first = create_department(client, hr_user, code="OPS", name="Operations")
    second = create_department(client, hr_user, code="FIN", name="Finance")
    third = create_department(client, hr_user, code="OPS2", name="Operations East")

    response = client.get(
        "/api/departments/?search=OPERATIONS&page=1&page_size=1&sort_by=name&sort_order=asc",
        **auth_headers(hr_user),
    )
    invalid_sort = client.get(
        "/api/departments/?sort_by=name_search",
        **auth_headers(hr_user),
    )
    too_many = client.get(
        "/api/departments/?page_size=101",
        **auth_headers(hr_user),
    )
    assert response.status_code == 200
    assert response.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 2,
        "total_pages": 2,
    }
    assert response.json()["data"]["departments"][0]["name"] == "Operations"
    assert invalid_sort.status_code == 400
    assert too_many.status_code == 400


def test_deactivation_is_blocked_until_no_active_employees_remain(
    client,
    department_api,
):
    hr_user = insert_user(department_api, "hr_manager")
    department = create_department(client, hr_user).json()["data"]["department"]
    active_employee = insert_employee(department_api, ObjectId(department["id"]))

    blocked = client.patch(
        f"/api/departments/{department['id']}/",
        {"is_active": False},
        format="json",
        **auth_headers(hr_user),
    )
    department_api["employees"].update_one(
        {"_id": active_employee["_id"]},
        {"$set": {"status": "inactive"}},
    )
    deactivated = client.patch(
        f"/api/departments/{department['id']}/",
        {"is_active": False},
        format="json",
        **auth_headers(hr_user),
    )

    assert blocked.status_code == 409
    assert deactivated.status_code == 200
    assert deactivated.json()["data"]["department"]["is_active"] is False
    assert department_api["departments"].count_documents({}) == 1


def test_department_employees_endpoint_searches_pages_and_hides_internal_fields(
    client,
    department_api,
):
    hr_user = insert_user(department_api, "hr_manager")
    department = create_department(client, hr_user).json()["data"]["department"]
    department_id = ObjectId(department["id"])
    insert_employee(
        department_api,
        department_id,
        first_name="Alice",
        last_name="Jones",
        name_search="alice jones",
        employee_code="EMP-ALICE",
    )
    insert_employee(
        department_api,
        department_id,
        first_name="Bob",
        last_name="Smith",
        name_search="bob smith",
        employee_code="EMP-BOB",
    )
    insert_employee(department_api, ObjectId(), first_name="Elsewhere")

    response = client.get(
        f"/api/departments/{department['id']}/employees/"
        "?search=ALICE&page=1&page_size=1&sort_by=first_name",
        **auth_headers(hr_user),
    )
    employee = response.json()["data"]["employees"][0]

    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 1
    assert employee["first_name"] == "Alice"
    assert employee["department_id"] == department["id"]
    assert "salary" not in employee
    assert "password_hash" not in employee
    assert "name_search" not in employee


def test_invalid_and_missing_department_ids_return_client_errors(client, department_api):
    hr_user = insert_user(department_api, "hr_manager")

    invalid = client.get("/api/departments/not-an-id/", **auth_headers(hr_user))
    missing = client.get(
        f"/api/departments/{ObjectId()}/",
        **auth_headers(hr_user),
    )
    unknown_department_employees = client.get(
        f"/api/departments/{ObjectId()}/employees/",
        **auth_headers(hr_user),
    )

    assert invalid.status_code == 400
    assert missing.status_code == 404
    assert unknown_department_employees.status_code == 404


def test_missing_authentication_is_rejected(client):
    response = client.get("/api/departments/")

    assert response.status_code == 401
