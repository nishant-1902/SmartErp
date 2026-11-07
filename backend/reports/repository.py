"""MongoDB aggregation pipelines used by reports."""

from datetime import datetime
from typing import Any

from bson.decimal128 import Decimal128
from pymongo.database import Database

from common.mongo import count_query_matches

PENDING_PURCHASE_STATUSES = [
    "pending_approval",
    "approved",
    "partially_received",
]


def _date_match(field: str, start: datetime | None, end: datetime | None) -> dict[str, Any]:
    bounds: dict[str, datetime] = {}
    if start is not None:
        bounds["$gte"] = start
    if end is not None:
        bounds["$lt"] = end
    return {field: bounds} if bounds else {}


def count_documents(
    database: Database[Any],
    collection_name: str,
    query: dict[str, Any],
) -> int:
    """Count indexed documents matching a fixed, service-owned report query."""
    if not query:
        return count_query_matches(database[collection_name], query)
    values = list(
        database[collection_name].aggregate(
            [{"$match": query}, {"$count": "count"}]
        )
    )
    return values[0]["count"] if values else 0


def active_count(database: Database[Any], collection_name: str, field: str) -> int:
    """Count active records from a fixed collection and status field."""
    status_value = "active" if field == "status" else True
    return count_documents(database, collection_name, {field: status_value})


def pending_purchase_count(database: Database[Any]) -> int:
    """Count purchase orders currently awaiting receipt or approval."""
    return count_documents(
        database,
        "purchase_orders",
        {"status": {"$in": PENDING_PURCHASE_STATUSES}},
    )


