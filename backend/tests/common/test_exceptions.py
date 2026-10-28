import logging

from pymongo.errors import DuplicateKeyError
from rest_framework.exceptions import ValidationError
from rest_framework.settings import api_settings

from common.exceptions import (
    ConflictError,
    DuplicateOperation,
    InsufficientStock,
    InvalidStateTransition,
    NotFoundError,
    PermissionDeniedError,
    ValidationFailed,
    api_exception_handler,
)


def test_custom_exceptions_map_to_expected_envelopes():
    examples = [
        (NotFoundError(), 404, "not_found"),
        (ConflictError(), 409, "conflict"),
        (ValidationFailed(), 400, "validation_error"),
        (PermissionDeniedError(), 403, "permission_denied"),
        (InvalidStateTransition(), 409, "invalid_state_transition"),
        (InsufficientStock(), 409, "insufficient_stock"),
        (DuplicateOperation(), 409, "duplicate_operation"),
    ]

    for exception, status, code in examples:
        response = api_exception_handler(exception, {})
        assert response.status_code == status
        assert response.data["success"] is False
        assert response.data["error"]["code"] == code


def test_custom_exception_preserves_message_and_details():
    exception = ValidationFailed("Bad input.", details={"field": "name"})

    response = api_exception_handler(exception, {})

    assert response.data["error"]["message"] == "Bad input."
    assert response.data["error"]["details"] == {"field": "name"}


def test_custom_exception_uses_structured_detail_when_details_not_separate():
    exception = ValidationFailed({"field": "Invalid."})

    response = api_exception_handler(exception, {})

    assert response.data["error"]["details"] == {"field": "Invalid."}


def test_drf_validation_error_uses_envelope_with_field_details():
    response = api_exception_handler(
        ValidationError({"name": ["This field is required."]}),
        {},
    )

    assert response.status_code == 400
    assert response.data == {
        "success": False,
        "error": {
            "code": "validation_error",
            "message": "Request validation failed.",
            "details": {"name": ["This field is required."]},
        },
    }


def test_duplicate_key_error_does_not_expose_index_name():
    exception = DuplicateKeyError(
        "duplicate key error index: secret_collection_secret_field_idx"
    )

    response = api_exception_handler(exception, {})
    response_text = str(response.data)

    assert response.status_code == 409
    assert response.data["error"]["code"] == "duplicate_key"
    assert "secret_collection_secret_field_idx" not in response_text


def test_unknown_exception_is_logged_and_returns_generic_message(caplog):
    exception = RuntimeError("sensitive database detail")

    with caplog.at_level(logging.ERROR, logger="common.exceptions"):
        response = api_exception_handler(exception, {})

    assert response.status_code == 500
    assert response.data["error"]["message"] == "An unexpected error occurred."
    assert "sensitive database detail" not in str(response.data)
    assert "Unhandled API exception" in caplog.text
    assert "sensitive database detail" in caplog.text


def test_django_rest_framework_uses_shared_exception_handler():
    assert api_settings.EXCEPTION_HANDLER is api_exception_handler
