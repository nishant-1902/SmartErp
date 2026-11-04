"""Report date handling, permission-filtered dashboard data, and serialization."""

import calendar
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from bson.decimal128 import Decimal128
from django.conf import settings
from pymongo.database import Database

from common.pagination import Pagination
from common.serialization import serialize_document
from reports import repository


def _business_timezone() -> ZoneInfo:
    """Return the configured business timezone."""
    return ZoneInfo(settings.BUSINESS_TIMEZONE)


def _to_utc_start(value: date | None) -> datetime | None:
    """Convert a local calendar date to its UTC midnight boundary."""
    if value is None:
        return None
    local = datetime.combine(value, time.min, tzinfo=_business_timezone())
    return local.astimezone(timezone.utc)


def _date_window(
    date_from: date | None,
    date_to: date | None,
) -> tuple[datetime | None, datetime | None]:
    """Return an inclusive local date range as a half-open UTC interval."""
    start = _to_utc_start(date_from)
    end = _to_utc_start(date_to + timedelta(days=1)) if date_to else None
    return start, end


def _month_start(value: date) -> date:
    return date(value.year, value.month, 1)


def _add_months(value: date, count: int) -> date:
    month_index = value.year * 12 + value.month - 1 + count
    year, month = divmod(month_index, 12)
    return date(year, month + 1, 1)


def _default_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    """Return UTC bounds spanning this month and the preceding eleven months."""
    local_now = (now or datetime.now(timezone.utc)).astimezone(_business_timezone())
    last_month = _month_start(local_now.date())
    first_month = _add_months(last_month, -11)
    after_last_month = _add_months(last_month, 1)
    return _to_utc_start(first_month), _to_utc_start(after_last_month)


def _monthly_window(
    date_from: date | None,
    date_to: date | None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, date, date]:
    """Resolve report date bounds and inclusive calendar-month labels."""
    if date_from is None and date_to is None:
        start, end = _default_month_window(now)
        local_now = (now or datetime.now(timezone.utc)).astimezone(_business_timezone())
        first_month = _add_months(_month_start(local_now.date()), -11)
        return start, end, first_month, _month_start(local_now.date())

    local_now = (now or datetime.now(timezone.utc)).astimezone(_business_timezone())
    first_month = _month_start(date_from or _add_months(local_now.date(), -11))
    last_month = _month_start(date_to or local_now.date())
    start = _to_utc_start(date_from) if date_from else _to_utc_start(first_month)
    end = (
        _to_utc_start(date_to + timedelta(days=1))
        if date_to
        else _to_utc_start(_add_months(last_month, 1))
    )
    return start, end, first_month, last_month


def _public(document: dict[str, Any]) -> dict[str, Any]:
    """Serialize a MongoDB aggregation result and expose `_id` as `id`."""
    result = serialize_document(document)
    if "_id" in result:
        result["id"] = result.pop("_id")
    return result


def _money_text(value: Any) -> str:
    """Return an exact aggregation money value as a two-decimal string."""
    if isinstance(value, Decimal128):
        value = value.to_decimal()
    if not isinstance(value, Decimal):
        value = Decimal(value)
    return format(value, ".2f")


def _page_meta(pagination: Pagination, total: int) -> dict[str, int]:
    return pagination.build_meta(total)


