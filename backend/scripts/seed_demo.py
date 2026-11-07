"""Seed and explain a local, synthetic SmartERP performance workload."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import os
from pathlib import Path
import re
import sys
from typing import Any

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django
from bson import ObjectId
from bson.decimal128 import Decimal128
from django.conf import settings
from faker import Faker
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.uri_parser import parse_uri

django.setup()

from common.time import utc_now  # noqa: E402
from common.management.commands.init_db import initialize_database  # noqa: E402
from database.indexes import COLLECTIONS  # noqa: E402
from reports.repository import PENDING_PURCHASE_STATUSES  # noqa: E402

DEFAULT_DATABASE = "smarterp_perf_demo"
DEMO_DATABASE_PATTERN = re.compile(r"^smarterp_perf_[a-z0-9_]+$")
PAGE_SIZE = 20


def _arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Seed an isolated local MongoDB demo database with fake records, "
            "then report explain(executionStats) for representative list and "
            "report query shapes."
        )
    )
    parser.add_argument("--database", default=DEFAULT_DATABASE)
    parser.add_argument("--records", type=int, default=10_000)
    parser.add_argument(
        "--explain-only",
        action="store_true",
        help="Explain existing seeded data without inserting documents.",
    )
    return parser.parse_args()


def _connect(database_name: str) -> tuple[MongoClient[dict[str, Any]], Database[Any]]:
    if settings.SMARTERP_ENV != "development":
        raise SystemExit("Refusing to run unless SMARTERP_ENV=development.")
    if not DEMO_DATABASE_PATTERN.fullmatch(database_name):
        raise SystemExit("Database name must start with smarterp_perf_.")
    mongo_uri = settings.MONGO_URI
    if not mongo_uri:
        raise SystemExit("MONGO_URI is not configured.")
    hosts = parse_uri(mongo_uri).get("nodelist") or []
    if not hosts or any(host not in {"localhost", "127.0.0.1", "::1"} for host, _ in hosts):
        raise SystemExit("Refusing to seed a MongoDB URI that is not local-only.")

    client: MongoClient[dict[str, Any]] = MongoClient(
        mongo_uri,
        serverSelectionTimeoutMS=5000,
    )
    hello = client.admin.command("hello")
    if not hello.get("setName") or not hello.get("isWritablePrimary"):
        client.close()
        raise SystemExit("A writable MongoDB replica-set primary is required.")
    return client, client[database_name]


def _demo_documents(
    collection_name: str,
    count: int,
    *,
    faker: Faker,
    department_ids: list[ObjectId],
    product_ids: list[ObjectId],
    supplier_ids: list[ObjectId],
    customer_ids: list[ObjectId],
    user_id: ObjectId,
    now: datetime,
) -> list[dict[str, Any]]:
    docs: list[dict[str, Any]] = []
    for index in range(count):
        created_at = now - timedelta(days=index % 730, minutes=index % 1440)
        amount = Decimal128(Decimal("25.50") + Decimal(index % 1000))
        if collection_name == "users":
            document = {
                "email": f"demo-user-{index:06d}@example.invalid",
                "password_hash": "synthetic-not-a-usable-password-hash",
                "full_name": faker.name(),
                "role": ("sales_manager", "inventory_manager", "employee")[index % 3],
                "is_active": index % 7 != 0,
                "token_version": 0,
                "last_login_at": created_at,
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "employees":
            first_name = faker.first_name()
            last_name = faker.last_name()
            document = {
                "employee_code": f"DEMO-EMP-{index:06d}",
                "first_name": first_name,
                "last_name": last_name,
                "name_search": f"{first_name} {last_name}".casefold(),
                "email": f"demo-employee-{index:06d}@example.invalid",
                "phone": None,
                "department_id": department_ids[index % len(department_ids)],
                "designation": ("Analyst", "Coordinator", "Associate")[index % 3],
                "joining_date": created_at,
                "status": ("active", "inactive", "on_leave")[index % 3],
                "created_at": created_at,
                "updated_at": created_at,
                "deactivated_at": None,
            }
        elif collection_name == "departments":
            name = f"{faker.bs().title()} {index}"
            document = {
                "code": f"DEMO-DEPT-{index:06d}",
                "name": name,
                "name_search": name.casefold(),
                "description": faker.sentence(),
                "manager_employee_id": None,
                "is_active": index % 5 != 0,
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "customers":
            name = faker.company()
            document = {
                "code": f"DEMO-CUST-{index:06d}",
                "name": name,
                "name_search": name.casefold(),
                "email": f"demo-customer-{index:06d}@example.invalid",
                "phone": faker.phone_number(),
                "tax_id": None,
                "billing_address": None,
                "shipping_address": None,
                "credit_limit": amount,
                "status": "active" if index % 8 else "inactive",
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "suppliers":
            name = faker.company()
            document = {
                "code": f"DEMO-SUP-{index:06d}",
                "name": name,
                "name_search": name.casefold(),
                "contact_person": faker.name(),
                "email": f"demo-supplier-{index:06d}@example.invalid",
                "phone": faker.phone_number(),
                "address": None,
                "status": "active" if index % 8 else "inactive",
                "payment_terms": "Net 30",
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "products":
            quantity = 2 if index % 5 == 0 else 30 + index % 500
            name = f"{faker.word().title()} Demo Product {index}"
            document = {
                "sku": f"DEMO-SKU-{index:06d}",
                "name": name,
                "name_search": name.casefold(),
                "description": "Synthetic performance-test product.",
                "category": f"Demo Category {index % 20:02d}",
                "unit": "each",
                "cost_price": amount,
                "selling_price": Decimal128(Decimal("50.00") + Decimal(index % 1000)),
                "quantity_on_hand": quantity,
                "reserved_quantity": 0,
                "min_stock_level": 5,
                "available_quantity": quantity,
                "is_low_stock": quantity <= 5,
                "is_active": index % 10 != 0,
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "stock_movements":
            quantity = 1 + index % 20
            document = {
                "product_id": product_ids[index % len(product_ids)],
                "movement_type": "adjustment",
                "quantity_change": quantity,
                "reserved_change": 0,
                "quantity_before": quantity,
                "quantity_after": quantity * 2,
                "reason": "Synthetic performance-test movement.",
                "reference_type": "demo",
                "reference_id": ObjectId(),
                "performed_by": user_id,
                "created_at": created_at,
            }
        elif collection_name == "purchase_orders":
            supplier_id = supplier_ids[index % len(supplier_ids)]
            status = (
                "approved",
                "partially_received",
                "pending_approval",
                "draft",
            )[index % 4]
            document = {
                "po_number": f"DEMO-PO-{index:06d}",
                "supplier_id": supplier_id,
                "supplier_snapshot": {
                    "code": f"DEMO-SUP-{index % len(supplier_ids):06d}",
                    "name": f"Demo Supplier {index % len(supplier_ids)}",
                    "email": None,
                },
                "items": [
                    {
                        "product_id": product_ids[index % len(product_ids)],
                        "sku": f"DEMO-SKU-{index % len(product_ids):06d}",
                        "name": f"Demo Product {index % len(product_ids)}",
                        "quantity_ordered": 10,
                        "quantity_received": 0,
                        "unit_cost": amount,
                        "line_total": amount,
                    }
                ],
                "tax_rate": Decimal128("0.00"),
                "subtotal": amount,
                "tax_total": Decimal128("0.00"),
                "grand_total": amount,
                "status": status,
                "status_history": [
                    {"status": status, "by": user_id, "at": created_at, "note": None}
                ],
                "created_by": user_id,
                "approved_by": user_id if status == "approved" else None,
                "created_at": created_at,
                "updated_at": created_at,
            }
        elif collection_name == "sales_orders":
            customer_id = customer_ids[index % len(customer_ids)]
            status = ("fulfilled", "confirmed", "draft", "cancelled")[index % 4]
            document = {
                "order_number": f"DEMO-SO-{index:06d}",
                "customer_id": customer_id,
                "customer_snapshot": {
                    "code": f"DEMO-CUST-{index % len(customer_ids):06d}",
                    "name": f"Demo Customer {index % len(customer_ids)}",
                    "email": None,
                    "billing_address": None,
                    "shipping_address": None,
                },
                "items": [
                    {
                        "product_id": product_ids[index % len(product_ids)],
                        "sku": f"DEMO-SKU-{index % len(product_ids):06d}",
                        "name": f"Demo Product {index % len(product_ids)}",
                        "quantity": 1,
                        "unit_price": amount,
                        "discount_percent": Decimal128("0.00"),
                        "tax_percent": Decimal128("0.00"),
                        "line_subtotal": amount,
                        "line_tax": Decimal128("0.00"),
                        "line_total": amount,
                        "returned_quantity": 0,
                    }
                ],
                "subtotal": amount,
                "discount_total": Decimal128("0.00"),
                "tax_total": Decimal128("0.00"),
                "grand_total": amount,
                "status": status,
                "return_status": "none",
                "payment_status": ("unpaid", "partial", "paid")[index % 3],
                "paid_total": Decimal128("0.00"),
                "created_by": user_id,
                "created_at": created_at,
                "updated_at": created_at,
                "fulfilled_at": created_at if status == "fulfilled" else None,
                "status_history": [
                    {"status": status, "by": user_id, "at": created_at, "note": None}
                ],
            }
        elif collection_name == "payments":
            order_id = ObjectId()
            document = {
                "sales_order_id": order_id,
                "customer_id": customer_ids[index % len(customer_ids)],
                "payment_reference": f"DEMO-PAY-{index:06d}",
                "amount": amount,
                "method": ("cash", "bank_transfer", "card", "other")[index % 4],
                "status": "completed",
                "received_at": created_at,
                "created_by": user_id,
                "created_at": created_at,
            }
        elif collection_name == "invoices":
            document = {
                "invoice_number": f"DEMO-INV-{index:06d}",
                "sales_order_id": ObjectId(),
                "customer_id": customer_ids[index % len(customer_ids)],
                "customer_snapshot": {
                    "code": f"DEMO-CUST-{index % len(customer_ids):06d}",
                    "name": f"Demo Customer {index % len(customer_ids)}",
                    "email": None,
                    "billing_address": None,
                    "shipping_address": None,
                },
                "items": [
                    {
                        "product_id": product_ids[index % len(product_ids)],
                        "sku": f"DEMO-SKU-{index % len(product_ids):06d}",
                        "name": f"Demo Product {index % len(product_ids)}",
                        "quantity": 1,
                        "unit_price": amount,
                        "discount_percent": Decimal128("0.00"),
                        "tax_percent": Decimal128("0.00"),
                        "line_subtotal": amount,
                        "line_tax": Decimal128("0.00"),
                        "line_total": amount,
                    }
                ],
                "subtotal": amount,
                "discount_total": Decimal128("0.00"),
                "tax_total": Decimal128("0.00"),
                "grand_total": amount,
                "issued_at": created_at,
                "due_date": created_at + timedelta(days=30),
                "created_at": created_at,
            }
        elif collection_name == "sales_returns":
            document = {
                "credit_note_number": f"DEMO-CN-{index:06d}",
                "sales_order_id": ObjectId(),
                "customer_id": customer_ids[index % len(customer_ids)],
                "customer_snapshot": {
                    "code": f"DEMO-CUST-{index % len(customer_ids):06d}",
                    "name": f"Demo Customer {index % len(customer_ids)}",
                    "email": None,
                    "billing_address": None,
                    "shipping_address": None,
                },
                "items": [
                    {
                        "product_id": product_ids[index % len(product_ids)],
                        "sku": f"DEMO-SKU-{index % len(product_ids):06d}",
                        "name": f"Demo Product {index % len(product_ids)}",
                        "quantity": 1,
                        "unit_price": amount,
                        "discount_percent": Decimal128("0.00"),
                        "tax_percent": Decimal128("0.00"),
                        "line_subtotal": amount,
                        "line_discount": Decimal128("0.00"),
                        "line_tax": Decimal128("0.00"),
                        "line_total": amount,
                    }
                ],
                "subtotal": amount,
                "discount_total": Decimal128("0.00"),
                "tax_total": Decimal128("0.00"),
                "total": amount,
                "reason": "Synthetic performance-test return.",
                "created_by": user_id,
                "created_at": created_at,
            }
        elif collection_name == "audit_logs":
            document = {
                "actor_id": user_id,
                "action": "demo.seed",
                "entity_type": "performance_demo",
                "entity_id": str(ObjectId()),
                "request_id": None,
                "before": None,
                "after": None,
                "created_at": created_at,
            }
        else:
            continue
        docs.append(document)
    return docs


def _seed(database: Database[Any], records: int) -> None:
    faker = Faker()
    faker.seed_instance(20261107)
    now = utc_now()
    per_supporting_collection = min(records, 1_000)
    user_id = ObjectId()

    # Seed parents first; child records use these generated IDs.
    users = _demo_documents(
        "users", per_supporting_collection, faker=faker, department_ids=[],
        product_ids=[], supplier_ids=[], customer_ids=[], user_id=user_id, now=now,
    )
    users[0]["_id"] = user_id
    database["users"].insert_many(users, ordered=False)
    department_docs = _demo_documents(
        "departments", per_supporting_collection, faker=faker, department_ids=[],
        product_ids=[], supplier_ids=[], customer_ids=[], user_id=user_id, now=now,
    )
    department_ids = database["departments"].insert_many(
        department_docs, ordered=False
    ).inserted_ids
    product_docs = _demo_documents(
        "products", records, faker=faker, department_ids=department_ids,
        product_ids=[], supplier_ids=[], customer_ids=[], user_id=user_id, now=now,
    )
    product_ids = database["products"].insert_many(
        product_docs, ordered=False
    ).inserted_ids
    supplier_docs = _demo_documents(
        "suppliers", per_supporting_collection, faker=faker, department_ids=department_ids,
        product_ids=product_ids, supplier_ids=[], customer_ids=[], user_id=user_id, now=now,
    )
    supplier_ids = database["suppliers"].insert_many(
        supplier_docs, ordered=False
    ).inserted_ids
    customer_docs = _demo_documents(
        "customers", per_supporting_collection, faker=faker, department_ids=department_ids,
        product_ids=product_ids, supplier_ids=supplier_ids, customer_ids=[], user_id=user_id, now=now,
    )
    customer_ids = database["customers"].insert_many(
        customer_docs, ordered=False
    ).inserted_ids

    for name in (
        "employees",
        "stock_movements",
        "purchase_orders",
        "sales_orders",
        "payments",
        "invoices",
        "sales_returns",
        "audit_logs",
    ):
        count = records if name in {"purchase_orders", "sales_orders"} else per_supporting_collection
        documents = _demo_documents(
            name,
            count,
            faker=faker,
            department_ids=list(department_ids),
            product_ids=list(product_ids),
            supplier_ids=list(supplier_ids),
            customer_ids=list(customer_ids),
            user_id=user_id,
            now=now,
        )
        if documents:
            database[name].insert_many(documents, ordered=False)


def _walk(value: Any):
    if isinstance(value, dict):
        yield value
        for key, child in value.items():
            if key != "rejectedPlans":
                yield from _walk(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk(child)


def _plan_summary(explain: dict[str, Any]) -> dict[str, Any]:
    plan_nodes = [node for node in _walk(explain) if "rejectedPlans" not in node]
    stages = {
        node["stage"]
        for node in plan_nodes
        if isinstance(node.get("stage"), str)
    }
    indexes = {
        node["indexName"]
        for node in plan_nodes
        if isinstance(node.get("indexName"), str)
    }
    indexes.update(
        index_name
        for node in plan_nodes
        for index_name in node.get("indexesUsed", [])
        if isinstance(index_name, str)
    )
    stats_candidates = [
        node
        for node in plan_nodes
        if "totalDocsExamined" in node and "totalKeysExamined" in node
    ]
    stats = max(
        stats_candidates,
        key=lambda node: node.get("totalDocsExamined", 0),
        default={},
    )
    pipeline_stages = explain.get("stages", [])
    output_count = (
        pipeline_stages[-1].get("nReturned")
        if pipeline_stages and isinstance(pipeline_stages[-1], dict)
        else None
    )
    return {
        "stages": stages,
        "indexes": sorted(indexes),
        "n_returned": output_count if output_count is not None else stats.get("nReturned", 0),
        "docs_examined": stats.get("totalDocsExamined", 0),
        "keys_examined": stats.get("totalKeysExamined", 0),
    }


def _explain_find(
    database: Database[Any],
    name: str,
    collection: str,
    query: dict[str, Any],
    sort: list[tuple[str, int]],
    *,
    limit: int = PAGE_SIZE,
    related_collections: tuple[str, ...] = (),
) -> tuple[str, dict[str, Any]]:
    explain = database.command(
        "explain",
        {
            "find": collection,
            "filter": query,
            "sort": dict(sort),
            "limit": limit,
        },
        verbosity="executionStats",
    )
    summary = _plan_summary(explain)
    summary["collection"] = collection
    summary["related_collections"] = related_collections
    return name, summary


def _explain_aggregate(
    database: Database[Any],
    name: str,
    collection: str,
    pipeline: list[dict[str, Any]],
    *,
    related_collections: tuple[str, ...] = (),
    hint: str | None = None,
) -> tuple[str, dict[str, Any]]:
    command = {
        "aggregate": collection,
        "pipeline": pipeline,
        "cursor": {},
    }
    if hint is not None:
        command["hint"] = hint
    explain = database.command(
        "explain",
        command,
        verbosity="executionStats",
    )
    summary = _plan_summary(explain)
    summary["collection"] = collection
    summary["related_collections"] = related_collections
    return name, summary


def _explain_count(
    database: Database[Any],
    name: str,
    collection: str,
    query: dict[str, Any],
) -> tuple[str, dict[str, Any]]:
    return _explain_aggregate(
        database,
        name,
        collection,
        [{"$match": query}, {"$count": "count"}],
        hint="_id_" if not query else None,
    )


def _explain_distinct(
    database: Database[Any],
    name: str,
    collection: str,
    field: str,
) -> tuple[str, dict[str, Any]]:
    explain = database.command(
        "explain",
        {"distinct": collection, "key": field},
        verbosity="executionStats",
    )
    summary = _plan_summary(explain)
    summary["collection"] = collection
    summary["related_collections"] = ()
    return name, summary


def _explain_cases(database: Database[Any]) -> list[tuple[str, dict[str, Any]]]:
    now = utc_now()
    start = now - timedelta(days=730)
    end = now + timedelta(days=1)
    chart_start = now - timedelta(days=365)
    first_department = database["departments"].find_one({}, {"_id": 1})["_id"]
    first_customer = database["customers"].find_one({}, {"_id": 1})["_id"]
    first_supplier = database["suppliers"].find_one({}, {"_id": 1})["_id"]
    fulfilled_sales = {"status": "fulfilled"}
    active_products = {"is_active": True}
    active_low_stock = {"is_active": True, "is_low_stock": True}
    purchase_window = {"created_at": {"$gte": chart_start, "$lt": end}}
    purchase_month_pipeline = [
        {
            "$match": {
                **purchase_window,
                "status": {"$nin": ["draft", "rejected", "cancelled"]},
            }
        },
        {
            "$addFields": {
                "month": {
                    "$dateToString": {
                        "format": "%Y-%m",
                        "date": "$created_at",
                        "timezone": settings.BUSINESS_TIMEZONE,
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
    inventory_statistics_pipeline = [
        {"$match": active_products},
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
                        "$multiply": ["$cost_price", "$quantity_on_hand"]
                    }
                },
            }
        },
    ]
    inventory_by_category_pipeline = [
        {"$match": active_products},
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
                        "$multiply": ["$cost_price", "$quantity_on_hand"]
                    }
                },
            }
        },
    ]
    cases = [
        _explain_find(database, "GET /api/users/ page", "users", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/users/ total", "users", {}),
        _explain_find(database, "GET /api/audit-logs/ page", "audit_logs", {}, [("created_at", -1), ("_id", -1)]),
        _explain_count(database, "GET /api/audit-logs/ total", "audit_logs", {}),
        _explain_find(database, "GET /api/departments/ page", "departments", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/departments/ total", "departments", {}),
        _explain_find(database, "GET /api/departments/{id}/employees/ page", "employees", {"department_id": first_department}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/departments/{id}/employees/ total", "employees", {"department_id": first_department}),
        _explain_find(database, "GET /api/employees/ page", "employees", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/employees/ total", "employees", {}),
        _explain_distinct(database, "GET /api/employees/designations/", "employees", "designation"),
        _explain_find(database, "GET /api/customers/ page", "customers", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/customers/ total", "customers", {}),
        _explain_find(database, "GET /api/customers/{id}/sales-orders/ page", "sales_orders", {"customer_id": first_customer}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/customers/{id}/sales-orders/ total", "sales_orders", {"customer_id": first_customer}),
        _explain_find(database, "GET /api/suppliers/ page", "suppliers", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/suppliers/ total", "suppliers", {}),
        _explain_find(database, "GET /api/suppliers/{id}/purchase-orders/ page", "purchase_orders", {"supplier_id": first_supplier}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/suppliers/{id}/purchase-orders/ total", "purchase_orders", {"supplier_id": first_supplier}),
        _explain_find(database, "GET /api/products/ page", "products", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/products/ total", "products", {}),
        _explain_find(database, "GET /api/products/low-stock/ page", "products", {"is_low_stock": True}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/products/low-stock/ total", "products", {"is_low_stock": True}),
        _explain_distinct(database, "GET /api/products/categories/", "products", "category"),
        _explain_find(database, "GET /api/stock-movements/ page", "stock_movements", {}, [("created_at", -1), ("_id", -1)]),
        _explain_count(database, "GET /api/stock-movements/ total", "stock_movements", {}),
        _explain_find(database, "GET /api/purchase-orders/ page", "purchase_orders", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/purchase-orders/ total", "purchase_orders", {}),
        _explain_find(database, "GET /api/sales-orders/ page", "sales_orders", {}, [("created_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/sales-orders/ total", "sales_orders", {}),
        _explain_find(database, "GET /api/payments/ page", "payments", {}, [("received_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/payments/ total", "payments", {}),
        _explain_find(database, "GET /api/invoices/ page", "invoices", {}, [("issued_at", -1), ("_id", 1)]),
        _explain_count(database, "GET /api/invoices/ total", "invoices", {}),
        _explain_aggregate(
            database,
            "GET /api/reports/sales/",
            "sales_orders",
            [
                {"$match": fulfilled_sales},
                {"$sort": {"fulfilled_at": -1, "_id": 1}},
                {"$skip": 0},
                {"$limit": PAGE_SIZE},
                {"$lookup": {"from": "sales_returns", "localField": "_id", "foreignField": "sales_order_id", "as": "returns"}},
                {"$addFields": {"returns_total": {"$sum": "$returns.total"}}},
            ],
            related_collections=("sales_returns",),
        ),
        _explain_count(database, "GET /api/reports/sales/ total", "sales_orders", fulfilled_sales),
        _explain_aggregate(
            database,
            "GET /api/reports/monthly-sales/",
            "sales_orders",
            [
                {"$match": {"status": "fulfilled", "fulfilled_at": {"$gte": chart_start, "$lt": end}}},
                {"$lookup": {"from": "sales_returns", "localField": "_id", "foreignField": "sales_order_id", "as": "returns"}},
                {"$addFields": {"returns_total": {"$sum": "$returns.total"}, "month": {"$dateToString": {"format": "%Y-%m", "date": "$fulfilled_at", "timezone": settings.BUSINESS_TIMEZONE}}}},
                {"$group": {"_id": "$month", "order_count": {"$sum": 1}, "gross_sales": {"$sum": "$grand_total"}, "returns_total": {"$sum": "$returns_total"}}},
                {"$sort": {"_id": 1}},
            ],
            related_collections=("sales_returns",),
        ),
        _explain_aggregate(
            database,
            "GET /api/reports/inventory/",
            "products",
            inventory_statistics_pipeline,
        ),
        _explain_aggregate(database, "GET /api/reports/low-stock/", "products", [{"$match": active_low_stock}, {"$sort": {"available_quantity": 1, "_id": 1}}, {"$skip": 0}, {"$limit": PAGE_SIZE}]),
        _explain_count(database, "GET /api/reports/low-stock/ total", "products", active_low_stock),
        _explain_aggregate(database, "GET /api/reports/employees/", "employees", [{"$match": {"joining_date": {"$gte": start, "$lt": end}}}, {"$sort": {"joining_date": -1, "_id": 1}}, {"$skip": 0}, {"$limit": PAGE_SIZE}]),
        _explain_count(database, "GET /api/reports/employees/ total", "employees", {"joining_date": {"$gte": start, "$lt": end}}),
        _explain_aggregate(database, "GET /api/reports/departments/", "departments", [{"$match": {"created_at": {"$gte": start, "$lt": end}}}, {"$sort": {"created_at": -1, "_id": 1}}, {"$skip": 0}, {"$limit": PAGE_SIZE}, {"$lookup": {"from": "employees", "localField": "_id", "foreignField": "department_id", "as": "employees"}}], related_collections=("employees",)),
        _explain_count(database, "GET /api/reports/departments/ total", "departments", {"created_at": {"$gte": start, "$lt": end}}),
        _explain_aggregate(database, "GET /api/reports/suppliers/", "suppliers", [{"$match": {"created_at": {"$gte": start, "$lt": end}}}, {"$sort": {"created_at": -1, "_id": 1}}, {"$skip": 0}, {"$limit": PAGE_SIZE}]),
        _explain_count(database, "GET /api/reports/suppliers/ total", "suppliers", {"created_at": {"$gte": start, "$lt": end}}),
        _explain_aggregate(database, "GET /api/reports/purchases/", "purchase_orders", [{"$match": {"created_at": {"$gte": start, "$lt": end}}}, {"$sort": {"created_at": -1, "_id": 1}}, {"$skip": 0}, {"$limit": PAGE_SIZE}]),
        _explain_count(database, "GET /api/reports/purchases/ total", "purchase_orders", {"created_at": {"$gte": start, "$lt": end}}),
        _explain_aggregate(database, "Dashboard: employee count", "employees", [{"$match": {"status": "active"}}, {"$count": "count"}]),
        _explain_aggregate(database, "Dashboard: department count", "departments", [{"$match": {"is_active": True}}, {"$count": "count"}]),
        _explain_aggregate(database, "Dashboard: product count", "products", [{"$match": active_products}, {"$count": "count"}]),
        _explain_aggregate(
            database,
            "Dashboard: inventory statistics",
            "products",
            inventory_statistics_pipeline,
        ),
        _explain_aggregate(
            database,
            "Dashboard: inventory by category",
            "products",
            inventory_by_category_pipeline,
        ),
        _explain_aggregate(database, "Dashboard: low-stock products", "products", [{"$match": active_low_stock}, {"$sort": {"available_quantity": 1, "_id": 1}}, {"$limit": 10}]),
        _explain_aggregate(database, "Dashboard: supplier count", "suppliers", [{"$match": {"status": "active"}}, {"$count": "count"}]),
        _explain_aggregate(database, "Dashboard: customer count", "customers", [{"$match": {"status": "active"}}, {"$count": "count"}]),
        _explain_aggregate(database, "Dashboard: pending purchases", "purchase_orders", [{"$match": {"status": {"$in": PENDING_PURCHASE_STATUSES}}}, {"$count": "count"}]),
        _explain_aggregate(
            database,
            "Dashboard: purchase statistics",
            "purchase_orders",
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
        ),
        _explain_aggregate(
            database,
            "Dashboard: sales chart",
            "sales_orders",
            [
                {"$match": {"status": "fulfilled", "fulfilled_at": {"$gte": chart_start, "$lt": end}}},
                {"$lookup": {"from": "sales_returns", "localField": "_id", "foreignField": "sales_order_id", "as": "returns"}},
                {"$addFields": {"returns_total": {"$sum": "$returns.total"}, "month": {"$dateToString": {"format": "%Y-%m", "date": "$fulfilled_at", "timezone": settings.BUSINESS_TIMEZONE}}}},
                {"$group": {"_id": "$month", "order_count": {"$sum": 1}, "gross_sales": {"$sum": "$grand_total"}}},
                {"$sort": {"_id": 1}},
            ],
            related_collections=("sales_returns",),
        ),
        _explain_aggregate(
            database,
            "Dashboard: purchase chart",
            "purchase_orders",
            purchase_month_pipeline,
        ),
        _explain_aggregate(
            database,
            "Dashboard: recent sales",
            "sales_orders",
            [
                {"$match": {"status": "fulfilled"}},
                {"$sort": {"fulfilled_at": -1, "_id": 1}},
                {"$limit": 10},
                {"$lookup": {"from": "sales_returns", "localField": "_id", "foreignField": "sales_order_id", "as": "returns"}},
            ],
            related_collections=("sales_returns",),
        ),
        _explain_aggregate(database, "Dashboard: recent purchases", "purchase_orders", [{"$match": {}}, {"$sort": {"updated_at": -1, "_id": 1}}, {"$limit": 10}]),
    ]
    return cases


def _print_plans(cases: list[tuple[str, dict[str, Any]]]) -> None:
    print("QUERY PLAN RESULTS (MongoDB explain executionStats)")
    print("COLLSCAN also flags explain cases requiring a full collection scan.")
    print("name | stages | indexes | nReturned | docsExamined | keysExamined")
    for name, result in cases:
        stages = ",".join(sorted(result["stages"])) or "n/a"
        indexes = ",".join(result["indexes"]) or "-"
        print(
            f"{name} | {stages} | {indexes} | {result['n_returned']} | "
            f"{result['docs_examined']} | {result['keys_examined']}"
        )

    print("INDEXES NOT SELECTED BY THIS EXPLAIN WORKLOAD")
    total_unused = 0
    exercised = {
        collection
        for _, result in cases
        for collection in (result["collection"], *result["related_collections"])
    }
    used_by_collection: dict[str, set[str]] = {collection: set() for collection in exercised}
    for _, result in cases:
        used_by_collection[result["collection"]].update(result["indexes"])
        for related in result["related_collections"]:
            related_indexes = {index.name for index in COLLECTIONS[related].indexes}
            used_by_collection[related].update(
                set(result["indexes"]) & related_indexes
            )
    for collection_name in sorted(exercised):
        used = used_by_collection[collection_name]
        for index in COLLECTIONS[collection_name].indexes:
            if index.name not in used:
                if not index.unique and index.expire_after_seconds is None:
                    total_unused += 1
                    print(f"- {collection_name}.{index.name}")
    print(f"Non-unique indexes not selected by workload: {total_unused}")


def main() -> int:
    args = _arguments()
    if args.records < 10_000:
        raise SystemExit("--records must be at least 10000.")
    client, database = _connect(args.database)
    try:
        client.admin.command("ping")
        if not args.explain_only:
            existing = [
                name
                for name in database.list_collection_names()
                if database[name].estimated_document_count() > 0
            ]
            if existing:
                raise SystemExit(
                    "Refusing to seed non-empty demo database; use a new "
                    f"database name with the smarterp_perf_ prefix. Found: {existing}"
                )
            initialize_database(database, lambda _: None)
            _seed(database, args.records)
            print(f"Seeded fake records into local database {args.database}:")
            for name in (
                "products",
                "sales_orders",
                "purchase_orders",
                "employees",
                "departments",
                "customers",
                "suppliers",
                "stock_movements",
                "payments",
                "invoices",
                "audit_logs",
            ):
                print(f"- {name}: {database[name].estimated_document_count()}")
        else:
            required = ("products", "sales_orders", "purchase_orders")
            counts = {name: database[name].estimated_document_count() for name in required}
            if min(counts.values()) < 10_000:
                raise SystemExit(
                    "Explain-only mode requires at least 10000 products, sales "
                    f"orders, and purchase orders; found {counts}."
                )
            initialize_database(database, lambda _: None)
        _print_plans(_explain_cases(database))
    finally:
        client.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
