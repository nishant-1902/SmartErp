"""Helpers for returning the API's standard JSON response envelopes."""

from typing import Any

from rest_framework.response import Response


def success_response(
    data: Any,
    meta: dict[str, Any] | None = None,
    status: int = 200,
    headers: dict[str, str] | None = None,
) -> Response:
    """Build a successful API response."""
    response = Response(
        {
            "success": True,
            "data": data,
            "meta": meta if meta is not None else {},
        },
        status=status,
    )
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response


def error_response(
    code: str,
    message: str,
    details: Any = None,
    *,
    status: int,
    headers: dict[str, str] | None = None,
) -> Response:
    """Build an error API response with a required HTTP status."""
    response = Response(
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
    if headers:
        for key, value in headers.items():
            response[key] = value
    return response