def list_sales_orders(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List fulfilled orders with their related credit-note totals."""
    match = {"status": "fulfilled", **_date_match("fulfilled_at", start, end)}
    pipeline = [
        {"$match": match},
        {"$sort": {"fulfilled_at": -1, "_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "sales_returns",
                "localField": "_id",
                "foreignField": "sales_order_id",
                "as": "returns",
            }
        },
        {
            "$addFields": {
                "returns_total": {"$sum": "$returns.total"},
                "net_total": {
                    "$subtract": [
                        "$grand_total",
                        {"$ifNull": [{"$sum": "$returns.total"}, Decimal128("0.00")]},
                    ]
                },
            }
        },
        {
            "$project": {
                "_id": 1,
                "order_number": 1,
                "customer_snapshot": 1,
                "fulfilled_at": 1,
                "grand_total": 1,
                "returns_total": 1,
                "net_total": 1,
            }
        },
    ]
    return list(database["sales_orders"].aggregate(pipeline)), count_documents(
        database,
        "sales_orders",
        match,
    )


def monthly_sales(
    database: Database[Any],
    *,
    start: datetime,
    end: datetime,
    timezone_name: str,
) -> list[dict[str, Any]]:
    """Group fulfilled sales and credit notes by local calendar month."""
    return list(
        database["sales_orders"].aggregate(
            [
                {
                    "$match": {
                        "status": "fulfilled",
                        **_date_match("fulfilled_at", start, end),
                    }
                },
                {
                    "$lookup": {
                        "from": "sales_returns",
                        "localField": "_id",
                        "foreignField": "sales_order_id",
                        "as": "returns",
                    }
                },
                {
                    "$addFields": {
                        "returns_total": {
                            "$ifNull": [
                                {"$sum": "$returns.total"},
                                Decimal128("0.00"),
                            ]
                        },
                        "month": {
                            "$dateToString": {
                                "format": "%Y-%m",
                                "date": "$fulfilled_at",
                                "timezone": timezone_name,
                            }
                        },
                    }
                },
                {
                    "$group": {
                        "_id": "$month",
                        "order_count": {"$sum": 1},
                        "gross_sales": {"$sum": "$grand_total"},
                        "returns_total": {"$sum": "$returns_total"},
                        "net_sales": {
                            "$sum": {"$subtract": ["$grand_total", "$returns_total"]}
                        },
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    )


def product_inventory_statistics(database: Database[Any]) -> dict[str, Any]:
    """Aggregate current active-product quantities and stock cost value."""
    rows = list(
        database["products"].aggregate(
            [
                {"$match": {"is_active": True}},
                {
                    "$group": {
                        "_id": None,
                        "active_products": {"$sum": 1},
                        "quantity_on_hand": {"$sum": "$quantity_on_hand"},
                        "reserved_quantity": {"$sum": "$reserved_quantity"},
                        "available_quantity": {
                            "$sum": {
                                "$subtract": [
                                    "$quantity_on_hand",
                                    "$reserved_quantity",
                                ]
                            }
                        },
                        "low_stock_count": {
                            "$sum": {"$cond": ["$is_low_stock", 1, 0]}
                        },
                        "stock_cost_value": {
                            "$sum": {
                                "$multiply": [
                                    "$cost_price",
                                    "$quantity_on_hand",
                                ]
                            }
                        },
                    }
                },
            ]
        )
    )
    return rows[0] if rows else {
        "active_products": 0,
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "available_quantity": 0,
        "low_stock_count": 0,
        "stock_cost_value": Decimal128("0.00"),
    }


def inventory_by_category(database: Database[Any]) -> list[dict[str, Any]]:
    """Aggregate current active-product stock quantities and cost by category."""
    return list(
        database["products"].aggregate(
            [
                {"$match": {"is_active": True}},
                {
                    "$group": {
                        "_id": "$category",
                        "product_count": {"$sum": 1},
                        "available_quantity": {
                            "$sum": {
                                "$subtract": [
                                    "$quantity_on_hand",
                                    "$reserved_quantity",
                                ]
                            }
                        },
                        "stock_cost_value": {
                            "$sum": {
                                "$multiply": [
                                    "$cost_price",
                                    "$quantity_on_hand",
                                ]
                            }
                        },
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    )


def monthly_purchase_totals(
    database: Database[Any],
    *,
    start: datetime,
    end: datetime,
    timezone_name: str,
) -> list[dict[str, Any]]:
    """Group non-draft purchase commitments by business calendar month."""
    return list(
        database["purchase_orders"].aggregate(
            [
                {
                    "$match": {
                        "created_at": {"$gte": start, "$lt": end},
                        "status": {"$nin": ["draft", "rejected", "cancelled"]},
                    }
                },
                {
                    "$addFields": {
                        "month": {
                            "$dateToString": {
                                "format": "%Y-%m",
                                "date": "$created_at",
                                "timezone": timezone_name,
                            }
                        }
                    }
                },
                {
                    "$group": {
                        "_id": "$month",
                        "purchase_count": {"$sum": 1},
                        "purchase_total": {"$sum": "$grand_total"},
                    }
                },
                {"$sort": {"_id": 1}},
            ]
        )
    )


def list_low_stock(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List active products at or below their available-stock threshold."""
    match = {
        "is_active": True,
        **_date_match("created_at", start, end),
        "is_low_stock": True,
    }
    pipeline = [
        {"$match": match},
        {"$sort": {"available_quantity": 1, "_id": 1}},
        {"$skip": skip},
        {"$limit": limit},
        {
            "$project": {
                "_id": 1,
                "sku": 1,
                "name": 1,
                "category": 1,
                "unit": 1,
                "quantity_on_hand": 1,
                "reserved_quantity": 1,
                "available_quantity": 1,
                "min_stock_level": 1,
            }
        },
    ]
    return list(database["products"].aggregate(pipeline)), count_documents(
        database,
        "products",
        match,
    )


def list_report_documents(
    database: Database[Any],
    collection_name: str,
    *,
    match: dict[str, Any],
    projection: dict[str, int],
    sort: dict[str, int],
    skip: int,
    limit: int,
    pipeline_stages: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """Return one projected page and a matching-document total."""
    pipeline = [
        {"$match": match},
        {"$sort": sort},
        {"$skip": skip},
        {"$limit": limit},
        *(pipeline_stages or []),
    ]
    pipeline.extend(
        [
            {"$project": projection},
        ]
    )
    return list(database[collection_name].aggregate(pipeline)), count_documents(
        database,
        collection_name,
        match,
    )


def list_employees(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List employees filtered by their joining date."""
    return list_report_documents(
        database,
        "employees",
        match=_date_match("joining_date", start, end),
        projection={
            "_id": 1,
            "employee_code": 1,
            "first_name": 1,
            "last_name": 1,
            "department_id": 1,
            "designation": 1,
            "joining_date": 1,
            "status": 1,
        },
        sort={"joining_date": -1, "_id": 1},
        skip=skip,
        limit=limit,
    )


def list_departments(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List departments with active and total employee counts."""
    lookup = [
        {
            "$lookup": {
                "from": "employees",
                "localField": "_id",
                "foreignField": "department_id",
                "as": "employees",
            }
        },
        {
            "$addFields": {
                "employee_count": {"$size": "$employees"},
                "active_employee_count": {
                    "$size": {
                        "$filter": {
                            "input": "$employees",
                            "as": "employee",
                            "cond": {"$eq": ["$$employee.status", "active"]},
                        }
                    }
                },
            }
        },
    ]
    return list_report_documents(
        database,
        "departments",
        match=_date_match("created_at", start, end),
        projection={
            "_id": 1,
            "code": 1,
            "name": 1,
            "description": 1,
            "is_active": 1,
            "employee_count": 1,
            "active_employee_count": 1,
        },
        sort={"created_at": -1, "_id": 1},
        skip=skip,
        limit=limit,
        pipeline_stages=lookup,
    )


def list_suppliers(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List suppliers in the requested creation-date window."""
    return list_report_documents(
        database,
        "suppliers",
        match=_date_match("created_at", start, end),
        projection={
            "_id": 1,
            "code": 1,
            "name": 1,
            "email": 1,
            "phone": 1,
            "status": 1,
            "created_at": 1,
        },
        sort={"created_at": -1, "_id": 1},
        skip=skip,
        limit=limit,
    )


def list_purchases(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    skip: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    """List purchase orders in the requested creation-date window."""
    return list_report_documents(
        database,
        "purchase_orders",
        match=_date_match("created_at", start, end),
        projection={
            "_id": 1,
            "po_number": 1,
            "supplier_snapshot": 1,
            "status": 1,
            "grand_total": 1,
            "created_at": 1,
            "updated_at": 1,
        },
        sort={"created_at": -1, "_id": 1},
        skip=skip,
        limit=limit,
    )


def purchase_statistics(database: Database[Any]) -> list[dict[str, Any]]:
    """Aggregate purchase-order counts and decimal totals by status."""
    return list(
        database["purchase_orders"].aggregate(
            [
                {
                    "$group": {
                        "_id": "$status",
                        "order_count": {"$sum": 1},
                        "grand_total": {"$sum": "$grand_total"},
                    }
                },
                {"$sort": {"_id": 1}},
            ],
            hint="ix_purchase_orders_status_total",
        )
    )


def recent_sales(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Return recent fulfilled sales with credit-note-adjusted totals."""
    pipeline = [
        {
            "$match": {
                "status": "fulfilled",
                **_date_match("fulfilled_at", start, end),
            }
        },
        {"$sort": {"fulfilled_at": -1, "_id": 1}},
        {"$limit": limit},
        {
            "$lookup": {
                "from": "sales_returns",
                "localField": "_id",
                "foreignField": "sales_order_id",
                "as": "returns",
            }
        },
        {
            "$addFields": {
                "net_total": {
                    "$subtract": [
                        "$grand_total",
                        {"$ifNull": [{"$sum": "$returns.total"}, Decimal128("0.00")]},
                    ]
                }
            }
        },
        {
            "$project": {
                "_id": 1,
                "order_number": 1,
                "customer_snapshot": 1,
                "fulfilled_at": 1,
                "net_total": 1,
                "status": 1,
            }
        },
    ]
    return list(database["sales_orders"].aggregate(pipeline))


def recent_purchases(
    database: Database[Any],
    *,
    start: datetime | None,
    end: datetime | None,
    limit: int,
) -> list[dict[str, Any]]:
    """Return recently updated purchase orders as purchase transactions."""
    return list(
        database["purchase_orders"].aggregate(
            [
                {"$match": _date_match("updated_at", start, end)},
                {"$sort": {"updated_at": -1, "_id": 1}},
                {"$limit": limit},
                {
                    "$project": {
                        "_id": 1,
                        "po_number": 1,
                        "supplier_snapshot": 1,
                        "updated_at": 1,
                        "grand_total": 1,
                        "status": 1,
                    }
                },
            ]
        )
    )
