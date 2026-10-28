import pytest

from common.exceptions import ValidationFailed
from common.pagination import MAX_PAGE_SIZE, parse_pagination


def test_pagination_defaults_and_meta_for_empty_result():
    pagination = parse_pagination()

    assert pagination.page == 1
    assert pagination.page_size == 20
    assert pagination.skip == 0
    assert pagination.limit == 20
    assert pagination.build_meta(0) == {
        "page": 1,
        "page_size": 20,
        "total": 0,
        "total_pages": 0,
    }


def test_pagination_parses_values_and_builds_meta():
    pagination = parse_pagination(
        "3",
        "25",
        sort_by="created_at",
        sort_order="DESC",
        allowed_sort_fields={"created_at", "name"},
    )

    assert pagination.skip == 50
    assert pagination.limit == 25
    assert pagination.sort == {"created_at": -1}
    assert pagination.build_meta(51) == {
        "page": 3,
        "page_size": 25,
        "total": 51,
        "total_pages": 3,
    }


@pytest.mark.parametrize(
    ("page", "page_size"),
    [("0", None), ("-1", None), ("abc", None), (None, "0"), (None, "1.5")],
)
def test_pagination_rejects_invalid_numbers(page, page_size):
    with pytest.raises(ValidationFailed):
        parse_pagination(page, page_size)


def test_pagination_rejects_page_size_above_maximum():
    with pytest.raises(ValidationFailed):
        parse_pagination(page_size=MAX_PAGE_SIZE + 1)


def test_pagination_rejects_sort_fields_not_in_allowlist():
    with pytest.raises(ValidationFailed):
        parse_pagination(sort_by="secret_field", allowed_sort_fields={"name"})


def test_pagination_rejects_invalid_sort_order():
    with pytest.raises(ValidationFailed):
        parse_pagination(sort_order="sideways")


def test_pagination_rejects_non_string_sort_values():
    with pytest.raises(ValidationFailed):
        parse_pagination(sort_by=[], allowed_sort_fields={"name"})
    with pytest.raises(ValidationFailed):
        parse_pagination(sort_order=None)


def test_pagination_meta_rejects_invalid_total():
    pagination = parse_pagination()

    with pytest.raises(ValueError):
        pagination.build_meta(-1)
