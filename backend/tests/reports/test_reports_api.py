"""Seeded API tests for aggregation-based reports."""

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from pymongo.errors import OperationFailure
from rest_framework.test import APIClient

from accounts.tokens import create_access_token
from common.time import utc_now
from tests.accounts.fakes import FakeCollection, FakeDatabase


def _decimal(value):
    return value.to_decimal() if isinstance(value, Decimal128) else value


def _path(document, path):
    value = document
    for part in path.split("."):
        if isinstance(value, list):
            value = [item.get(part) for item in value if isinstance(item, dict)]
        elif isinstance(value, dict):
            value = value.get(part)
        else:
            return None
    return value


def _evaluate(expression, document, database, variables=None):
    variables = variables or {}
    if isinstance(expression, str):
        if expression.startswith("$$"):
            return _path(variables, expression[2:])
        if expression.startswith("$"):
            return _path(document, expression[1:])
        return expression
    if isinstance(expression, list):
        return [
            _evaluate(item, document, database, variables)
            for item in expression
        ]
    if not isinstance(expression, dict):
        return _decimal(expression)
    if "$subtract" in expression:
        left, right = _evaluate(expression["$subtract"], document, database, variables)
        return _decimal(left) - _decimal(right)
    if "$multiply" in expression:
        left, right = _evaluate(expression["$multiply"], document, database, variables)
        return _decimal(left) * _decimal(right)
    if "$sum" in expression:
        values = _evaluate(expression["$sum"], document, database, variables)
        if not isinstance(values, list):
            values = [values]
        return sum(_decimal(value or 0) for value in values)
    if "$ifNull" in expression:
        value, fallback = _evaluate(expression["$ifNull"], document, database, variables)
        return fallback if value is None else value
    if "$lte" in expression:
        left, right = _evaluate(expression["$lte"], document, database, variables)
        return left <= right
    if "$eq" in expression:
        left, right = _evaluate(expression["$eq"], document, database, variables)
        return left == right
    if "$cond" in expression:
        condition, yes, no = expression["$cond"]
        return _evaluate(
            yes if _evaluate(condition, document, database, variables) else no,
            document,
            database,
            variables,
        )
    if "$size" in expression:
        return len(_evaluate(expression["$size"], document, database, variables))
    if "$filter" in expression:
        spec = expression["$filter"]
        values = _evaluate(spec["input"], document, database, variables)
        filtered = []
        for value in values:
            nested_variables = {**variables, spec["as"]: value}
            if _evaluate(spec["cond"], document, database, nested_variables):
                filtered.append(value)
        return filtered
    if "$dateToString" in expression:
        spec = expression["$dateToString"]
        value = _evaluate(spec["date"], document, database, variables)
        return value.astimezone(ZoneInfo(spec["timezone"])).strftime("%Y-%m")
    return {
        key: _evaluate(value, document, database, variables)
        for key, value in expression.items()
    }


def _matches(document, query, database):
    for field, expected in query.items():
        if field == "$expr":
            if not _evaluate(expected, document, database):
                return False
            continue
        actual = _path(document, field)
        if isinstance(expected, dict):
            for operator, value in expected.items():
                if operator == "$in" and actual not in value:
                    return False
                if operator == "$nin" and actual in value:
                    return False
                if operator == "$gte" and not actual >= value:
                    return False
                if operator == "$lt" and not actual < value:
                    return False
                if operator == "$lte" and not actual <= value:
                    return False
        elif actual != expected:
            return False
    return True


