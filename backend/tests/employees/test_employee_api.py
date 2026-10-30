"""API tests for employee management and self-service endpoints."""

from datetime import date, datetime, time, timezone
from uuid import uuid4

import pytest
from bson import ObjectId
from django.conf import settings
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from tests.accounts.fakes import FakeDatabase


@pytest.fixture
def employee_api(monkeypatch):
    """Route authentication and employee requests to an isolated fake database."""
    database = FakeDatabase()
    monkeypatch.setattr(
        settings,
        "JWT_SECRET_KEY",
        "employee-test-secret-key-at-least-32-bytes",
    )
    monkeypatch.setattr(settings, "JWT_ISSUER", "employee-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "employee-test-client")
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
    monkeypatch.setattr("employees.views.MongoClient", factory)
    return database


@pytest.fixture
def client():
    """Return a fresh API test client."""
    return APIClient()


def insert_user(database, role, *, employee_id=None):
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "test-hash",
        "full_name": "Employee Test User",
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": employee_id,
        "last_login_at": None,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    database["users"].insert_one(user)
    return user


def auth_headers(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


def insert_department(database, *, is_active=True):
    department = {
        "_id": ObjectId(),
        "code": f"DEPT-{uuid4().hex[:8].upper()}",
        "name": "Engineering",
        "name_search": "engineering",
        "description": None,
        "manager_employee_id": None,
        "is_active": is_active,
        "created_at": utc_now(),
        "updated_at": utc_now(),
    }
    database["departments"].insert_one(department)
    return department


def employee_body(department, **overrides):
    body = {
        "employee_code": "emp-001",
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": " ADA.LOVELACE@Example.Test ",
        "phone": "+1 (415) 555-0123",
        "department_id": str(department["_id"]),
        "designation": "Engineer",
        "joining_date": "2024-01-15",
        "status": "active",
    }
    body.update(overrides)
    return body


def create_employee(client, user, department, **overrides):
    return client.post(
        "/api/employees/",
        employee_body(department, **overrides),
        format="json",
        **auth_headers(user),
    )


def test_hr_can_create_employee_with_normalized_fields_and_audit(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)

    response = create_employee(client, hr_user, department)

    assert response.status_code == 201
    employee = response.json()["data"]["employee"]
    stored = employee_api["employees"].find_one({"_id": ObjectId(employee["id"])})
    assert employee["employee_code"] == "EMP-001"
    assert employee["email"] == "ada.lovelace@example.test"
    assert employee["phone"] == "+14155550123"
    assert employee["department_id"] == str(department["_id"])
    assert employee["joining_date"] == "2024-01-15T00:00:00+00:00"
    assert stored["joining_date"] == datetime.combine(
        date(2024, 1, 15),
        time.min,
        tzinfo=timezone.utc,
    )
    assert employee_api["audit_logs"].count_documents(
        {
            "action": "employee_created",
            "entity_id": employee["id"],
            "outcome": "success",
        }
    ) == 1


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("email", "not-an-email"),
        ("phone", "555-ABCD"),
        ("phone", "+123"),
        ("joining_date", "2099-01-01"),
        ("status", "terminated"),
        ("first_name", "  "),
        ("employee_code", " "),
    ],
)
def test_create_rejects_invalid_fields(client, employee_api, field, value):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)

    response = create_employee(
        client,
        hr_user,
        department,
        **{field: value},
    )

    assert response.status_code == 400
    assert response.json()["success"] is False
    assert employee_api["employees"].count_documents({}) == 0


