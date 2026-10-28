from datetime import datetime, timezone

from common.time import utc_now


def test_utc_now_returns_timezone_aware_utc_datetime():
    value = utc_now()

    assert isinstance(value, datetime)
    assert value.tzinfo is timezone.utc
    assert value.utcoffset().total_seconds() == 0
