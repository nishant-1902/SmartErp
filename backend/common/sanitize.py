"""Input helpers that prevent MongoDB operator and regex injection."""

import re
from typing import Any

from common.exceptions import ValidationFailed


def sanitize_dict(value: dict[str, Any]) -> dict[str, Any]:
    """Validate keys recursively and return the input dictionary unchanged."""
    if not isinstance(value, dict):
        raise ValidationFailed("Expected an object.", details={"field": "input"})

    def check_keys(item: Any) -> None:
        if isinstance(item, dict):
            for key, nested_value in item.items():
                if not isinstance(key, str) or key.startswith("$") or "." in key:
                    raise ValidationFailed(
                        "Input contains an unsafe key.",
                        details={"reason": "unsafe_key"},
                    )
                check_keys(nested_value)
        elif isinstance(item, (list, tuple)):
            for nested_value in item:
                check_keys(nested_value)

    check_keys(value)
    return value


def escape_regex(value: str) -> str:
    """Escape literal user text before it is used in a regular-expression search."""
    if not isinstance(value, str):
        raise TypeError("Regex search text must be a string.")
    return re.escape(value)
