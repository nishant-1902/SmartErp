import pytest

from common.exceptions import ValidationFailed
from common.sanitize import escape_regex, sanitize_dict


def test_sanitize_dict_accepts_safe_nested_input_without_mutation():
    value = {"name": "item", "filters": {"active": True}, "values": [{"count": 2}]}

    assert sanitize_dict(value) is value


@pytest.mark.parametrize(
    "value",
    [
        {"$ne": None},
        {"profile.name": "Nishant"},
        {"filters": {"$gt": 1}},
        {"items": [{"$where": "return true"}]},
    ],
)
def test_sanitize_dict_rejects_operator_and_dotted_keys(value):
    with pytest.raises(ValidationFailed):
        sanitize_dict(value)


def test_sanitize_dict_rejects_non_object_input():
    with pytest.raises(ValidationFailed):
        sanitize_dict(["name"])


def test_escape_regex_treats_search_text_as_literal():
    assert escape_regex("a.*[b]") == r"a\.\*\[b\]"
