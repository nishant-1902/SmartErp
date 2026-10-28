"""Convert MongoDB documents to values that JSON renderers can encode."""

from collections.abc import Mapping
from datetime import datetime, timezone
from decimal import Decimal
from math import isfinite
from typing import Any

from bson import ObjectId
from bson.decimal128 import Decimal128


def _serialize_value(value: Any) -> Any:
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        else:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    if isinstance(value, (Decimal128, Decimal)):
        return str(value.to_decimal() if isinstance(value, Decimal128) else value)
    if isinstance(value, Mapping):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_serialize_value(item) for item in value]
    if isinstance(value, float) and not isfinite(value):
        raise ValueError("Non-finite float is not JSON-safe.")
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    raise TypeError(f"Unsupported BSON document value: {type(value).__name__}")


def serialize_document(document: Mapping[str, Any]) -> dict[str, Any]:
    """Return a JSON-safe dictionary for a MongoDB document."""
    if not isinstance(document, Mapping):
        raise TypeError("MongoDB document must be a mapping.")
    return {key: _serialize_value(value) for key, value in document.items()}
