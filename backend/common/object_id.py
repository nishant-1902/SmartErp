"""Validation helpers for MongoDB ObjectIds."""

from bson import ObjectId

from common.exceptions import ValidationFailed


def is_valid_object_id(value: object) -> bool:
    """Return whether a value is a BSON ObjectId or a valid ObjectId string."""
    if isinstance(value, ObjectId):
        return True
    return isinstance(value, str) and ObjectId.is_valid(value)


def parse_object_id(value: object) -> ObjectId:
    """Parse an ObjectId or raise a client-safe validation error."""
    if not is_valid_object_id(value):
        raise ValidationFailed(
            "Invalid ObjectId.",
            details={"field": "id"},
        )
    return value if isinstance(value, ObjectId) else ObjectId(value)