def _report_page(
    values: list[dict[str, Any]],
    total: int,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    return [_public(value) for value in values], _page_meta(pagination, total)


def sales_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return a paginated, fulfilled-only sales report net of returns."""
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_sales_orders(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    items = [_public(value) for value in values]
    for item in items:
        for field in ("grand_total", "returns_total", "net_total"):
            item[field] = _money_text(item.get(field, Decimal128("0.00")))
    return items, _page_meta(pagination, total)


def _monthly_sales_data(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    start, end, first_month, last_month = _monthly_window(date_from, date_to, now)
    rows = repository.monthly_sales(
        database,
        start=start,
        end=end,
        timezone_name=settings.BUSINESS_TIMEZONE,
    )
    by_month = {row["_id"]: row for row in rows}
    output = []
    current_month = first_month
    while current_month <= last_month:
        key = current_month.strftime("%Y-%m")
        row = by_month.get(key, {})
        output.append(
            {
                "month": key,
                "order_count": row.get("order_count", 0),
                "gross_sales": _money_text(
                    row.get("gross_sales", Decimal128("0.00"))
                ),
                "returns_total": _money_text(
                    row.get("returns_total", Decimal128("0.00"))
                ),
                "net_sales": _money_text(
                    row.get("net_sales", Decimal128("0.00"))
                ),
            }
        )
        current_month = _add_months(current_month, 1)
    return output


def monthly_sales_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
    now: datetime | None = None,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Return paginated calendar-month sales totals, including zero months."""
    rows = _monthly_sales_data(
        database,
        date_from=date_from,
        date_to=date_to,
        now=now,
    )
    page = rows[pagination.skip : pagination.skip + pagination.limit]
    return page, pagination.build_meta(len(rows))


def inventory_report(database: Database[Any]) -> dict[str, Any]:
    """Return inventory quantities and decimal-valued cost statistics."""
    stats = _public(repository.product_inventory_statistics(database))
    stats.pop("id", None)
    stats["stock_cost_value"] = _money_text(stats["stock_cost_value"])
    return stats


def low_stock_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_low_stock(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return _report_page(values, total, pagination)


def employees_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_employees(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return _report_page(values, total, pagination)


def departments_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_departments(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return _report_page(values, total, pagination)


def suppliers_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_suppliers(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return _report_page(values, total, pagination)


def purchases_report(
    database: Database[Any],
    *,
    date_from: date | None,
    date_to: date | None,
    pagination: Pagination,
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    start, end = _date_window(date_from, date_to)
    values, total = repository.list_purchases(
        database,
        start=start,
        end=end,
        skip=pagination.skip,
        limit=pagination.limit,
    )
    return _report_page(values, total, pagination)


def _purchase_statistics(database: Database[Any]) -> dict[str, Any]:
    rows = repository.purchase_statistics(database)
    statuses = {
        row["_id"]: {
            "order_count": row["order_count"],
            "grand_total": _money_text(row["grand_total"]),
        }
        for row in rows
    }
    return {
        "status_breakdown": statuses,
        "pending_order_count": sum(
            statuses.get(status, {}).get("order_count", 0)
            for status in repository.PENDING_PURCHASE_STATUSES
        ),
        "grand_total": _money_text(
            sum(
                (
                    (
                        row["grand_total"].to_decimal()
                        if isinstance(row["grand_total"], Decimal128)
                        else Decimal(row["grand_total"])
                    )
                    for row in rows
                ),
                Decimal("0.00"),
            )
        ),
    }


def _current_month_window(now: datetime | None = None) -> tuple[datetime, datetime]:
    local_now = (now or datetime.now(timezone.utc)).astimezone(_business_timezone())
    first_month = _month_start(local_now.date())
    return (
        _to_utc_start(first_month),
        _to_utc_start(_add_months(first_month, 1)),
    )


def _recent_transactions(
    database: Database[Any],
    *,
    permissions: set[str] | frozenset[str],
    start: datetime | None,
    end: datetime | None,
) -> list[dict[str, Any]]:
    transactions: list[dict[str, Any]] = []
    if "sales:read" in permissions:
        for row in repository.recent_sales(database, start=start, end=end, limit=10):
            transactions.append(
                {
                    "type": "sale",
                    "id": str(row["_id"]),
                    "number": row["order_number"],
                    "party": row["customer_snapshot"]["name"],
                    "status": row["status"],
                    "occurred_at": row["fulfilled_at"],
                    "amount": row["net_total"],
                }
            )
    if "purchase:read" in permissions:
        for row in repository.recent_purchases(
            database,
            start=start,
            end=end,
            limit=10,
        ):
            transactions.append(
                {
                    "type": "purchase",
                    "id": str(row["_id"]),
                    "number": row["po_number"],
                    "party": row["supplier_snapshot"]["name"],
                    "status": row["status"],
                    "occurred_at": row["updated_at"],
                    "amount": row["grand_total"],
                }
            )
    transactions.sort(
        key=lambda transaction: transaction["occurred_at"],
        reverse=True,
    )
    return [_public(value) for value in transactions[:10]]


def dashboard_report(
    database: Database[Any],
    *,
    permissions: set[str] | frozenset[str],
    date_from: date | None,
    date_to: date | None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return only dashboard widgets authorized by the caller's permissions."""
    widgets: dict[str, Any] = {}
    if "employees:read" in permissions:
        widgets["total_employees"] = repository.active_count(
            database,
            "employees",
            "status",
        )
    if "departments:read" in permissions:
        widgets["total_departments"] = repository.active_count(
            database,
            "departments",
            "is_active",
        )
    if "products:read" in permissions:
        widgets["total_products"] = repository.active_count(
            database,
            "products",
            "is_active",
        )
    if {"products:read", "stock:read"} <= permissions:
        widgets["inventory_statistics"] = inventory_report(database)
        widgets["low_stock_count"] = widgets["inventory_statistics"]["low_stock_count"]
    if "suppliers:read" in permissions:
        widgets["total_suppliers"] = repository.active_count(
            database,
            "suppliers",
            "status",
        )
    if "customers:read" in permissions:
        widgets["total_customers"] = repository.active_count(
            database,
            "customers",
            "status",
        )
    if "purchase:read" in permissions:
        widgets["pending_purchase_orders"] = repository.pending_purchase_count(database)
        widgets["purchase_statistics"] = _purchase_statistics(database)
    if "sales:read" in permissions:
        start, end = _current_month_window(now)
        current = repository.monthly_sales(
            database,
            start=start,
            end=end,
            timezone_name=settings.BUSINESS_TIMEZONE,
        )
        month_key = (now or datetime.now(timezone.utc)).astimezone(
            _business_timezone()
        ).strftime("%Y-%m")
        month = next((row for row in current if row["_id"] == month_key), {})
        widgets["monthly_sales"] = {
            "month": month_key,
            "order_count": month.get("order_count", 0),
            "gross_sales": _money_text(
                month.get("gross_sales", Decimal128("0.00"))
            ),
            "returns_total": _money_text(
                month.get("returns_total", Decimal128("0.00"))
            ),
            "net_sales": _money_text(
                month.get("net_sales", Decimal128("0.00"))
            ),
        }
        widgets["sales_chart"] = _monthly_sales_data(
            database,
            date_from=None,
            date_to=None,
            now=now,
        )
    if "sales:read" in permissions or "purchase:read" in permissions:
        start, end = _date_window(date_from, date_to)
        widgets["recent_transactions"] = _recent_transactions(
            database,
            permissions=permissions,
            start=start,
            end=end,
        )
    return widgets
