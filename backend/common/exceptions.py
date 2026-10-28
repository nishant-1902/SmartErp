"""Application exceptions and the shared DRF exception handler."""

import logging
from typing import Any

from pymongo.errors import DuplicateKeyError
from rest_framework.exceptions import APIException, ValidationError
from rest_framework.views import exception_handler as drf_exception_handler
from rest_framework.response import Response

from common.responses import error_response

logger = logging.getLogger(__name__)


class ApplicationError(APIException):
    """Base for expected application errors returned to API clients."""

    status_code = 400
    default_detail = "The request could not be completed."
    default_code = "application_error"

    def __init__(self, message: Any = None, details: Any = None) -> None:
        super().__init__(
            detail=message if message is not None else self.default_detail,
            code=self.default_code,
        )
        self.details = details


class NotFoundError(ApplicationError):
    """Raised when a requested resource does not exist."""

    status_code = 404
    default_detail = "The requested resource was not found."
    default_code = "not_found"


class ConflictError(ApplicationError):
    """Raised when a request conflicts with the current resource state."""

    status_code = 409
    default_detail = "The request conflicts with the current state."
    default_code = "conflict"


class ValidationFailed(ApplicationError):
    """Raised when input fails application-level validation."""

    status_code = 400
    default_detail = "The submitted data is invalid."
    default_code = "validation_error"


class PermissionDeniedError(ApplicationError):
    """Raised when the current user is not allowed to perform an action."""

    status_code = 403
    default_detail = "You do not have permission to perform this action."
    default_code = "permission_denied"


class InvalidStateTransition(ConflictError):
    """Raised when an operation is not allowed in the resource's current state."""

    default_detail = "This state transition is not allowed."
    default_code = "invalid_state_transition"


class InsufficientStock(ConflictError):
    """Raised when an operation needs more stock than is available."""

    default_detail = "There is not enough stock to complete this operation."
    default_code = "insufficient_stock"


class DuplicateOperation(ConflictError):
    """Raised when an idempotent operation has already been applied."""

    default_detail = "This operation has already been completed."
    default_code = "duplicate_operation"


def api_exception_handler(
    exc: Exception,
    context: dict[str, Any],
) -> Response:
    """Convert expected API exceptions to the shared envelope and hide unknown errors."""
    if isinstance(exc, DuplicateKeyError):
        return error_response(
            "duplicate_key",
            "A record with the same unique value already exists.",
            status=409,
        )

    if isinstance(exc, ApplicationError):
        detail = exc.detail
        message = str(detail) if isinstance(detail, str) else exc.default_detail
        details = exc.details
        if details is None and not isinstance(detail, str):
            details = detail
        return error_response(
            exc.default_code,
            message,
            details=details,
            status=exc.status_code,
        )

    response = drf_exception_handler(exc, context)
    if response is None:
        logger.error(
            "Unhandled API exception",
            exc_info=(type(exc), exc, exc.__traceback__),
        )
        return error_response(
            "internal_server_error",
            "An unexpected error occurred.",
            status=500,
        )

    if isinstance(exc, ValidationError):
        return error_response(
            "validation_error",
            "Request validation failed.",
            details=response.data,
            status=response.status_code,
        )

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        detail = detail["detail"]
    if isinstance(detail, str):
        message = detail
        details = None
    else:
        message = "The request could not be completed."
        details = response.data

    return error_response(
        str(getattr(exc, "default_code", "request_error")),
        message,
        details=details,
        status=response.status_code,
    )
