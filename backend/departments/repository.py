"""PyMongo data access for departments and their employee lists."""

from collections.abc import Mapping
import re
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.object_id import parse_object_id
from common.mongo import count_query_matches
from common.time import utc_now

_DEPARTMENT_UPDATE_FIELDS = {
    "code",
    "name",
    "description",
    "manager_employee_id",
    "is_active",
}
_DEPARTMENT_FIELDS = (
    "code",
    "name",
    "description",
    "manager_employee_id",
    "is_active",
    "created_at",
    "updated_at",
)
DEPARTMENT_SORT_FIELDS = frozenset(
    {"code", "name", "created_at", "updated_at", "is_active"}
)
EMPLOYEE_SORT_FIELDS = frozenset(
    {
        "employee_code",
        "first_name",
        "last_name",
        "email",
        "designation",
        "joining_date",
        "status",
        "created_at",
    }
)
_EMPLOYEE_RESPONSE_FIELDS = (
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "phone",
    "department_id",
    "designation",
    "joining_date",
    "status",
    "created_at",
    "updated_at",
)


def normalize_department_code(code: str) -> str:
    """Normalize department codes so case variants share one unique value."""
    normalized = code.strip().upper()
    if not normalized:
        raise ValueError("Department code must not be empty.")
    return normalized


def normalize_department_name(name: str) -> str:
    """Normalize a department name for case-insensitive uniqueness and search."""
    normalized = name.strip()
    if not normalized:
        raise ValueError("Department name must not be empty.")
    return normalized.casefold()


def create_department(
    database: Database[Any],
    *,
    code: str,
    name: str,
    description: str | None,
    manager_employee_id: ObjectId | str | None,
    is_active: bool,
) -> dict[str, Any]:
    """Insert a department with normalized uniqueness fields and UTC timestamps."""
    now = utc_now()
    document: dict[str, Any] = {
        "code": normalize_department_code(code),
        "name": name.strip(),
        "name_search": normalize_department_name(name),
        "description": description,
        "manager_employee_id": (
            parse_object_id(manager_employee_id)
            if manager_employee_id is not None
            else None
        ),
        "is_active": is_active,
        "created_at": now,
        "updated_at": now,
    }
    result = database["departments"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_department_by_id(
    database: Database[Any],
    department_id: ObjectId | str,
    session: Any = None,
) -> dict[str, Any] | None:
    """Find a department by a validated ObjectId."""
    return database["departments"].find_one(
        {"_id": parse_object_id(department_id)},
        session=session,
    )


def find_department_by_code(database: Database[Any], code: str) -> dict[str, Any] | None:
    """Find a department by its normalized unique code."""
    return database["departments"].find_one(
        {"code": normalize_department_code(code)}
    )


def find_department_by_name(database: Database[Any], name: str) -> dict[str, Any] | None:
    """Find a department by its normalized unique name."""
    return database["departments"].find_one(
        {"name_search": normalize_department_name(name)}
    )


def _department_list_query(
    search: str | None,
    is_active: bool | None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"code": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
        ]
    if is_active is not None:
        query["is_active"] = is_active
    return query


def list_departments(
    database: Database[Any],
    *,
    search: str | None,
    is_active: bool | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one page of departments matching validated filters."""
    if sort_by is not None and sort_by not in DEPARTMENT_SORT_FIELDS:
        raise ValueError("Department sort field is not allowed.")
    field = "name_search" if sort_by == "name" else sort_by
    sort_fields = (
        [(field, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if field is not None
        else [("created_at", -1), ("_id", 1)]
    )
    return list(
        database["departments"]
        .find(_department_list_query(search, is_active))
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )


def count_departments(
    database: Database[Any],
    *,
    search: str | None,
    is_active: bool | None,
) -> int:
    """Count departments matching the same validated list filters."""
    return count_query_matches(
        database["departments"],
        _department_list_query(search, is_active),
    )


def update_department(
    database: Database[Any],
    department_id: ObjectId | str,
    updates: Mapping[str, Any],
    *,
    session: Any = None,
    expected_is_active: bool | None = None,
) -> dict[str, Any] | None:
    """Update an allowlisted set of department fields and return the new document."""
    if not updates or any(
        not isinstance(field, str)
        or field.startswith("$")
        or "." in field
        or field not in _DEPARTMENT_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Department update contains an unsupported field.")

    changes = dict(updates)
    if "code" in changes:
        changes["code"] = normalize_department_code(changes["code"])
    if "name" in changes:
        changes["name"] = changes["name"].strip()
        changes["name_search"] = normalize_department_name(changes["name"])
    if "manager_employee_id" in changes and changes["manager_employee_id"] is not None:
        changes["manager_employee_id"] = parse_object_id(
            changes["manager_employee_id"]
        )
    changes["updated_at"] = utc_now()

    query: dict[str, Any] = {"_id": parse_object_id(department_id)}
    if expected_is_active is not None:
        query["is_active"] = expected_is_active
    database["departments"].update_one(
        query,
        {"$set": changes},
        session=session,
    )
    return find_department_by_id(database, department_id, session=session)


def find_active_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
    session: Any = None,
) -> dict[str, Any] | None:
    """Find a current active employee suitable to manage a department."""
    return database["employees"].find_one(
        {"_id": parse_object_id(employee_id), "status": "active"},
        session=session,
    )


def _department_query(
    department_id: ObjectId,
    search: str | None,
) -> dict[str, Any]:
    query: dict[str, Any] = {"department_id": department_id}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"employee_code": {"$regex": escaped, "$options": "i"}},
            {"first_name": {"$regex": escaped, "$options": "i"}},
            {"last_name": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
        ]
    return query


def count_active_department_employees(
    database: Database[Any],
    department_id: ObjectId | str,
    session: Any = None,
) -> int:
    """Count active employees assigned to a department."""
    return database["employees"].count_documents(
        {
            "department_id": parse_object_id(department_id),
            "status": "active",
        },
        session=session,
    )


def list_department_employees(
    database: Database[Any],
    department_id: ObjectId | str,
    *,
    search: str | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one safe, paginated employee result page."""
    if sort_by is not None and sort_by not in EMPLOYEE_SORT_FIELDS:
        raise ValueError("Employee sort field is not allowed.")
    department_object_id = parse_object_id(department_id)
    sort_fields = (
        [(sort_by, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if sort_by is not None
        else [("created_at", -1), ("_id", 1)]
    )
    cursor = (
        database["employees"]
        .find(_department_query(department_object_id, search))
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )
    return [
        {
            "_id": employee["_id"],
            **{
                field: employee[field]
                for field in _EMPLOYEE_RESPONSE_FIELDS
                if field in employee
            },
        }
        for employee in cursor
    ]


def count_department_employees(
    database: Database[Any],
    department_id: ObjectId | str,
    *,
    search: str | None,
) -> int:
    """Count all employees matching the department employee-list filters."""
    return count_query_matches(
        database["employees"],
        _department_query(parse_object_id(department_id), search),
    )


def serialize_department_fields(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return only the public department fields and the stable ``id`` key."""
    return {
        "id": document["_id"],
        **{
            field: document.get(field)
            for field in _DEPARTMENT_FIELDS
        },
    }
