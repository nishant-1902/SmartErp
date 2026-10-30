"""Employee business rules, audit logging, and response serialization."""

from contextlib import contextmanager
from typing import Any, Generator

from bson import ObjectId
from pymongo.database import Database

from accounts.repository import find_user_by_id, write_audit_log
from common.exceptions import ConflictError, NotFoundError, ValidationFailed
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from common.time import utc_now
from departments.repository import find_department_by_id
from employees.repository import (
    count_employees,
    create_employee as insert_employee,
    deactivate_employee as deactivate_employee_record,
    find_employee_by_code,
    find_employee_by_email,
    find_employee_by_id,
    list_designations as list_designation_records,
    list_employees as list_employee_records,
    public_employee,
    update_employee as update_employee_record,
)


@contextmanager
def _employee_transaction(database: Database[Any]) -> Generator[Any, None, None]:
    """Keep employee mutations and their audit records in one Mongo transaction."""
    client = getattr(database, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        yield None
        return
    with client.start_session() as session:
        with session.start_transaction():
            yield session


def _public_employee(document: dict[str, Any]) -> dict[str, Any]:
    """Convert an allowlisted employee record into JSON-safe fields."""
    employee = public_employee(document)
    employee["id"] = employee.pop("_id")
    return serialize_document(employee)


def _validate_department(
    database: Database[Any],
    department_id: ObjectId | str,
    session: Any = None,
) -> None:
    """Require a department reference to point at an active department."""
    department = find_department_by_id(database, department_id, session=session)
    if department is None or department.get("is_active") is not True:
        raise ValidationFailed(
            "Employee department must exist and be active.",
            details={"department_id": "Department is missing or inactive."},
        )


def _check_unique_values(
    database: Database[Any],
    values: dict[str, Any],
    *,
    exclude_id: ObjectId | None = None,
) -> None:
    """Reject duplicate employee codes and normalized email addresses."""
    for field, finder in (
        ("employee_code", find_employee_by_code),
        ("email", find_employee_by_email),
    ):
        if field not in values:
            continue
        existing = finder(database, values[field])
        if existing is not None and existing.get("_id") != exclude_id:
            raise ConflictError(
                f"Employee {field} already exists.",
                details={field: "Must be unique."},
            )


def _audit_employee_change(
    database: Database[Any],
    *,
    employee_id: ObjectId,
    actor_id: ObjectId | str,
    action: str,
    session: Any,
) -> None:
    """Write a standard audit record for a successful employee mutation."""
    write_audit_log(
        database,
        actor_id=actor_id,
        action=action,
        resource="employee",
        resource_id=employee_id,
        outcome="success",
        now=utc_now(),
        session=session,
    )


def create_employee(
    database: Database[Any],
    *,
    values: dict[str, Any],
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Create an employee after checking uniqueness and its active department."""
    _check_unique_values(database, values)
    with _employee_transaction(database) as session:
        _validate_department(database, values["department_id"], session=session)
        employee = insert_employee(database, **values, session=session)
        _audit_employee_change(
            database,
            employee_id=employee["_id"],
            actor_id=actor_id,
            action="employee_created",
            session=session,
        )
    return _public_employee(employee)


def get_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one public employee record or a not-found error."""
    employee = find_employee_by_id(database, employee_id)
    if employee is None:
        raise NotFoundError("Employee was not found.")
    return _public_employee(employee)


def get_current_employee(
    database: Database[Any],
    user_id: ObjectId | str,
) -> dict[str, Any]:
    """Resolve the authenticated user's linked employee profile."""
    user = find_user_by_id(database, user_id)
    if user is None or user.get("employee_id") is None:
        raise NotFoundError("No employee profile is linked to this account.")
    employee_id = parse_object_id(user["employee_id"])
    employee = find_employee_by_id(database, employee_id)
    if employee is None:
        raise NotFoundError("No employee profile is linked to this account.")
    return _public_employee(employee)


def list_employees(
    database: Database[Any],
    *,
    search: str | None,
    department_id: ObjectId | None,
    status: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return employees matching validated filters with pagination metadata."""
    employees = list_employee_records(
        database,
        search=search,
        department_id=department_id,
        status=status,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_employees(
        database,
        search=search,
        department_id=department_id,
        status=status,
    )
    return (
        [_public_employee(employee) for employee in employees],
        pagination.build_meta(total),
    )


def update_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
    *,
    values: dict[str, Any],
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Update an employee's allowlisted fields and audit the change."""
    parsed_id = parse_object_id(employee_id)
    current = find_employee_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Employee was not found.")

    _check_unique_values(database, values, exclude_id=parsed_id)
    effective_department_id = values.get("department_id")
    if effective_department_id is None and values.get("status") == "active":
        effective_department_id = current["department_id"]
    with _employee_transaction(database) as session:
        if effective_department_id is not None:
            _validate_department(
                database,
                effective_department_id,
                session=session,
            )
        updated = update_employee_record(
            database,
            parsed_id,
            values,
            session=session,
        )
        if updated is None:
            raise NotFoundError("Employee was not found.")
        _audit_employee_change(
            database,
            employee_id=parsed_id,
            actor_id=actor_id,
            action="employee_updated",
            session=session,
        )
    return _public_employee(updated)


def deactivate_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
    *,
    actor_id: ObjectId | str,
) -> dict[str, Any]:
    """Set the employee inactive, preserve its document, and audit the change."""
    parsed_id = parse_object_id(employee_id)
    current = find_employee_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Employee was not found.")
    if current.get("status") == "inactive":
        return _public_employee(current)

    with _employee_transaction(database) as session:
        updated = deactivate_employee_record(
            database,
            parsed_id,
            session=session,
        )
        if updated is None:
            raise NotFoundError("Employee was not found.")
        _audit_employee_change(
            database,
            employee_id=parsed_id,
            actor_id=actor_id,
            action="employee_deactivated",
            session=session,
        )
    return _public_employee(updated)


def list_designations(database: Database[Any]) -> list[str]:
    """Return the sorted set of distinct employee designations."""
    return list_designation_records(database)