def test_create_rejects_missing_inactive_or_invalid_department(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    inactive_department = insert_department(employee_api, is_active=False)

    missing = create_employee(
        client,
        hr_user,
        {"_id": ObjectId()},
    )
    inactive = create_employee(client, hr_user, inactive_department)
    invalid_id = client.post(
        "/api/employees/",
        employee_body(inactive_department, department_id="not-an-object-id"),
        format="json",
        **auth_headers(hr_user),
    )

    assert missing.status_code == 400
    assert inactive.status_code == 400
    assert invalid_id.status_code == 400


@pytest.mark.parametrize(
    ("overrides", "expected_field"),
    [
        ({"employee_code": "EMP-001"}, "employee_code"),
        ({"employee_code": "EMP-002", "email": "ada.lovelace@example.test"}, "email"),
    ],
)
def test_duplicate_employee_code_and_case_insensitive_email_return_conflict(
    client,
    employee_api,
    overrides,
    expected_field,
):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    assert create_employee(client, hr_user, department).status_code == 201

    response = create_employee(client, hr_user, department, **overrides)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "conflict"
    assert expected_field in response.json()["error"]["details"]


@pytest.mark.parametrize(
    ("role", "can_read_directory", "can_write"),
    [
        ("super_admin", True, True),
        ("hr_manager", True, True),
        ("inventory_manager", True, False),
        ("purchase_manager", True, False),
        ("sales_manager", True, False),
        ("employee", False, False),
    ],
)
def test_employee_permissions_follow_role_matrix(
    client,
    employee_api,
    role,
    can_read_directory,
    can_write,
):
    user = insert_user(employee_api, role)
    department = insert_department(employee_api)

    listing = client.get("/api/employees/", **auth_headers(user))
    creation = create_employee(client, user, department)

    assert listing.status_code == (200 if can_read_directory else 403)
    assert creation.status_code == (201 if can_write else 403)


def test_employee_can_read_only_their_own_profile(client, employee_api):
    department = insert_department(employee_api)
    own_employee_response = client.post(
        "/api/employees/",
        employee_body(department),
        format="json",
        **auth_headers(insert_user(employee_api, "hr_manager")),
    )
    own_id = own_employee_response.json()["data"]["employee"]["id"]
    own_object_id = ObjectId(own_id)
    employee_user = insert_user(
        employee_api,
        "employee",
        employee_id=own_object_id,
    )
    other_employee_response = client.post(
        "/api/employees/",
        employee_body(
            department,
            employee_code="EMP-002",
            email="second.employee@example.test",
        ),
        format="json",
        **auth_headers(insert_user(employee_api, "hr_manager")),
    )
    other_id = other_employee_response.json()["data"]["employee"]["id"]

    me = client.get("/api/employees/me/", **auth_headers(employee_user))
    own_detail = client.get(
        f"/api/employees/{own_id}/",
        **auth_headers(employee_user),
    )
    other_detail = client.get(
        f"/api/employees/{other_id}/",
        **auth_headers(employee_user),
    )
    directory = client.get("/api/employees/", **auth_headers(employee_user))

    assert me.status_code == 200
    assert me.json()["data"]["employee"]["id"] == own_id
    assert own_detail.status_code == 200
    assert other_detail.status_code == 403
    assert directory.status_code == 403


def test_me_route_rejects_non_employee_and_unlinked_employee(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    employee_user = insert_user(employee_api, "employee")

    hr_response = client.get("/api/employees/me/", **auth_headers(hr_user))
    missing_link = client.get("/api/employees/me/", **auth_headers(employee_user))

    assert hr_response.status_code == 403
    assert missing_link.status_code == 404


def test_patch_fields_are_allowlisted_and_each_change_is_audited(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    created = create_employee(client, hr_user, department)
    employee_id = created.json()["data"]["employee"]["id"]

    patched = client.patch(
        f"/api/employees/{employee_id}/",
        {
            "first_name": "Augusta",
            "phone": "415.555.0188",
        },
        format="json",
        **auth_headers(hr_user),
    )
    immutable_code = client.patch(
        f"/api/employees/{employee_id}/",
        {"employee_code": "CHANGED"},
        format="json",
        **auth_headers(hr_user),
    )
    empty_patch = client.patch(
        f"/api/employees/{employee_id}/",
        {},
        format="json",
        **auth_headers(hr_user),
    )

    assert patched.status_code == 200
    assert patched.json()["data"]["employee"]["first_name"] == "Augusta"
    assert patched.json()["data"]["employee"]["phone"] == "4155550188"
    assert immutable_code.status_code == 400
    assert empty_patch.status_code == 400
    assert employee_api["audit_logs"].count_documents(
        {
            "action": "employee_updated",
            "entity_id": employee_id,
            "outcome": "success",
        }
    ) == 1


def test_patch_revalidates_department_and_email_uniqueness(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    inactive_department = insert_department(employee_api, is_active=False)
    first = create_employee(client, hr_user, department).json()["data"]["employee"]
    second = create_employee(
        client,
        hr_user,
        department,
        employee_code="EMP-002",
        email="second@example.test",
    ).json()["data"]["employee"]

    inactive_department_response = client.patch(
        f"/api/employees/{first['id']}/",
        {"department_id": str(inactive_department["_id"])},
        format="json",
        **auth_headers(hr_user),
    )
    duplicate_email = client.patch(
        f"/api/employees/{second['id']}/",
        {"email": "ADA.LOVELACE@example.test"},
        format="json",
        **auth_headers(hr_user),
    )

    assert inactive_department_response.status_code == 400
    assert duplicate_email.status_code == 409


def test_reactivating_employee_requires_an_active_department(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    created = create_employee(
        client,
        hr_user,
        department,
        status="on_leave",
    ).json()["data"]["employee"]
    employee_api["departments"].update_one(
        {"_id": department["_id"]},
        {"$set": {"is_active": False}},
    )

    response = client.patch(
        f"/api/employees/{created['id']}/",
        {"status": "active"},
        format="json",
        **auth_headers(hr_user),
    )

    assert response.status_code == 400
    assert (
        employee_api["employees"].find_one({"_id": ObjectId(created["id"])})["status"]
        == "on_leave"
    )


def test_delete_deactivates_without_removing_document_and_audits(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    created = create_employee(client, hr_user, department)
    employee_id = created.json()["data"]["employee"]["id"]

    deleted = client.delete(
        f"/api/employees/{employee_id}/",
        **auth_headers(hr_user),
    )
    repeated = client.delete(
        f"/api/employees/{employee_id}/",
        **auth_headers(hr_user),
    )

    assert deleted.status_code == 200
    assert deleted.json()["data"]["employee"]["status"] == "inactive"
    assert repeated.status_code == 200
    assert employee_api["employees"].count_documents(
        {"_id": ObjectId(employee_id)}
    ) == 1
    assert employee_api["audit_logs"].count_documents(
        {
            "action": "employee_deactivated",
            "entity_id": employee_id,
            "outcome": "success",
        }
    ) == 1


def test_list_search_filters_sort_and_pagination_meta(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    other_department = insert_department(employee_api)
    create_employee(client, hr_user, department)
    create_employee(
        client,
        hr_user,
        department,
        employee_code="EMP-002",
        first_name="Grace",
        last_name="Hopper",
        email="grace@example.test",
        status="on_leave",
    )
    create_employee(
        client,
        hr_user,
        other_department,
        employee_code="EMP-003",
        first_name="Alan",
        last_name="Turing",
        email="alan@example.test",
    )

    response = client.get(
        "/api/employees/?search=example&department_id="
        f"{department['_id']}&status=active&page=1&page_size=1"
        "&sort_by=first_name&sort_order=asc",
        **auth_headers(hr_user),
    )
    invalid_department = client.get(
        "/api/employees/?department_id=invalid",
        **auth_headers(hr_user),
    )
    invalid_sort = client.get(
        "/api/employees/?sort_by=name_search",
        **auth_headers(hr_user),
    )

    assert response.status_code == 200
    assert response.json()["meta"] == {
        "page": 1,
        "page_size": 1,
        "total": 1,
        "total_pages": 1,
    }
    assert response.json()["data"]["employees"][0]["employee_code"] == "EMP-001"
    assert invalid_department.status_code == 400
    assert invalid_sort.status_code == 400


def test_designations_are_distinct_and_sorted(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")
    department = insert_department(employee_api)
    create_employee(client, hr_user, department, designation="Engineer")
    create_employee(
        client,
        hr_user,
        department,
        employee_code="EMP-002",
        email="second@example.test",
        designation="engineer",
    )
    create_employee(
        client,
        hr_user,
        department,
        employee_code="EMP-003",
        email="third@example.test",
        designation="Analyst",
    )

    response = client.get(
        "/api/employees/designations/",
        **auth_headers(hr_user),
    )

    assert response.status_code == 200
    assert response.json()["data"]["designations"] == ["Analyst", "Engineer", "engineer"]


def test_invalid_and_missing_employee_ids(client, employee_api):
    hr_user = insert_user(employee_api, "hr_manager")

    invalid = client.get("/api/employees/not-an-id/", **auth_headers(hr_user))
    missing = client.get(
        f"/api/employees/{ObjectId()}/",
        **auth_headers(hr_user),
    )

    assert invalid.status_code == 400
    assert missing.status_code == 404
