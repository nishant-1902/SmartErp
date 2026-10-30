"""PyMongo data access for employee records."""

from collections.abc import Mapping
from datetime import date, datetime, time, timezone
import re
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.object_id import parse_object_id
from common.time import utc_now

EMPLOYEE_SORT_FIELDS = frozenset(
    {
        "employee_code",
        "first_name",
        "last_name",
        "email",
        "department_id",
        "designation",
        "joining_date",
        "status",
        "created_at",
        "updated_at",
    }
)
EMPLOYEE_RESPONSE_FIELDS = (
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
EMPLOYEE_UPDATE_FIELDS = frozenset(
    {
        "first_name",
        "last_name",
        "email",
        "phone",
        "department_id",
        "designation",
        "joining_date",
        "status",
    }
)


def _bson_date(value: date | datetime) -> datetime:
    """Convert a validated calendar date to a timezone-aware BSON datetime."""
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


def normalize_employee_code(employee_code: str) -> str:
    """Normalize employee codes to uppercase for consistent uniqueness."""
    normalized = employee_code.strip().upper()
    if not normalized:
        raise ValueError("Employee code must not be empty.")
    return normalized


def normalize_employee_email(email: str) -> str:
    """Normalize employee email addresses to lowercase."""
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Employee email must not be empty.")
    return normalized


def _public_projection(document: Mapping[str, Any]) -> dict[str, Any]:
    """Project only employee directory fields and the stable public ID."""
    return {
        "_id": document["_id"],
        **{
            field: document[field]
            for field in EMPLOYEE_RESPONSE_FIELDS
            if field in document
        },
    }


def create_employee(
    database: Database[Any],
    *,
    employee_code: str,
    first_name: str,
    last_name: str,
    email: str,
    phone: str | None,
    department_id: ObjectId | str,
    designation: str,
    joining_date: date | datetime,
    status: str,
    session: Any = None,
) -> dict[str, Any]:
    """Insert a normalized employee document with UTC timestamps."""
    normalized_first = first_name.strip()
    normalized_last = last_name.strip()
    normalized_designation = designation.strip()
    if not normalized_first or not normalized_last or not normalized_designation:
        raise ValueError("Employee names and designation must not be empty.")
    if status not in {"active", "inactive", "on_leave"}:
        raise ValueError("Employee status is not supported.")

    now = utc_now()
    document: dict[str, Any] = {
        "employee_code": normalize_employee_code(employee_code),
        "first_name": normalized_first,
        "last_name": normalized_last,
        "name_search": f"{normalized_first} {normalized_last}".casefold(),
        "email": normalize_employee_email(email),
        "phone": phone,
        "department_id": parse_object_id(department_id),
        "designation": normalized_designation,
        "joining_date": _bson_date(joining_date),
        "status": status,
        "created_at": now,
        "updated_at": now,
        "deactivated_at": now if status == "inactive" else None,
    }
    result = database["employees"].insert_one(document, session=session)
    document["_id"] = result.inserted_id
    return document


def find_employee_by_id(
    database: Database[Any],
    employee_id: ObjectId | str,
    session: Any = None,
) -> dict[str, Any] | None:
    """Find an employee by a validated ObjectId."""
    return database["employees"].find_one(
        {"_id": parse_object_id(employee_id)},
        session=session,
    )


def find_employee_by_code(database: Database[Any], employee_code: str) -> dict[str, Any] | None:
    """Find an employee by its normalized unique code."""
    return database["employees"].find_one(
        {"employee_code": normalize_employee_code(employee_code)}
    )


def find_employee_by_email(database: Database[Any], email: str) -> dict[str, Any] | None:
    """Find an employee by its normalized unique email."""
    return database["employees"].find_one(
        {"email": normalize_employee_email(email)}
    )


def _employee_list_query(
    *,
    search: str | None,
    department_id: ObjectId | None,
    status: str | None,
) -> dict[str, Any]:
    query: dict[str, Any] = {}
    if search:
        escaped = re.escape(search.strip())
        query["$or"] = [
            {"employee_code": {"$regex": escaped, "$options": "i"}},
            {"first_name": {"$regex": escaped, "$options": "i"}},
            {"last_name": {"$regex": escaped, "$options": "i"}},
            {"name_search": {"$regex": escaped, "$options": "i"}},
            {"email": {"$regex": escaped, "$options": "i"}},
        ]
    if department_id is not None:
        query["department_id"] = parse_object_id(department_id)
    if status is not None:
        query["status"] = status
    return query


def list_employees(
    database: Database[Any],
    *,
    search: str | None,
    department_id: ObjectId | None,
    status: str | None,
    skip: int,
    limit: int,
    sort_by: str | None,
    sort_order: str,
) -> list[dict[str, Any]]:
    """Return one safe employee directory page matching validated filters."""
    if sort_by is not None and sort_by not in EMPLOYEE_SORT_FIELDS:
        raise ValueError("Employee sort field is not allowed.")
    sort_fields = (
        [(sort_by, 1 if sort_order == "asc" else -1), ("_id", 1)]
        if sort_by is not None
        else [("created_at", -1), ("_id", 1)]
    )
    cursor = (
        database["employees"]
        .find(
            _employee_list_query(
                search=search,
                department_id=department_id,
                status=status,
            )
        )
        .sort(sort_fields)
        .skip(skip)
        .limit(limit)
    )
    return [_public_projection(document) for document in cursor]


def count_employees(
    database: Database[Any],
    *,
    search: str | None,
    department_id: ObjectId | None,
    status: str | None,
) -> int:
    """Count employees matching the same validated list filters."""
    return database["employees"].count_documents(
        _employee_list_query(
            search=search,
            department_id=department_id,
            status=status,
        )
    )


def update_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
    updates: Mapping[str, Any],
    *,
    session: Any = None,
) -> dict[str, Any] | None:
    """Update an allowlisted employee field set and return the updated record."""
    if not updates or any(
        not isinstance(field, str)
        or field.startswith("$")
        or "." in field
        or field not in EMPLOYEE_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Employee update contains an unsupported field.")

    changes = dict(updates)
    if "email" in changes:
        changes["email"] = normalize_employee_email(changes["email"])
    if "department_id" in changes:
        changes["department_id"] = parse_object_id(changes["department_id"])
    if "joining_date" in changes:
        changes["joining_date"] = _bson_date(changes["joining_date"])
    if "first_name" in changes or "last_name" in changes:
        current = find_employee_by_id(database, employee_id, session=session)
        if current is None:
            return None
        first_name = changes.get("first_name", current["first_name"]).strip()
        last_name = changes.get("last_name", current["last_name"]).strip()
        if not first_name or not last_name:
            raise ValueError("Employee names must not be empty.")
        changes["first_name"] = first_name
        changes["last_name"] = last_name
        changes["name_search"] = f"{first_name} {last_name}".casefold()
    if "designation" in changes:
        changes["designation"] = changes["designation"].strip()
        if not changes["designation"]:
            raise ValueError("Employee designation must not be empty.")
    changes["updated_at"] = utc_now()
    if changes.get("status") == "inactive":
        changes["deactivated_at"] = utc_now()
    elif changes.get("status") in {"active", "on_leave"}:
        changes["deactivated_at"] = None

    database["employees"].update_one(
        {"_id": parse_object_id(employee_id)},
        {"$set": changes},
        session=session,
    )
    return find_employee_by_id(database, employee_id, session=session)


def deactivate_employee(
    database: Database[Any],
    employee_id: ObjectId | str,
    *,
    session: Any = None,
) -> dict[str, Any] | None:
    """Set an employee's status to inactive without deleting its document."""
    now = utc_now()
    database["employees"].update_one(
        {"_id": parse_object_id(employee_id), "status": {"$ne": "inactive"}},
        {
            "$set": {
                "status": "inactive",
                "deactivated_at": now,
                "updated_at": now,
            }
        },
        session=session,
    )
    return find_employee_by_id(database, employee_id, session=session)


def list_designations(database: Database[Any]) -> list[str]:
    """Return distinct non-empty employee designations in sorted order."""
    designations = database["employees"].distinct("designation")
    return sorted(
        {
            value.strip()
            for value in designations
            if isinstance(value, str) and value.strip()
        },
        key=lambda value: (value.casefold(), value),
    )


def public_employee(document: Mapping[str, Any]) -> dict[str, Any]:
    """Serialize a Mongo employee into its public directory fields."""
    return _public_projection(document)
