"""Report date handling, permission-filtered dashboard data, and serialization."""

import calendar
import logging
from collections.abc import Callable
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from bson.decimal128 import Decimal128
from django.conf import settings
from pymongo.database import Database
from pymongo.errors import PyMongoError

from common.pagination import Pagination
from common.serialization import serialize_document
from reports import repository

logger = logging.getLogger(__name__)


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


def _purchase_chart_data(
    database: Database[Any],
    sales_chart: list[dict[str, Any]],
    *,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Align fulfilled net sales with monthly purchase commitments."""
    start, end = _default_month_window(now)
    purchase_rows = repository.monthly_purchase_totals(
        database,
        start=start,
        end=end,
        timezone_name=settings.BUSINESS_TIMEZONE,
    )
    purchases_by_month = {row["_id"]: row for row in purchase_rows}
    return [
        {
            "month": month["month"],
            "net_sales": month["net_sales"],
            "purchase_total": _money_text(
                purchases_by_month.get(month["month"], {}).get(
                    "purchase_total",
                    Decimal128("0.00"),
                )
            ),
            "purchase_count": purchases_by_month.get(
                month["month"],
                {},
            ).get("purchase_count", 0),
        }
        for month in sales_chart
    ]


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


def _load_dashboard_widget(
    name: str,
    loader: Callable[[], Any],
    widget_errors: dict[str, dict[str, str]],
) -> Any:
    """Run one widget query and convert MongoDB failures to safe widget errors."""
    try:
        return loader()
    except PyMongoError:
        logger.exception(
            "Dashboard widget aggregation failed",
            extra={"widget": name},
        )
        widget_errors[name] = {
            "code": "widget_unavailable",
            "message": "This dashboard widget could not be loaded.",
        }
        return None


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
    widget_errors: dict[str, dict[str, str]] = {}
    if "employees:read" in permissions:
        value = _load_dashboard_widget(
            "total_employees",
            lambda: repository.active_count(database, "employees", "status"),
            widget_errors,
        )
        if value is not None:
            widgets["total_employees"] = value
    if "departments:read" in permissions:
        value = _load_dashboard_widget(
            "total_departments",
            lambda: repository.active_count(database, "departments", "is_active"),
            widget_errors,
        )
        if value is not None:
            widgets["total_departments"] = value
    if "products:read" in permissions:
        value = _load_dashboard_widget(
            "total_products",
            lambda: repository.active_count(database, "products", "is_active"),
            widget_errors,
        )
        if value is not None:
            widgets["total_products"] = value
    if {"products:read", "stock:read"} <= permissions:
        stats = _load_dashboard_widget(
            "inventory_statistics",
            lambda: inventory_report(database),
            widget_errors,
        )
        if stats is not None:
            widgets["inventory_statistics"] = stats
            widgets["low_stock_count"] = stats["low_stock_count"]
        else:
            widget_errors["low_stock_count"] = widget_errors[
                "inventory_statistics"
            ]
        categories = _load_dashboard_widget(
            "inventory_by_category",
            lambda: [
                {
                    "category": row["_id"],
                    "product_count": row["product_count"],
                    "available_quantity": row["available_quantity"],
                    "stock_cost_value": _money_text(row["stock_cost_value"]),
                }
                for row in repository.inventory_by_category(database)
            ],
            widget_errors,
        )
        if categories is not None:
            widgets["inventory_by_category"] = categories
        low_stock_values = _load_dashboard_widget(
            "low_stock_products",
            lambda: [
                _public(value)
                for value in repository.list_low_stock(
                    database,
                    start=None,
                    end=None,
                    skip=0,
                    limit=10,
                )[0]
            ],
            widget_errors,
        )
        if low_stock_values is not None:
            widgets["low_stock_products"] = low_stock_values
    if "suppliers:read" in permissions:
        value = _load_dashboard_widget(
            "total_suppliers",
            lambda: repository.active_count(database, "suppliers", "status"),
            widget_errors,
        )
        if value is not None:
            widgets["total_suppliers"] = value
    if "customers:read" in permissions:
        value = _load_dashboard_widget(
            "total_customers",
            lambda: repository.active_count(database, "customers", "status"),
            widget_errors,
        )
        if value is not None:
            widgets["total_customers"] = value
    if "purchase:read" in permissions:
        pending = _load_dashboard_widget(
            "pending_purchase_orders",
            lambda: repository.pending_purchase_count(database),
            widget_errors,
        )
        if pending is not None:
            widgets["pending_purchase_orders"] = pending
        statistics = _load_dashboard_widget(
            "purchase_statistics",
            lambda: _purchase_statistics(database),
            widget_errors,
        )
        if statistics is not None:
            widgets["purchase_statistics"] = statistics
    if "sales:read" in permissions:
        sales_chart = _load_dashboard_widget(
            "sales_chart",
            lambda: _monthly_sales_data(
                database,
                date_from=None,
                date_to=None,
                now=now,
            ),
            widget_errors,
        )
        start, end = _current_month_window(now)
        current = _load_dashboard_widget(
            "monthly_sales",
            lambda: repository.monthly_sales(
                database,
                start=start,
                end=end,
                timezone_name=settings.BUSINESS_TIMEZONE,
            ),
            widget_errors,
        )
        if current is not None:
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
        if sales_chart is not None:
            widgets["sales_chart"] = sales_chart
    if {"sales:read", "purchase:read"} <= permissions:
        if sales_chart is None:
            widget_errors["purchases_vs_sales"] = {
                "code": "widget_unavailable",
                "message": "This dashboard widget could not be loaded.",
            }
        else:
            comparison = _load_dashboard_widget(
                "purchases_vs_sales",
                lambda: _purchase_chart_data(database, sales_chart, now=now),
                widget_errors,
            )
            if comparison is not None:
                widgets["purchases_vs_sales"] = comparison
    if "sales:read" in permissions or "purchase:read" in permissions:
        start, end = _date_window(date_from, date_to)
        transactions = _load_dashboard_widget(
            "recent_transactions",
            lambda: _recent_transactions(
                database,
                permissions=permissions,
                start=start,
                end=end,
            ),
            widget_errors,
        )
        if transactions is not None:
            widgets["recent_transactions"] = transactions
    if widget_errors:
        widgets["widget_errors"] = widget_errors
    return widgets
