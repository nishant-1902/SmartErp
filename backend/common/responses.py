"""Helpers for returning the API's standard JSON response envelopes."""

from typing import Any

from rest_framework.response import Response


def success_response(
    data: Any,
    meta: dict[str, Any] | None = None,
    status: int = 200,
) -> Response:
    """Build a successful API response."""
    return Response(
        {
            "success": True,
            "data": data,
            "meta": meta if meta is not None else {},
        },
        status=status,
    )


def error_response(
    code: str,
    message: str,
    details: Any = None,
    *,
    status: int,
) -> Response:
    """Build an error API response with a required HTTP status."""
    return Response(
        {
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details if details is not None else {},
            },
        },
        status=status,
    )