class AggregateCollection(FakeCollection):
    """Run the small aggregation operator subset used by reports tests."""

    def __init__(self, database, name):
        super().__init__()
        self.database = database
        self.name = name

    def aggregate(self, pipeline, **kwargs):
        documents = [deepcopy(value) for value in self.documents.values()]
        for stage in pipeline:
            operator, specification = next(iter(stage.items()))
            if operator == "$match":
                documents = [
                    item
                    for item in documents
                    if _matches(item, specification, self.database)
                ]
            elif operator == "$lookup":
                foreign = self.database[specification["from"]]
                for item in documents:
                    local = _path(item, specification["localField"])
                    item[specification["as"]] = [
                        deepcopy(candidate)
                        for candidate in foreign.documents.values()
                        if _path(candidate, specification["foreignField"]) == local
                    ]
            elif operator == "$addFields":
                for item in documents:
                    for field, expression in specification.items():
                        item[field] = _evaluate(
                            expression,
                            item,
                            self.database,
                        )
            elif operator == "$group":
                grouped = {}
                for item in documents:
                    group_id = _evaluate(
                        specification["_id"],
                        item,
                        self.database,
                    )
                    group = grouped.setdefault(group_id, {"_id": group_id})
                    for field, accumulator in specification.items():
                        if field == "_id":
                            continue
                        amount = _evaluate(accumulator["$sum"], item, self.database)
                        group[field] = group.get(field, 0) + _decimal(amount)
                documents = list(grouped.values())
            elif operator == "$sort":
                for field, direction in reversed(list(specification.items())):
                    documents.sort(
                        key=lambda item: (_path(item, field) is None, _path(item, field)),
                        reverse=direction < 0,
                    )
            elif operator == "$skip":
                documents = documents[specification:]
            elif operator == "$limit":
                documents = documents[:specification]
            elif operator == "$project":
                projected = []
                for item in documents:
                    output = {}
                    if specification.get("_id", 1) and "_id" in item:
                        output["_id"] = item["_id"]
                    for field, include in specification.items():
                        if include and field != "_id" and field in item:
                            output[field] = item[field]
                    projected.append(output)
                documents = projected
            elif operator == "$count":
                documents = [{specification: len(documents)}] if documents else []
            else:
                raise AssertionError(f"Unsupported test aggregation stage: {operator}")
        return documents


class AggregateDatabase(FakeDatabase):
    """Isolated fake database with report aggregation support."""

    def __getitem__(self, collection_name):
        if collection_name not in self.collections:
            self.collections[collection_name] = AggregateCollection(
                self,
                collection_name,
            )
        return self.collections[collection_name]


@pytest.fixture
def reports_api(monkeypatch):
    database = AggregateDatabase()
    monkeypatch.setattr(settings, "JWT_SECRET_KEY", "reports-test-secret-key-at-least-32-bytes")
    monkeypatch.setattr(settings, "JWT_ISSUER", "reports-test")
    monkeypatch.setattr(settings, "JWT_AUDIENCE", "reports-test-client")

    class FakeMongoClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def __getitem__(self, database_name):
            return database

    monkeypatch.setattr(
        "accounts.authentication.MongoClient",
        lambda *args, **kwargs: FakeMongoClient(),
    )

    @contextmanager
    def fake_reports_database():
        yield database

    monkeypatch.setattr("reports.views.mongo_database", fake_reports_database)
    return database


@pytest.fixture
def client():
    return APIClient()


def add_user(database, role):
    now = utc_now()
    user = {
        "_id": ObjectId(),
        "email": f"{uuid4().hex}@example.test",
        "password_hash": "not-used",
        "full_name": "Reports Test User",
        "role": role,
        "is_active": True,
        "token_version": 0,
        "employee_id": None,
        "last_login_at": None,
        "created_at": now,
        "updated_at": now,
    }
    database["users"].insert_one(user)
    return user


def headers(user):
    return {"HTTP_AUTHORIZATION": f"Bearer {create_access_token(user)}"}


