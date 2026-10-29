import pytest
from bson import ObjectId

from accounts.repository import (
    create_user,
    deactivate_user,
    find_user_by_email,
    find_user_by_id,
    update_user,
)
from common.exceptions import ValidationFailed
from tests.accounts.fakes import FakeDatabase


def test_create_and_find_user_normalizes_email_and_employee_id():
    database = FakeDatabase()
    employee_id = ObjectId()
    user = create_user(
        database,
        email="  User@Example.COM ",
        password_hash="encoded",
        full_name="  Example User  ",
        role="employee",
        employee_id=str(employee_id),
    )

    assert user["email"] == "user@example.com"
    assert user["full_name"] == "Example User"
    assert user["employee_id"] == employee_id
    assert user["token_version"] == 0
    assert user["last_login_at"] is None
    assert find_user_by_email(database, " USER@example.com ")["_id"] == user["_id"]
    assert find_user_by_id(database, str(user["_id"]))["_id"] == user["_id"]


def test_update_password_and_deactivation_increment_token_version():
    database = FakeDatabase()
    user = create_user(
        database,
        email="user@example.com",
        password_hash="before",
        full_name="Example User",
        role="employee",
    )

    updated = update_user(database, user["_id"], {"password_hash": "after"})
    assert updated["token_version"] == 1

    deactivated = deactivate_user(database, user["_id"])
    assert deactivated["is_active"] is False
    assert deactivated["token_version"] == 2


def test_update_rejects_unknown_or_operator_fields():
    database = FakeDatabase()
    user = create_user(
        database,
        email="user@example.com",
        password_hash="encoded",
        full_name="Example User",
        role="employee",
    )

    with pytest.raises(ValueError):
        update_user(database, user["_id"], {"$set": {"role": "super_admin"}})
    with pytest.raises(ValueError):
        update_user(database, user["_id"], {"role.name": "super_admin"})


def test_invalid_user_id_is_rejected():
    with pytest.raises(ValidationFailed):
        find_user_by_id(FakeDatabase(), "not-an-object-id")
