"""Shared operational endpoints."""

from typing import Any

from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.response import Response

from common.responses import success_response


@api_view(["GET"])
@authentication_classes([])
@permission_classes([])
def health_check(request: Any) -> Response:
    """Return a public liveness response without querying MongoDB."""
    return success_response({"status": "ok"})