def seed_data(database, *, include_current_month_sale=False):
    """Insert exact, small datasets for report calculations."""
    local_zone = ZoneInfo("Asia/Kolkata")
    march_fulfilled = datetime(2026, 3, 10, 12, tzinfo=local_zone).astimezone(timezone.utc)
    april_fulfilled = datetime(2026, 4, 5, 12, tzinfo=local_zone).astimezone(timezone.utc)
    customer_id = ObjectId()
    supplier_id = ObjectId()
    department_id = ObjectId()
    march_order_id = ObjectId()
    april_order_id = ObjectId()
    now = utc_now()
    database["employees"].insert_one({
        "_id": ObjectId(), "employee_code": "EMP-1", "first_name": "Ada",
        "last_name": "Lovelace", "department_id": department_id,
        "designation": "Engineer", "joining_date": march_fulfilled,
        "status": "active", "created_at": now,
    })
    database["employees"].insert_one({
        "_id": ObjectId(), "employee_code": "EMP-2", "first_name": "Grace",
        "last_name": "Hopper", "department_id": department_id,
        "designation": "Engineer", "joining_date": march_fulfilled,
        "status": "inactive", "created_at": now,
    })
    database["departments"].insert_one({
        "_id": department_id, "code": "OPS", "name": "Operations",
        "name_search": "operations", "is_active": True, "created_at": march_fulfilled,
        "updated_at": now,
    })
    database["products"].insert_one({
        "_id": ObjectId(), "sku": "STOCK-1", "name": "Available",
        "category": "Tools", "unit": "each", "quantity_on_hand": 10,
        "reserved_quantity": 2, "min_stock_level": 3,
        "cost_price": Decimal128("2.50"), "is_active": True,
        "created_at": now,
    })
    database["products"].insert_one({
        "_id": ObjectId(), "sku": "STOCK-2", "name": "Low",
        "category": "Tools", "unit": "each", "quantity_on_hand": 4,
        "reserved_quantity": 1, "min_stock_level": 3,
        "cost_price": Decimal128("5.00"), "is_active": True,
        "created_at": now,
    })
    database["products"].insert_one({
        "_id": ObjectId(), "sku": "STOCK-3", "name": "Inactive",
        "category": "Tools", "unit": "each", "quantity_on_hand": 1,
        "reserved_quantity": 0, "min_stock_level": 5,
        "cost_price": Decimal128("100.00"), "is_active": False,
        "created_at": now,
    })
    database["suppliers"].insert_one({
        "_id": supplier_id, "code": "SUP-1", "name": "Acme Supply",
        "name_search": "acme supply", "status": "active", "created_at": now,
        "updated_at": now,
    })
    database["customers"].insert_one({
        "_id": customer_id, "code": "CUS-1", "name": "Acme Customer",
        "name_search": "acme customer", "status": "active", "created_at": now,
    })
    database["purchase_orders"].insert_one({
        "_id": ObjectId(), "po_number": "PO-1", "supplier_id": supplier_id,
        "supplier_snapshot": {"name": "Acme Supply"}, "status": "approved",
        "grand_total": Decimal128("50.00"), "created_at": march_fulfilled,
        "updated_at": march_fulfilled,
    })
    database["purchase_orders"].insert_one({
        "_id": ObjectId(), "po_number": "PO-2", "supplier_id": supplier_id,
        "supplier_snapshot": {"name": "Acme Supply"}, "status": "received",
        "grand_total": Decimal128("20.00"), "created_at": april_fulfilled,
        "updated_at": april_fulfilled,
    })
    for order_id, number, fulfilled_at, amount in (
        (march_order_id, "SO-MAR", march_fulfilled, "100.00"),
        (april_order_id, "SO-APR", april_fulfilled, "40.00"),
    ):
        database["sales_orders"].insert_one({
            "_id": order_id, "order_number": number, "customer_id": customer_id,
            "customer_snapshot": {"name": "Acme Customer"}, "status": "fulfilled",
            "fulfilled_at": fulfilled_at, "grand_total": Decimal128(amount),
            "created_at": fulfilled_at,
        })
    database["sales_orders"].insert_one({
        "_id": ObjectId(), "order_number": "SO-OUTSIDE",
        "customer_snapshot": {"name": "Acme Customer"}, "status": "fulfilled",
        "fulfilled_at": datetime(2026, 2, 28, 18, 29, 59, 999000, timezone.utc),
        "grand_total": Decimal128("999.00"),
        "created_at": now,
    })
    if include_current_month_sale:
        current_fulfilled = datetime.now(timezone.utc)
        database["sales_orders"].insert_one({
            "_id": ObjectId(), "order_number": "SO-CURRENT",
            "customer_snapshot": {"name": "Acme Customer"}, "status": "fulfilled",
            "fulfilled_at": current_fulfilled,
            "grand_total": Decimal128("10.00"),
            "created_at": current_fulfilled,
        })
    database["sales_orders"].insert_one({
        "_id": ObjectId(), "order_number": "SO-DRAFT",
        "customer_snapshot": {"name": "Acme Customer"}, "status": "draft",
        "fulfilled_at": None, "grand_total": Decimal128("900.00"),
        "created_at": now,
    })
    database["sales_returns"].insert_one({
        "_id": ObjectId(), "credit_note_number": "CN-1",
        "sales_order_id": march_order_id, "customer_id": customer_id,
        "total": Decimal128("20.00"), "created_at": april_fulfilled,
    })
    return {
        "department_id": department_id,
        "march_order_id": march_order_id,
        "april_order_id": april_order_id,
    }


