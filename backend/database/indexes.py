"""MongoDB collection validators and workload-driven index definitions."""

from dataclasses import dataclass
from typing import Any

from bson.decimal128 import Decimal128


@dataclass(frozen=True)
class IndexDefinition:
    """Declarative definition for one MongoDB index."""

    name: str
    keys: tuple[tuple[str, int], ...]
    unique: bool = False
    partial_filter_expression: dict[str, Any] | None = None
    expire_after_seconds: int | None = None


@dataclass(frozen=True)
class CollectionDefinition:
    """Purpose, validator, and indexes for one application collection."""

    purpose: str
    validator: dict[str, Any]
    indexes: tuple[IndexDefinition, ...]


def _schema(
    required: tuple[str, ...],
    properties: dict[str, Any],
) -> dict[str, Any]:
    """Build a MongoDB JSON Schema validator."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": list(required),
            "properties": properties,
        }
    }


def _index(
    name: str,
    *keys: tuple[str, int],
    unique: bool = False,
    partial: dict[str, Any] | None = None,
    ttl: int | None = None,
) -> IndexDefinition:
    return IndexDefinition(
        name=name,
        keys=keys,
        unique=unique,
        partial_filter_expression=partial,
        expire_after_seconds=ttl,
    )


_ADDRESS_SCHEMA = {
    "bsonType": "object",
    "required": ["line1", "city", "country"],
    "properties": {
        "line1": {"bsonType": "string", "minLength": 1, "maxLength": 200},
        "line2": {"bsonType": ["string", "null"], "maxLength": 200},
        "city": {"bsonType": "string", "minLength": 1, "maxLength": 100},
        "region": {"bsonType": ["string", "null"], "maxLength": 100},
        "postal_code": {"bsonType": ["string", "null"], "maxLength": 30},
        "country": {"bsonType": "string", "minLength": 2, "maxLength": 100},
    },
}

_SUPPLIER_SNAPSHOT_SCHEMA = {
    "bsonType": "object",
    "required": ["code", "name"],
    "properties": {
        "code": {"bsonType": "string"},
        "name": {"bsonType": "string"},
        "email": {"bsonType": ["string", "null"]},
    },
}

_CUSTOMER_SNAPSHOT_SCHEMA = {
    "bsonType": "object",
    "required": ["code", "name"],
    "properties": {
        "code": {"bsonType": "string"},
        "name": {"bsonType": "string"},
        "email": {"bsonType": ["string", "null"]},
        "billing_address": {"bsonType": ["object", "null"]},
        "shipping_address": {"bsonType": ["object", "null"]},
    },
}


COLLECTIONS: dict[str, CollectionDefinition] = {
    "users": CollectionDefinition(
        purpose="Login identities, role grants, and links to employee profiles.",
        validator=_schema(
            (
                "email", "password_hash", "full_name", "role", "is_active",
                "token_version", "last_login_at", "created_at", "updated_at",
            ),
            {
                "email": {
                    "bsonType": "string",
                    "minLength": 3,
                    "maxLength": 254,
                    "pattern": "^[^A-Z]*$",
                },
                "password_hash": {"bsonType": "string", "minLength": 1},
                "full_name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "role": {
                    "enum": [
                        "super_admin", "hr_manager", "inventory_manager",
                        "purchase_manager", "sales_manager", "employee",
                    ]
                },
                "is_active": {"bsonType": "bool"},
                "employee_id": {"bsonType": ["objectId", "null"]},
                "token_version": {"bsonType": ["int", "long"], "minimum": 0},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "last_login_at": {"bsonType": ["date", "null"]},
            },
        ),
        indexes=(
            _index("uq_users_email", ("email", 1), unique=True),
            _index(
                "uq_users_employee_id",
                ("employee_id", 1),
                unique=True,
                partial={"employee_id": {"$type": "objectId"}},
            ),
            _index("ix_users_active_created", ("is_active", 1), ("created_at", -1)),
            _index("ix_users_role_active", ("role", 1), ("is_active", 1)),
        ),
    ),
    "employees": CollectionDefinition(
        purpose="Employee profiles and HR list/filter queries.",
        validator=_schema(
            (
                "employee_code", "first_name", "last_name", "name_search", "email",
                "department_id", "designation", "joining_date", "status", "created_at",
                "updated_at",
            ),
            {
                "employee_code": {
                    "bsonType": "string", "minLength": 1, "maxLength": 40
                },
                "first_name": {
                    "bsonType": "string", "minLength": 1, "maxLength": 100
                },
                "last_name": {
                    "bsonType": "string", "minLength": 1, "maxLength": 100
                },
                "name_search": {"bsonType": "string", "minLength": 1},
                "email": {
                    "bsonType": "string",
                    "minLength": 3,
                    "maxLength": 254,
                    "pattern": "^[^A-Z]*$",
                },
                "phone": {"bsonType": ["string", "null"]},
                "department_id": {"bsonType": "objectId"},
                "designation": {
                    "bsonType": "string", "minLength": 1, "maxLength": 100
                },
                "joining_date": {"bsonType": "date"},
                "status": {"enum": ["active", "inactive", "on_leave"]},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "deactivated_at": {"bsonType": ["date", "null"]},
            },
        ),
        indexes=(
            _index("uq_employees_code", ("employee_code", 1), unique=True),
            _index("uq_employees_email", ("email", 1), unique=True),
            _index(
                "ix_employees_department_status",
                ("department_id", 1),
                ("status", 1),
            ),
            _index("ix_employees_status_name", ("status", 1), ("name_search", 1)),
        ),
    ),
    "departments": CollectionDefinition(
        purpose="Organization units that employees belong to.",
        validator=_schema(
            ("code", "name", "name_search", "is_active", "created_at", "updated_at"),
            {
                "code": {"bsonType": "string", "minLength": 1, "maxLength": 40},
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 120},
                "name_search": {"bsonType": "string", "minLength": 1},
                "description": {"bsonType": ["string", "null"]},
                "manager_employee_id": {"bsonType": ["objectId", "null"]},
                "is_active": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_departments_code", ("code", 1), unique=True),
            _index("uq_departments_name", ("name_search", 1), unique=True),
            _index("ix_departments_active_name", ("is_active", 1), ("name_search", 1)),
        ),
    ),
    "products": CollectionDefinition(
        purpose="Product catalogue and current stock summary.",
        validator=_schema(
            (
                "sku", "name", "name_search", "category", "unit", "cost_price",
                "selling_price", "quantity_on_hand", "reserved_quantity",
                "min_stock_level", "is_active", "created_at", "updated_at",
            ),
            {
                "sku": {
                    "bsonType": "string",
                    "minLength": 1,
                    "maxLength": 64,
                    "pattern": "^[^a-z]*$",
                },
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "name_search": {"bsonType": "string", "minLength": 1},
                "description": {"bsonType": ["string", "null"]},
                "category": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "unit": {"bsonType": "string", "minLength": 1, "maxLength": 30},
                "cost_price": {"bsonType": "decimal", "minimum": Decimal128("0.01")},
                "selling_price": {"bsonType": "decimal", "minimum": Decimal128("0.01")},
                "quantity_on_hand": {"bsonType": ["int", "long"], "minimum": 0},
                "reserved_quantity": {"bsonType": ["int", "long"], "minimum": 0},
                "min_stock_level": {"bsonType": ["int", "long"], "minimum": 0},
                "is_active": {"bsonType": "bool"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_products_sku", ("sku", 1), unique=True),
            _index("ix_products_category_active", ("category", 1), ("is_active", 1)),
            _index("ix_products_active_name", ("is_active", 1), ("name_search", 1)),
        ),
    ),
    "stock_movements": CollectionDefinition(
        purpose="Append-only record of every stock increase or decrease.",
        validator=_schema(
            (
                "product_id", "movement_type", "quantity_change", "reserved_change",
                "quantity_before", "quantity_after", "reason", "reference_type",
                "reference_id", "performed_by", "created_at",
            ),
            {
                "product_id": {"bsonType": "objectId"},
                "movement_type": {
                    "enum": [
                        "purchase_receipt",
                        "sale_fulfilment",
                        "sale_return",
                        "adjustment",
                        "reservation",
                        "reservation_release",
                    ]
                },
                "quantity_change": {"bsonType": ["int", "long"]},
                "reserved_change": {"bsonType": ["int", "long"]},
                "quantity_before": {"bsonType": ["int", "long"], "minimum": 0},
                "quantity_after": {"bsonType": ["int", "long"], "minimum": 0},
                "reason": {"bsonType": "string", "minLength": 1, "maxLength": 500},
                "reference_type": {"bsonType": "string"},
                "reference_id": {"bsonType": "objectId"},
                "performed_by": {"bsonType": "objectId"},
                "created_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("ix_stock_product_created", ("product_id", 1), ("created_at", -1)),
            _index("ix_stock_reference", ("reference_type", 1), ("reference_id", 1)),
            _index("ix_stock_created", ("created_at", -1)),
        ),
    ),
    "suppliers": CollectionDefinition(
        purpose="Supplier contact records used by purchase orders.",
        validator=_schema(
            ("code", "name", "name_search", "status", "created_at", "updated_at"),
            {
                "code": {"bsonType": "string", "minLength": 1, "maxLength": 40},
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "name_search": {"bsonType": "string", "minLength": 1},
                "email": {"bsonType": ["string", "null"]},
                "phone": {"bsonType": ["string", "null"]},
                "contact_person": {"bsonType": ["string", "null"]},
                "address": {
                    "bsonType": ["object", "null"],
                    "required": _ADDRESS_SCHEMA["required"],
                    "properties": _ADDRESS_SCHEMA["properties"],
                },
                "payment_terms": {"bsonType": ["string", "null"]},
                "status": {"enum": ["active", "inactive"]},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_suppliers_code", ("code", 1), unique=True),
            _index("ix_suppliers_status_name", ("status", 1), ("name_search", 1)),
        ),
    ),
    "purchase_orders": CollectionDefinition(
        purpose=(
            "Purchase workflow state, totals, and immutable supplier/product "
            "snapshots."
        ),
        validator=_schema(
            (
                "po_number", "supplier_id", "supplier_snapshot", "items", "status",
                "tax_rate", "subtotal", "tax_total", "grand_total", "created_by",
                "created_at", "updated_at", "status_history",
            ),
            {
                "po_number": {"bsonType": "string", "minLength": 1, "maxLength": 40},
                "supplier_id": {"bsonType": "objectId"},
                "supplier_snapshot": _SUPPLIER_SNAPSHOT_SCHEMA,
                "items": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": [
                            "product_id", "sku", "name", "quantity_ordered",
                            "quantity_received", "unit_cost", "line_total",
                        ],
                        "properties": {
                            "product_id": {"bsonType": "objectId"},
                            "sku": {"bsonType": "string"},
                            "name": {"bsonType": "string"},
                            "quantity_ordered": {
                                "bsonType": ["int", "long"], "minimum": 1
                            },
                            "quantity_received": {
                                "bsonType": ["int", "long"], "minimum": 0
                            },
                            "unit_cost": {"bsonType": "decimal", "minimum": 0},
                            "line_total": {"bsonType": "decimal", "minimum": 0},
                        },
                    },
                },
                "status": {
                    "enum": [
                        "draft", "pending_approval", "approved", "rejected",
                        "partially_received", "received", "cancelled",
                    ]
                },
                "tax_rate": {
                    "bsonType": "decimal",
                    "minimum": 0,
                    "maximum": 100,
                },
                "subtotal": {"bsonType": "decimal", "minimum": 0},
                "tax_total": {"bsonType": "decimal", "minimum": 0},
                "grand_total": {"bsonType": "decimal", "minimum": 0},
                "created_by": {"bsonType": "objectId"},
                "approved_by": {"bsonType": ["objectId", "null"]},
                "status_history": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["status", "by", "at"],
                        "properties": {
                            "status": {"bsonType": "string"},
                            "by": {"bsonType": "objectId"},
                            "at": {"bsonType": "date"},
                            "note": {"bsonType": ["string", "null"]},
                        },
                    },
                },
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_purchase_orders_number", ("po_number", 1), unique=True),
            _index(
                "ix_purchase_orders_status_created",
                ("status", 1),
                ("created_at", -1),
            ),
            _index(
                "ix_purchase_orders_supplier_created",
                ("supplier_id", 1),
                ("created_at", -1),
            ),
        ),
    ),
    "purchase_receipts": CollectionDefinition(
        purpose="Each full or partial receipt against a purchase order.",
        validator=_schema(
            (
                "receipt_reference", "purchase_order_id", "supplier_id", "items",
                "received_by", "created_at", "idempotency_key", "notes",
            ),
            {
                "receipt_reference": {
                    "bsonType": "string", "minLength": 1, "maxLength": 64
                },
                "purchase_order_id": {"bsonType": "objectId"},
                "supplier_id": {"bsonType": "objectId"},
                "items": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": ["product_id", "quantity_received"],
                        "properties": {
                            "product_id": {"bsonType": "objectId"},
                            "quantity_received": {
                                "bsonType": ["int", "long"],
                                "minimum": 1,
                            },
                        },
                    },
                },
                "received_by": {"bsonType": "objectId"},
                "created_at": {"bsonType": "date"},
                "idempotency_key": {
                    "bsonType": "string",
                    "minLength": 36,
                    "maxLength": 36,
                },
                "notes": {"bsonType": ["string", "null"], "maxLength": 500},
            },
        ),
        indexes=(
            _index(
                "uq_purchase_receipts_reference",
                ("receipt_reference", 1),
                unique=True,
            ),
            _index(
                "ix_receipts_order_created",
                ("purchase_order_id", 1),
                ("created_at", -1),
            ),
            _index(
                "ix_receipts_supplier_created",
                ("supplier_id", 1),
                ("created_at", -1),
            ),
            _index(
                "uq_receipts_order_idempotency",
                ("purchase_order_id", 1),
                ("idempotency_key", 1),
                unique=True,
                partial={"idempotency_key": {"$type": "string"}},
            ),
        ),
    ),
    "customers": CollectionDefinition(
        purpose="Customer contacts, addresses, tax identity, and credit settings.",
        validator=_schema(
            ("code", "name", "name_search", "status", "created_at", "updated_at"),
            {
                "code": {"bsonType": "string", "minLength": 1, "maxLength": 40},
                "name": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "name_search": {"bsonType": "string", "minLength": 1},
                "email": {"bsonType": ["string", "null"]},
                "phone": {"bsonType": ["string", "null"]},
                "tax_id": {"bsonType": ["string", "null"], "minLength": 1},
                "billing_address": {
                    "bsonType": ["object", "null"],
                    "required": _ADDRESS_SCHEMA["required"],
                    "properties": _ADDRESS_SCHEMA["properties"],
                },
                "shipping_address": {
                    "bsonType": ["object", "null"],
                    "required": _ADDRESS_SCHEMA["required"],
                    "properties": _ADDRESS_SCHEMA["properties"],
                },
                "credit_limit": {"bsonType": ["decimal", "null"], "minimum": 0},
                "status": {"enum": ["active", "inactive"]},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_customers_code", ("code", 1), unique=True),
            _index(
                "uq_customers_tax_id_present",
                ("tax_id", 1),
                unique=True,
                partial={"tax_id": {"$type": "string"}},
            ),
            _index("ix_customers_status_name", ("status", 1), ("name_search", 1)),
        ),
    ),
    "sales_orders": CollectionDefinition(
        purpose=(
            "Sales workflow, customer snapshot, and server-calculated order "
            "totals."
        ),
        validator=_schema(
            (
                "order_number", "customer_id", "customer_snapshot", "items", "status",
                "return_status", "payment_status", "subtotal", "discount_total",
                "tax_total", "grand_total", "created_by", "created_at", "updated_at",
                "status_history",
            ),
            {
                "order_number": {
                    "bsonType": "string", "minLength": 1, "maxLength": 40
                },
                "customer_id": {"bsonType": "objectId"},
                "customer_snapshot": _CUSTOMER_SNAPSHOT_SCHEMA,
                "items": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": [
                            "product_id", "sku", "name", "quantity", "unit_price",
                            "line_subtotal", "line_tax", "line_total",
                        ],
                        "properties": {
                            "product_id": {"bsonType": "objectId"},
                            "sku": {"bsonType": "string"},
                            "name": {"bsonType": "string"},
                            "quantity": {"bsonType": ["int", "long"], "minimum": 1},
                            "unit_price": {"bsonType": "decimal", "minimum": 0},
                            "discount_percent": {
                                "bsonType": ["decimal", "int", "long"],
                                "minimum": 0,
                                "maximum": 100,
                            },
                            "tax_percent": {
                                "bsonType": ["decimal", "int", "long"],
                                "minimum": 0,
                            },
                            "line_subtotal": {"bsonType": "decimal", "minimum": 0},
                            "line_tax": {"bsonType": "decimal", "minimum": 0},
                            "line_total": {"bsonType": "decimal", "minimum": 0},
                        },
                    },
                },
                "status": {"enum": ["draft", "confirmed", "fulfilled", "cancelled"]},
                "return_status": {"enum": ["none", "partial", "full"]},
                "payment_status": {"enum": ["unpaid", "partial", "paid"]},
                "subtotal": {"bsonType": "decimal", "minimum": 0},
                "discount_total": {"bsonType": "decimal", "minimum": 0},
                "tax_total": {"bsonType": "decimal", "minimum": 0},
                "grand_total": {"bsonType": "decimal", "minimum": 0},
                "created_by": {"bsonType": "objectId"},
                "created_at": {"bsonType": "date"},
                "updated_at": {"bsonType": "date"},
                "fulfilled_at": {"bsonType": ["date", "null"]},
                "status_history": {
                    "bsonType": "array",
                    "items": {
                        "bsonType": "object",
                        "required": ["status", "by", "at"],
                        "properties": {
                            "status": {"bsonType": "string"},
                            "by": {"bsonType": "objectId"},
                            "at": {"bsonType": "date"},
                            "note": {"bsonType": ["string", "null"]},
                        },
                    },
                },
            },
        ),
        indexes=(
            _index("uq_sales_orders_number", ("order_number", 1), unique=True),
            _index(
                "ix_sales_orders_customer_created",
                ("customer_id", 1),
                ("created_at", -1),
            ),
            _index(
                "ix_sales_orders_status_created",
                ("status", 1),
                ("created_at", -1),
            ),
        ),
    ),
    "payments": CollectionDefinition(
        purpose="Append-only customer payment records allocated to sales orders.",
        validator=_schema(
            (
                "sales_order_id", "customer_id", "amount", "method", "status",
                "received_at", "created_by",
            ),
            {
                "sales_order_id": {"bsonType": "objectId"},
                "customer_id": {"bsonType": "objectId"},
                "payment_reference": {"bsonType": ["string", "null"], "minLength": 1},
                "amount": {
                    "bsonType": "decimal",
                    "minimum": 0,
                    "exclusiveMinimum": True,
                },
                "method": {"enum": ["cash", "bank_transfer", "card", "other"]},
                "status": {"enum": ["pending", "completed", "refunded", "failed"]},
                "received_at": {"bsonType": "date"},
                "created_by": {"bsonType": "objectId"},
                "created_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index(
                "uq_payments_reference_present",
                ("payment_reference", 1),
                unique=True,
                partial={"payment_reference": {"$type": "string"}},
            ),
            _index(
                "ix_payments_order_created",
                ("sales_order_id", 1),
                ("created_at", -1),
            ),
            _index("ix_payments_customer_status", ("customer_id", 1), ("status", 1)),
        ),
    ),
    "invoices": CollectionDefinition(
        purpose="Immutable invoice snapshots created when sales orders are fulfilled.",
        validator=_schema(
            (
                "invoice_number", "sales_order_id", "customer_id", "customer_snapshot",
                "items", "subtotal", "discount_total", "tax_total", "grand_total",
                "issued_at", "due_date", "created_at",
            ),
            {
                "invoice_number": {
                    "bsonType": "string", "minLength": 1, "maxLength": 40
                },
                "sales_order_id": {"bsonType": "objectId"},
                "customer_id": {"bsonType": "objectId"},
                "customer_snapshot": _CUSTOMER_SNAPSHOT_SCHEMA,
                "items": {
                    "bsonType": "array",
                    "minItems": 1,
                    "items": {
                        "bsonType": "object",
                        "required": [
                            "sku", "name", "quantity", "unit_price",
                            "line_subtotal", "line_tax", "line_total",
                        ],
                        "properties": {
                            "sku": {"bsonType": "string"},
                            "name": {"bsonType": "string"},
                            "quantity": {"bsonType": ["int", "long"], "minimum": 1},
                            "unit_price": {"bsonType": "decimal", "minimum": 0},
                            "line_subtotal": {"bsonType": "decimal", "minimum": 0},
                            "line_tax": {"bsonType": "decimal", "minimum": 0},
                            "line_total": {"bsonType": "decimal", "minimum": 0},
                        },
                    },
                },
                "subtotal": {"bsonType": "decimal", "minimum": 0},
                "discount_total": {"bsonType": "decimal", "minimum": 0},
                "tax_total": {"bsonType": "decimal", "minimum": 0},
                "grand_total": {"bsonType": "decimal", "minimum": 0},
                "issued_at": {"bsonType": "date"},
                "due_date": {"bsonType": "date"},
                "created_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_invoices_number", ("invoice_number", 1), unique=True),
            _index("uq_invoices_sales_order", ("sales_order_id", 1), unique=True),
            _index(
                "ix_invoices_customer_issued",
                ("customer_id", 1),
                ("issued_at", -1),
            ),
        ),
    ),
    "audit_logs": CollectionDefinition(
        purpose="Append-only record of security-sensitive and business state changes.",
        validator=_schema(
            ("actor_id", "action", "entity_type", "entity_id", "created_at"),
            {
                "actor_id": {"bsonType": ["objectId", "null"]},
                "action": {"bsonType": "string", "minLength": 1, "maxLength": 100},
                "entity_type": {"bsonType": "string", "minLength": 1, "maxLength": 80},
                "entity_id": {"bsonType": ["objectId", "string"]},
                "before": {"bsonType": ["object", "null"]},
                "after": {"bsonType": ["object", "null"]},
                "request_id": {"bsonType": ["string", "null"]},
                "created_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index(
                "ix_audit_entity_created",
                ("entity_type", 1),
                ("entity_id", 1),
                ("created_at", -1),
            ),
            _index("ix_audit_actor_created", ("actor_id", 1), ("created_at", -1)),
            _index("ix_audit_action_created", ("action", 1), ("created_at", -1)),
            _index("ix_audit_created", ("created_at", -1)),
        ),
    ),
    "refresh_tokens": CollectionDefinition(
        purpose=(
            "Hashed refresh-token records supporting rotation, revocation, "
            "and reuse detection."
        ),
        validator=_schema(
            (
                "user_id", "token_hash", "family_id", "status", "created_at",
                "expires_at", "revoked_at", "replaced_by", "user_agent", "ip",
            ),
            {
                "user_id": {"bsonType": "objectId"},
                "token_hash": {"bsonType": "string", "minLength": 1},
                "family_id": {"bsonType": "string", "minLength": 1},
                "status": {"enum": ["active", "rotated", "revoked"]},
                "created_at": {"bsonType": "date"},
                "expires_at": {"bsonType": "date"},
                "revoked_at": {"bsonType": ["date", "null"]},
                "replaced_by": {"bsonType": ["objectId", "null"]},
                "user_agent": {"bsonType": ["string", "null"]},
                "ip": {"bsonType": ["string", "null"]},
            },
        ),
        indexes=(
            _index("uq_refresh_tokens_hash", ("token_hash", 1), unique=True),
            _index(
                "ix_refresh_user_status_expiry",
                ("user_id", 1),
                ("status", 1),
                ("expires_at", 1),
            ),
            _index("ttl_refresh_tokens_expiry", ("expires_at", 1), ttl=0),
        ),
    ),
    "login_attempts": CollectionDefinition(
        purpose=(
            "Short-lived failed-login counts keyed by normalized email and "
            "client IP."
        ),
        validator=_schema(
            ("email", "client_ip", "failed_count", "window_started_at", "expires_at"),
            {
                "email": {"bsonType": "string", "minLength": 3, "maxLength": 254},
                "client_ip": {"bsonType": "string", "minLength": 1, "maxLength": 64},
                "failed_count": {"bsonType": ["int", "long"], "minimum": 0},
                "window_started_at": {"bsonType": "date"},
                "expires_at": {"bsonType": "date"},
                "locked_until": {"bsonType": ["date", "null"]},
            },
        ),
        indexes=(
            _index(
                "uq_login_attempts_email_ip",
                ("email", 1),
                ("client_ip", 1),
                unique=True,
            ),
            _index("ttl_login_attempts_expiry", ("expires_at", 1), ttl=0),
        ),
    ),
    "idempotency_keys": CollectionDefinition(
        purpose="Deduplication records and replay responses for retryable operations.",
        validator=_schema(
            ("key", "scope", "request_hash", "status", "created_at", "expires_at"),
            {
                "key": {"bsonType": "string", "minLength": 1, "maxLength": 255},
                "scope": {"bsonType": "string", "minLength": 1, "maxLength": 200},
                "request_hash": {"bsonType": "string", "minLength": 1},
                "status": {"enum": ["processing", "completed", "failed"]},
                "result_id": {"bsonType": ["objectId", "null"]},
                "response": {"bsonType": ["object", "null"]},
                "created_at": {"bsonType": "date"},
                "expires_at": {"bsonType": "date"},
            },
        ),
        indexes=(
            _index("uq_idempotency_scope_key", ("scope", 1), ("key", 1), unique=True),
            _index("ttl_idempotency_expiry", ("expires_at", 1), ttl=0),
        ),
    ),
    "counters": CollectionDefinition(
        purpose="Atomic counters that allocate human-readable business numbers.",
        validator=_schema(
            ("_id", "value", "updated_at"),
            {
                "_id": {"bsonType": "string", "minLength": 1},
                "value": {"bsonType": ["int", "long"], "minimum": 0},
                "updated_at": {"bsonType": "date"},
            },
        ),
        indexes=(),
    ),
}
