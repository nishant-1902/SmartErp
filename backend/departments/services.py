"""Department business rules and response serialization."""

from contextlib import contextmanager
from typing import Any, Generator

from bson import ObjectId
from pymongo.database import Database

from common.exceptions import ConflictError, NotFoundError, ValidationFailed
from common.object_id import parse_object_id
from common.pagination import Pagination
from common.serialization import serialize_document
from departments.repository import (
    count_departments,
    count_active_department_employees,
    count_department_employees,
    create_department as insert_department,
    find_active_employee,
    find_department_by_code,
    find_department_by_id,
    find_department_by_name,
    list_departments as list_department_records,
    list_department_employees as list_employee_records,
    serialize_department_fields,
    update_department as update_department_record,
)


@contextmanager
def _department_transaction(database: Database[Any]) -> Generator[Any, None, None]:
    """Use a Mongo transaction for deactivation's cross-collection check and update."""
    client = getattr(database, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        yield None
        return
    with client.start_session() as session:
        with session.start_transaction():
            yield session


def _public_department(document: dict[str, Any]) -> dict[str, Any]:
    """Serialize a department without its internal normalized search field."""
    return serialize_document(serialize_department_fields(document))


def _public_employee(document: dict[str, Any]) -> dict[str, Any]:
    """Convert a repository employee record into JSON-safe public fields."""
    return serialize_document(
        {
            "id": document["_id"],
            **{
                field: value
                for field, value in document.items()
                if field != "_id"
            },
        }
    )


def _validate_manager(
    database: Database[Any],
    manager_employee_id: ObjectId | None,
    session: Any = None,
) -> None:
    """Reject a manager reference unless it identifies an active employee."""
    if manager_employee_id is not None and find_active_employee(
        database,
        manager_employee_id,
        session=session,
    ) is None:
        raise ValidationFailed(
            "Department manager must be an existing active employee.",
            details={"manager_employee_id": "Employee is missing or inactive."},
        )


def _check_unique_values(
    database: Database[Any],
    values: dict[str, Any],
    *,
    exclude_id: ObjectId | None = None,
) -> None:
    """Raise a conflict when a normalized code or name is already assigned."""
    checks = (
        ("code", find_department_by_code),
        ("name", find_department_by_name),
    )
    for field, finder in checks:
        if field not in values:
            continue
        existing = finder(database, values[field])
        if existing is not None and existing.get("_id") != exclude_id:
            raise ConflictError(
                f"Department {field} already exists.",
                details={field: "Must be unique."},
            )


def create_department(
    database: Database[Any],
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Validate references and uniqueness before creating a department."""
    _check_unique_values(database, values)
    _validate_manager(database, values.get("manager_employee_id"))
    department = insert_department(database, **values)
    return _public_department(department)


def get_department(
    database: Database[Any],
    department_id: ObjectId | str,
) -> dict[str, Any]:
    """Return one department or a safe not-found error."""
    department = find_department_by_id(database, department_id)
    if department is None:
        raise NotFoundError("Department was not found.")
    return _public_department(department)


def list_departments(
    database: Database[Any],
    *,
    search: str | None,
    is_active: bool | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List matching departments with validated sorting and pagination."""
    departments = list_department_records(
        database,
        search=search,
        is_active=is_active,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_departments(database, search=search, is_active=is_active)
    return [_public_department(department) for department in departments], (
        pagination.build_meta(total)
    )


def update_department(
    database: Database[Any],
    department_id: ObjectId | str,
    *,
    values: dict[str, Any],
) -> dict[str, Any]:
    """Update department fields while enforcing manager and deactivation rules."""
    parsed_id = parse_object_id(department_id)
    current = find_department_by_id(database, parsed_id)
    if current is None:
        raise NotFoundError("Department was not found.")

    _check_unique_values(database, values, exclude_id=parsed_id)
    if "manager_employee_id" in values:
        _validate_manager(database, values["manager_employee_id"])

    deactivate = values.get("is_active") is False and current.get("is_active") is True
    if deactivate:
        with _department_transaction(database) as session:
            active_employees = count_active_department_employees(
                database,
                parsed_id,
                session=session,
            )
            if active_employees:
                raise ConflictError(
                    "Department cannot be deactivated while active employees are assigned.",
                    details={"active_employee_count": active_employees},
                )
            updated = update_department_record(
                database,
                parsed_id,
                values,
                session=session,
                expected_is_active=True,
            )
    else:
        updated = update_department_record(database, parsed_id, values)

    if updated is None:
        raise NotFoundError("Department was not found.")
    if updated.get("is_active") is not values.get("is_active", updated.get("is_active")):
        raise ConflictError("Department state changed; retry the request.")
    return _public_department(updated)


def list_department_employees(
    database: Database[Any],
    department_id: ObjectId | str,
    *,
    search: str | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """List employees assigned to an existing department."""
    parsed_id = parse_object_id(department_id)
    if find_department_by_id(database, parsed_id) is None:
        raise NotFoundError("Department was not found.")

    employees = list_employee_records(
        database,
        parsed_id,
        search=search,
        skip=pagination.skip,
        limit=pagination.limit,
        sort_by=pagination.sort_by,
        sort_order=pagination.sort_order,
    )
    total = count_department_employees(
        database,
        parsed_id,
        search=search,
    )
    return (
        [_public_employee(employee) for employee in employees],
        pagination.build_meta(total),
    )