def test_sales_and_monthly_sales_are_fulfilled_only_and_net_of_returns(
    reports_api,
    client,
):
    seed_data(reports_api)
    user = add_user(reports_api, "sales_manager")
    sales = client.get(
        "/api/reports/sales/?date_from=2026-03-01&date_to=2026-04-30",
        **headers(user),
    )
    monthly = client.get(
        "/api/reports/monthly-sales/?date_from=2026-03-01&date_to=2026-04-30",
        **headers(user),
    )

    assert sales.status_code == 200
    assert sales.json()["meta"]["total"] == 2
    assert {
        item["order_number"]: item["net_total"]
        for item in sales.json()["data"]["sales"]
    } == {"SO-MAR": "80.00", "SO-APR": "40.00"}
    assert monthly.status_code == 200
    assert monthly.json()["data"]["monthly_sales"] == [
        {
            "month": "2026-03",
            "order_count": 1,
            "gross_sales": "100.00",
            "returns_total": "20.00",
            "net_sales": "80.00",
        },
        {
            "month": "2026-04",
            "order_count": 1,
            "gross_sales": "40.00",
            "returns_total": "0.00",
            "net_sales": "40.00",
        },
    ]


def test_inventory_low_stock_and_dashboard_widget_permissions(reports_api, client):
    seed_data(reports_api)
    user = add_user(reports_api, "inventory_manager")
    inventory = client.get("/api/reports/inventory/", **headers(user))
    low_stock = client.get(
        "/api/reports/low-stock/?page=1&page_size=1",
        **headers(user),
    )
    dashboard = client.get("/api/reports/dashboard/", **headers(user))
    data = dashboard.json()["data"]["dashboard"]

    assert inventory.json()["data"]["inventory"] == {
        "active_products": 2,
        "quantity_on_hand": 14,
        "reserved_quantity": 3,
        "available_quantity": 11,
        "low_stock_count": 1,
        "stock_cost_value": "45.00",
    }
    assert low_stock.status_code == 200
    assert low_stock.json()["meta"]["total"] == 1
    assert low_stock.json()["data"]["low_stock"][0]["sku"] == "STOCK-2"
    assert "inventory_statistics" in data
    assert data["inventory_by_category"] == [
        {
            "category": "Tools",
            "product_count": 2,
            "available_quantity": 11,
            "stock_cost_value": "45.00",
        }
    ]
    assert len(data["low_stock_products"]) == 1
    assert data["low_stock_products"][0]["sku"] == "STOCK-2"
    assert "pending_purchase_orders" in data
    assert "sales_chart" in data
    assert "total_customers" not in data
    assert "purchase_statistics" in data


def test_resource_reports_and_dashboard_return_seeded_totals(reports_api, client):
    seed_data(reports_api, include_current_month_sale=True)
    user = add_user(reports_api, "super_admin")
    date_range = "date_from=2026-03-01&date_to=2026-04-30"

    employees = client.get(
        f"/api/reports/employees/?{date_range}",
        **headers(user),
    )
    departments = client.get(
        f"/api/reports/departments/?{date_range}",
        **headers(user),
    )
    suppliers = client.get(
        f"/api/reports/suppliers/?{date_range}",
        **headers(user),
    )
    purchases = client.get(
        f"/api/reports/purchases/?{date_range}",
        **headers(user),
    )
    dashboard = client.get("/api/reports/dashboard/", **headers(user))

    assert employees.status_code == departments.status_code == 200
    assert employees.json()["meta"]["total"] == 2
    assert departments.json()["data"]["departments"][0]["employee_count"] == 2
    assert departments.json()["data"]["departments"][0]["active_employee_count"] == 1
    assert suppliers.json()["meta"]["total"] == 0
    assert purchases.json()["meta"]["total"] == 2
    widgets = dashboard.json()["data"]["dashboard"]
    assert widgets["total_employees"] == 1
    assert widgets["total_departments"] == 1
    assert widgets["total_products"] == 2
    assert widgets["low_stock_count"] == 1
    assert widgets["total_suppliers"] == 1
    assert widgets["total_customers"] == 1
    assert widgets["pending_purchase_orders"] == 1
    assert widgets["purchase_statistics"] == {
        "status_breakdown": {
            "approved": {"order_count": 1, "grand_total": "50.00"},
            "received": {"order_count": 1, "grand_total": "20.00"},
        },
        "pending_order_count": 1,
        "grand_total": "70.00",
    }
    assert widgets["monthly_sales"]["order_count"] == 1
    assert widgets["monthly_sales"]["gross_sales"] == "10.00"
    assert widgets["monthly_sales"]["net_sales"] == "10.00"
    current_month = datetime.now(timezone.utc).astimezone(
        ZoneInfo("Asia/Kolkata")
    ).strftime("%Y-%m")
    assert next(
        month for month in widgets["sales_chart"] if month["month"] == current_month
    )["net_sales"] == "10.00"
    chart_months = {month["month"]: month for month in widgets["purchases_vs_sales"]}
    assert chart_months["2026-03"]["net_sales"] == "80.00"
    assert chart_months["2026-03"]["purchase_total"] == "50.00"
    assert chart_months["2026-04"]["net_sales"] == "40.00"
    assert chart_months["2026-04"]["purchase_total"] == "20.00"
    assert len(widgets["recent_transactions"]) >= 4
    assert {item["type"] for item in widgets["recent_transactions"]} == {
        "purchase",
        "sale",
    }


