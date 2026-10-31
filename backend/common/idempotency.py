"""Transactional idempotency support for retryable API operations."""

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any, TypeVar
from uuid import UUID

from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from common.exceptions import IdempotencyKeyReuse, ValidationFailed
from common.object_id import parse_object_id
from common.time import utc_now

T = TypeVar("T")
IDEMPOTENCY_TTL = timedelta(hours=24)


def normalize_idempotency_key(value: str | None) -> str:
    """Validate and canonicalize an RFC 4122 UUID idempotency key."""
    if not value:
        raise ValidationFailed(
            "The Idempotency-Key header is required and must be a UUID.",
            details={"Idempotency-Key": "A UUID is required."},
        )
    try:
        return str(UUID(value))
    except (AttributeError, TypeError, ValueError) as exc:
        raise ValidationFailed(
            "The Idempotency-Key header is required and must be a UUID.",
            details={"Idempotency-Key": "A UUID is required."},
        ) from exc


def _request_hash(request_body: Mapping[str, Any]) -> str:
    """Hash a stable JSON representation of a validated request body."""
    canonical = json.dumps(
        request_body,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _scope(user_id: ObjectId | str, endpoint: str) -> str:
    """Build the unique idempotency scope for one user and API operation."""
    parsed_user_id = parse_object_id(user_id)
    if not isinstance(endpoint, str) or not endpoint.strip():
        raise ValueError("Idempotency endpoint must be a non-empty string.")
    scope = f"{parsed_user_id}:{endpoint.strip()}"
    if len(scope) > 200:
        raise ValueError("Idempotency scope exceeds the database field limit.")
    return scope


def _stored_response(
    database: Database[Any],
    *,
    scope: str,
    key: str,
    request_hash: str,
) -> Any | None:
    """Return a completed response or reject reuse with a different body."""
    record = database["idempotency_keys"].find_one({"scope": scope, "key": key})
    if record is None:
        return None
    if record.get("request_hash") != request_hash:
        raise IdempotencyKeyReuse()
    if record.get("status") != "completed" or record.get("response") is None:
        return None
    return record["response"]


def execute_idempotent(
    database: Database[Any],
    *,
    user_id: ObjectId | str,
    endpoint: str,
    key: str,
    request_body: Mapping[str, Any],
    operation: Callable[[ClientSession, ObjectId], T],
    now: datetime | None = None,
) -> T:
    """Run database work once and persist its result in the same transaction.

    The operation may be retried by PyMongo and must perform database work only
    through the provided session. It receives a stable ObjectId for references
    created by the operation.
    """
    normalized_key = normalize_idempotency_key(key)
    scope = _scope(user_id, endpoint)
    body_hash = _request_hash(request_body)
    created_at = now or utc_now()
    if created_at.tzinfo is None or created_at.utcoffset() is None:
        raise ValueError("Idempotency timestamp must be timezone-aware.")

    operation_id = ObjectId()
    client = getattr(database, "client", None)
    if client is None or not callable(getattr(client, "start_session", None)):
        raise ValueError("A MongoDB database client is required for transactions.")

    def transaction(session: ClientSession) -> T:
        existing = database["idempotency_keys"].find_one(
            {"scope": scope, "key": normalized_key},
            session=session,
        )
        if existing is not None:
            if existing.get("request_hash") != body_hash:
                raise IdempotencyKeyReuse()
            if (
                existing.get("status") == "completed"
                and existing.get("response") is not None
            ):
                return existing["response"]
            raise RuntimeError("An incomplete idempotency record was found.")

        database["idempotency_keys"].insert_one(
            {
                "_id": operation_id,
                "scope": scope,
                "key": normalized_key,
                "request_hash": body_hash,
                "status": "processing",
                "result_id": operation_id,
                "response": None,
                "created_at": created_at,
                "expires_at": created_at + IDEMPOTENCY_TTL,
            },
            session=session,
        )
        response = operation(session, operation_id)
        database["idempotency_keys"].update_one(
            {"_id": operation_id, "scope": scope, "key": normalized_key},
            {"$set": {"status": "completed", "response": response}},
            session=session,
        )
        return response

    try:
        with client.start_session() as session:
            return session.with_transaction(
                transaction,
                read_concern=ReadConcern("snapshot"),
                write_concern=WriteConcern("majority"),
            )
    except DuplicateKeyError:
        replay = _stored_response(
            database,
            scope=scope,
            key=normalized_key,
            request_hash=body_hash,
        )
        if replay is not None:
            return replay
        raise
