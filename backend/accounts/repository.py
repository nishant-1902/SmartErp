"""PyMongo repositories for user accounts and refresh-token records."""

from collections.abc import Mapping
from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo.database import Database

from common.exceptions import ValidationFailed

from common.object_id import parse_object_id
from common.time import utc_now

USER_ROLES = {
    "super_admin",
    "hr_manager",
    "inventory_manager",
    "purchase_manager",
    "sales_manager",
    "employee",
}

_USER_UPDATE_FIELDS = {
    "email",
    "password_hash",
    "full_name",
    "role",
    "is_active",
    "employee_id",
    "last_login_at",
}
_REFRESH_TOKEN_UPDATE_FIELDS = {
    "status",
    "revoked_at",
    "replaced_by",
    "user_agent",
    "ip",
}


def normalize_email(email: str) -> str:
    """Trim and lowercase an email address."""
    normalized = email.strip().lower()
    if not normalized:
        raise ValueError("Email must not be empty.")
    return normalized


def create_user(
    database: Database[Any],
    *,
    email: str,
    password_hash: str,
    full_name: str,
    role: str,
    employee_id: ObjectId | str | None = None,
) -> dict[str, Any]:
    """Create and return a user document with normalized account fields."""
    normalized_name = full_name.strip()
    if not normalized_name:
        raise ValueError("Full name must not be empty.")
    if role not in USER_ROLES:
        raise ValueError("Role is not supported.")
    if not password_hash:
        raise ValueError("Password hash must not be empty.")

    now = utc_now()
    document: dict[str, Any] = {
        "email": normalize_email(email),
        "password_hash": password_hash,
        "full_name": normalized_name,
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": (
            parse_object_id(employee_id) if employee_id is not None else None
        ),
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    result = database["users"].insert_one(document)
    document["_id"] = result.inserted_id
    return document


def find_user_by_email(database: Database[Any], email: str) -> dict[str, Any] | None:
    """Find a user by its normalized email address."""
    return database["users"].find_one({"email": normalize_email(email)})