def test_dashboard_hides_unpermitted_widgets_and_empty_reports_are_zero_filled(
    reports_api,
    client,
):
    hr_user = add_user(reports_api, "hr_manager")
    dashboard = client.get("/api/reports/dashboard/", **headers(hr_user))
    assert dashboard.status_code == 200
    widgets = dashboard.json()["data"]["dashboard"]
    assert "total_employees" in widgets
    assert "total_departments" in widgets
    assert "sales_chart" not in widgets
    assert "purchase_statistics" not in widgets
    assert "total_suppliers" not in widgets

    sales_user = add_user(reports_api, "sales_manager")
    sales = client.get("/api/reports/sales/", **headers(sales_user))
    monthly = client.get(
        "/api/reports/monthly-sales/?date_from=2026-01-01&date_to=2026-02-28",
        **headers(sales_user),
    )
    inventory = client.get("/api/reports/inventory/", **headers(sales_user))
    assert sales.status_code == 200
    assert sales.json()["data"]["sales"] == []
    assert sales.json()["meta"]["total"] == 0
    assert monthly.json()["data"]["monthly_sales"] == [
        {
            "month": "2026-01",
            "order_count": 0,
            "gross_sales": "0.00",
            "returns_total": "0.00",
            "net_sales": "0.00",
        },
        {
            "month": "2026-02",
            "order_count": 0,
            "gross_sales": "0.00",
            "returns_total": "0.00",
            "net_sales": "0.00",
        },
    ]
    assert inventory.status_code == 200
    assert inventory.json()["data"]["inventory"] == {
        "active_products": 0,
        "quantity_on_hand": 0,
        "reserved_quantity": 0,
        "available_quantity": 0,
        "low_stock_count": 0,
        "stock_cost_value": "0.00",
    }


def test_report_date_validation_and_endpoint_permissions(reports_api, client):
    employee = add_user(reports_api, "employee")
    sales_manager = add_user(reports_api, "sales_manager")
    assert client.get("/api/reports/dashboard/", **headers(employee)).status_code == 403
    assert client.get("/api/reports/purchases/", **headers(sales_manager)).status_code == 403
    invalid_date = client.get(
        "/api/reports/sales/?date_from=not-a-date",
        **headers(sales_manager),
    )
    reversed_dates = client.get(
        "/api/reports/sales/?date_from=2026-04-02&date_to=2026-04-01",
        **headers(sales_manager),
    )
    unsafe = client.get(
        "/api/reports/sales/?$where=true",
        **headers(sales_manager),
    )
    assert invalid_date.status_code == 400
    assert reversed_dates.status_code == 400
    assert unsafe.status_code == 400


def test_dashboard_keeps_other_widgets_when_one_aggregation_fails(
    reports_api,
    client,
    monkeypatch,
):
    seed_data(reports_api)
    user = add_user(reports_api, "inventory_manager")

    def fail_category_aggregation(database):
        raise OperationFailure("private database detail", 123)

    monkeypatch.setattr(
        "reports.services.repository.inventory_by_category",
        fail_category_aggregation,
    )
    response = client.get("/api/reports/dashboard/", **headers(user))

    dashboard = response.json()["data"]["dashboard"]
    assert response.status_code == 200
    assert dashboard["total_products"] == 2
    assert dashboard["low_stock_count"] == 1
    assert dashboard["low_stock_products"][0]["sku"] == "STOCK-2"
    assert "inventory_by_category" not in dashboard
    assert dashboard["widget_errors"]["inventory_by_category"] == {
        "code": "widget_unavailable",
        "message": "This dashboard widget could not be loaded.",
    }
    assert "private database detail" not in response.content.decode()
