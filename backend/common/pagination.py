"""Validated pagination and sort helpers for API list endpoints."""

from collections.abc import Collection
from dataclasses import dataclass
from math import ceil

from common.exceptions import ValidationFailed

DEFAULT_PAGE_SIZE = 20
MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class Pagination:
    """Parsed pagination values and an optional whitelisted sort order."""

    page: int
    page_size: int
    sort_by: str | None = None
    sort_order: str = "asc"

    @property
    def skip(self) -> int:
        """Number of documents to skip for this page."""
        return (self.page - 1) * self.page_size

    @property
    def limit(self) -> int:
        """Maximum number of documents to return."""
        return self.page_size

    @property
    def sort(self) -> dict[str, int] | None:
        """MongoDB sort specification, or None when no sort was requested."""
        if self.sort_by is None:
            return None
        return {self.sort_by: 1 if self.sort_order == "asc" else -1}

    def build_meta(self, total: int) -> dict[str, int]:
        """Build the standard pagination metadata for a total item count."""
        if isinstance(total, bool) or not isinstance(total, int) or total < 0:
            raise ValueError("Total must be a non-negative integer.")
        return {
            "page": self.page,
            "page_size": self.page_size,
            "total": total,
            "total_pages": ceil(total / self.page_size) if total else 0,
        }


def _parse_positive_int(value: str | int | None, field: str, default: int) -> int:
    if value is None:
        return default
    if isinstance(value, bool):
        raise ValidationFailed(
            f"{field} must be a positive integer.",
            details={field: "Must be a positive integer."},
        )
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationFailed(
            f"{field} must be a positive integer.",
            details={field: "Must be a positive integer."},
        ) from exc
    if parsed < 1 or str(value).strip() not in {str(parsed), f"+{parsed}"}:
        raise ValidationFailed(
            f"{field} must be a positive integer.",
            details={field: "Must be a positive integer."},
        )
    return parsed


def parse_pagination(
    page: str | int | None = None,
    page_size: str | int | None = None,
    *,
    sort_by: str | None = None,
    sort_order: str = "asc",
    allowed_sort_fields: Collection[str] = (),
) -> Pagination:
    """Validate page, page size, and optional sort against an allowlist."""
    parsed_page = _parse_positive_int(page, "page", 1)
    parsed_page_size = _parse_positive_int(page_size, "page_size", DEFAULT_PAGE_SIZE)
    if parsed_page_size > MAX_PAGE_SIZE:
        raise ValidationFailed(
            f"page_size must not exceed {MAX_PAGE_SIZE}.",
            details={"page_size": f"Must not exceed {MAX_PAGE_SIZE}."},
        )

    if sort_by is not None and (
        not isinstance(sort_by, str) or sort_by not in allowed_sort_fields
    ):
        raise ValidationFailed(
            "Requested sort field is not allowed.",
            details={"sort_by": "Choose an allowed sort field."},
        )
    if not isinstance(sort_order, str):
        raise ValidationFailed(
            "sort_order must be 'asc' or 'desc'.",
            details={"sort_order": "Use 'asc' or 'desc'."},
        )
    normalized_order = sort_order.lower()
    if normalized_order not in {"asc", "desc"}:
        raise ValidationFailed(
            "sort_order must be 'asc' or 'desc'.",
            details={"sort_order": "Use 'asc' or 'desc'."},
        )

    return Pagination(
        page=parsed_page,
        page_size=parsed_page_size,
        sort_by=sort_by,
        sort_order=normalized_order,
    )
