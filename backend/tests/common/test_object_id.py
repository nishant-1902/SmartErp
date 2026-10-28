import pytest
from bson import ObjectId

from common.exceptions import ValidationFailed
from common.object_id import is_valid_object_id, parse_object_id


def test_parse_object_id_from_string():
    value = "507f1f77bcf86cd799439011"

    assert parse_object_id(value) == ObjectId(value)


def test_parse_object_id_accepts_existing_object_id():
    value = ObjectId()

    assert parse_object_id(value) is value


@pytest.mark.parametrize("value", ["not-an-id", "", None, 123, b"123456789012"])
def test_parse_object_id_rejects_invalid_values(value):
    with pytest.raises(ValidationFailed) as exc_info:
        parse_object_id(value)

    assert exc_info.value.status_code == 400


def test_is_valid_object_id_checks_strings_and_objects():
    assert is_valid_object_id("507f1f77bcf86cd799439011")
    assert is_valid_object_id(ObjectId())
    assert not is_valid_object_id("not-an-id")
    assert not is_valid_object_id(None)