def find_user_by_id(
    database: Database[Any],
    user_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Find a user by a validated BSON ObjectId."""
    return database["users"].find_one({"_id": parse_object_id(user_id)})


def update_user(
    database: Database[Any],
    user_id: ObjectId | str,
    updates: Mapping[str, Any],
) -> dict[str, Any] | None:
    """Update an allowlisted set of user fields and return the updated document."""
    if not updates:
        raise ValueError("At least one user field must be updated.")
    unsafe_fields = {
        field
        for field in updates
        if field.startswith("$") or "." in field or field not in _USER_UPDATE_FIELDS
    }
    if unsafe_fields:
        raise ValueError("User update contains an unsupported field.")

    changes = dict(updates)
    if "email" in changes:
        changes["email"] = normalize_email(changes["email"])
    if "full_name" in changes:
        changes["full_name"] = changes["full_name"].strip()
        if not changes["full_name"]:
            raise ValueError("Full name must not be empty.")
    if "role" in changes and changes["role"] not in USER_ROLES:
        raise ValueError("Role is not supported.")
    if "employee_id" in changes and changes["employee_id"] is not None:
        changes["employee_id"] = parse_object_id(changes["employee_id"])

    update: dict[str, Any] = {
        "$set": {**changes, "updated_at": utc_now()}
    }
    if "password_hash" in changes or changes.get("is_active") is False:
        update["$inc"] = {"token_version": 1}

    database["users"].update_one(
        {"_id": parse_object_id(user_id)},
        update,
    )
    return find_user_by_id(database, user_id)


def deactivate_user(
    database: Database[Any],
    user_id: ObjectId | str,
) -> dict[str, Any] | None:
    """Deactivate a user and invalidate all of that user's access tokens."""
    database["users"].update_one(
        {"_id": parse_object_id(user_id), "is_active": True},
        {
            "$set": {"is_active": False, "updated_at": utc_now()},
            "$inc": {"token_version": 1},
        },
    )
    return find_user_by_id(database, user_id)


def create_refresh_token(
    database: Database[Any],
    *,
    user_id: ObjectId | str,
    token_hash: str,
    family_id: str,
    expires_at: datetime,
    user_agent: str | None = None,
    ip: str | None = None,
    now: datetime | None = None,
) -> ObjectId:
    """Insert a refresh-token record containing only the opaque token's hash."""
    if not token_hash or not family_id:
        raise ValueError("Token hash and family ID must not be empty.")
    created_at = now or utc_now()
    document = {
        "user_id": parse_object_id(user_id),
        "token_hash": token_hash,
        "family_id": family_id,
        "status": "active",
        "created_at": created_at,
        "expires_at": expires_at,
        "revoked_at": None,
        "replaced_by": None,
        "user_agent": user_agent,
        "ip": ip,
    }
    return database["refresh_tokens"].insert_one(document).inserted_id


def find_refresh_token_by_hash(
    database: Database[Any],
    token_hash: str,
) -> dict[str, Any] | None:
    """Find a refresh-token record using its SHA-256 hash."""
    return database["refresh_tokens"].find_one({"token_hash": token_hash})


def update_refresh_token(
    database: Database[Any],
    token_id: ObjectId | str,
    updates: Mapping[str, Any],
) -> bool:
    """Update allowlisted refresh-token metadata and report whether it matched."""
    if not updates or any(
        field.startswith("$")
        or "." in field
        or field not in _REFRESH_TOKEN_UPDATE_FIELDS
        for field in updates
    ):
        raise ValueError("Refresh-token update contains an unsupported field.")
    result = database["refresh_tokens"].update_one(
        {"_id": parse_object_id(token_id)},
        {"$set": dict(updates)},
    )
    return result.matched_count == 1


def rotate_refresh_token_record(
    database: Database[Any],
    token_id: ObjectId,
    replacement_id: ObjectId,
    now: datetime,
) -> bool:
    """Atomically mark an active record rotated by its replacement."""
    result = database["refresh_tokens"].update_one(
        {"_id": token_id, "status": "active"},
        {
            "$set": {
                "status": "rotated",
                "revoked_at": now,
                "replaced_by": replacement_id,
            }
        },
    )
    return result.matched_count == 1


def revoke_refresh_token_family(
    database: Database[Any],
    family_id: str,
    now: datetime,
) -> None:
    """Revoke every token record in a family."""
    database["refresh_tokens"].update_many(
        {"family_id": family_id},
        {"$set": {"status": "revoked", "revoked_at": now}},
    )


def delete_refresh_token(database: Database[Any], token_id: ObjectId) -> None:
    """Delete an unissued replacement after a failed rotation compare-and-set."""
    database["refresh_tokens"].delete_one({"_id": token_id})


def write_audit_log(
    database: Database[Any],
    *,
    actor_id: ObjectId | str | None,
    action: str,
    resource: str,
    resource_id: str | ObjectId | None,
    outcome: str,
    ip: str | None = None,
    user_agent: str | None = None,
    now: datetime | None = None,
) -> ObjectId:
    """Append an audit log entry summarizing a security-sensitive action."""
    document = {
        "actor_id": parse_object_id(actor_id) if actor_id is not None else None,
        "action": action,
        "entity_type": resource,
        "entity_id": str(resource_id) if resource_id is not None else None,
        "request_id": None,
        "before": None,
        "after": None,
        "created_at": now or utc_now(),
    }
    document["outcome"] = outcome
    document["ip"] = ip
    document["user_agent"] = user_agent
    return database["audit_logs"].insert_one(document).inserted_id


def get_login_attempt(
    database: Database[Any],
    email: str,
    client_ip: str,
) -> dict[str, Any] | None:
    """Fetch the current rate-limit record for one email/IP pair."""
    return database["login_attempts"].find_one({
        "email": normalize_email(email),
        "client_ip": client_ip,
    })


def upsert_login_attempt(
    database: Database[Any],
    email: str,
    client_ip: str,
    *,
    failed_count: int,
    window_started_at: datetime,
    expires_at: datetime,
    locked_until: datetime | None = None,
) -> None:
    """Create or update the current login-attempt counter for an email/IP pair."""
    database["login_attempts"].update_one(
        {"email": normalize_email(email), "client_ip": client_ip},
        {
            "$set": {
                "email": normalize_email(email),
                "client_ip": client_ip,
                "failed_count": failed_count,
                "window_started_at": window_started_at,
                "expires_at": expires_at,
                "locked_until": locked_until,
            }
        },
        upsert=True,
    )


def clear_login_attempts(database: Database[Any], email: str, client_ip: str) -> None:
    """Clear all failed-login counters for a successful login."""
    database["login_attempts"].delete_one({
        "email": normalize_email(email),
        "client_ip": client_ip,
    })
