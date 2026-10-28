from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128

from common.serialization import serialize_document


def test_serialize_document_converts_bson_and_nested_values():
    object_id = ObjectId("507f1f77bcf86cd799439011")
    result = serialize_document(
        {
            "_id": object_id,
            "amount": Decimal128("12.30"),
            "created_at": datetime(2026, 1, 2, 3, 4, tzinfo=timezone.utc),
            "items": [{"price": Decimal("0.10"), "id": object_id}],
        }
    )

    assert result == {
        "_id": str(object_id),
        "amount": "12.30",
        "created_at": "2026-01-02T03:04:00+00:00",
        "items": [{"price": "0.10", "id": str(object_id)}],
    }


def test_serialize_document_normalizes_aware_times_to_utc():
    result = serialize_document(
        {"created_at": datetime(2026, 1, 2, 5, 0, tzinfo=timezone(timedelta(hours=2)))}
    )

    assert result["created_at"] == "2026-01-02T03:00:00+00:00"


def test_serialize_document_treats_naive_bson_time_as_utc():
    result = serialize_document({"created_at": datetime(2026, 1, 2, 3, 4)})

    assert result["created_at"] == "2026-01-02T03:04:00+00:00"


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_serialize_document_rejects_non_json_finite_floats(value):
    with pytest.raises(ValueError):
        serialize_document({"value": value})
