from common.responses import error_response, success_response


def test_success_response_uses_standard_envelope():
    response = success_response({"id": "abc"})

    assert response.status_code == 200
    assert response.data == {
        "success": True,
        "data": {"id": "abc"},
        "meta": {},
    }


def test_success_response_includes_meta_and_custom_status():
    response = success_response([], meta={"page": 2}, status=201)

    assert response.status_code == 201
    assert response.data["meta"] == {"page": 2}


def test_error_response_uses_standard_envelope():
    response = error_response(
        "not_found",
        "Missing.",
        {"resource": "item"},
        status=404,
    )

    assert response.status_code == 404
    assert response.data == {
        "success": False,
        "error": {
            "code": "not_found",
            "message": "Missing.",
            "details": {"resource": "item"},
        },
    }


def test_error_response_defaults_details_to_empty_object():
    response = error_response("conflict", "Conflict.", status=409)

    assert response.data["error"]["details"] == {}
