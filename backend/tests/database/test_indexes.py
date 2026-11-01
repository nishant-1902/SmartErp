from database.indexes import COLLECTIONS


EXPECTED_COLLECTIONS = {
    "users",
    "employees",
    "departments",
    "products",
    "stock_movements",
    "suppliers",
    "purchase_orders",
    "purchase_receipts",
    "customers",
    "sales_orders",
    "payments",
    "invoices",
    "audit_logs",
    "refresh_tokens",
    "login_attempts",
    "idempotency_keys",
    "counters",
}


def test_all_required_collections_have_purpose_validator_and_indexes():
    assert set(COLLECTIONS) == EXPECTED_COLLECTIONS
    for collection_name, definition in COLLECTIONS.items():
        assert definition.purpose
        assert definition.validator["$jsonSchema"]["bsonType"] == "object"
        if collection_name != "counters":
            assert definition.indexes


def test_required_unique_indexes_are_defined():
    required = {
        ("users", ("email",)),
        ("employees", ("employee_code",)),
        ("employees", ("email",)),
        ("products", ("sku",)),
        ("suppliers", ("code",)),
        ("customers", ("code",)),
        ("purchase_orders", ("po_number",)),
        ("sales_orders", ("order_number",)),
        ("invoices", ("invoice_number",)),
        ("purchase_receipts", ("receipt_reference",)),
        ("purchase_receipts", ("purchase_order_id", "idempotency_key")),
        ("idempotency_keys", ("scope", "key")),
    }
    defined = {
        (collection_name, tuple(field for field, _ in index.keys))
        for collection_name, definition in COLLECTIONS.items()
        for index in definition.indexes
        if index.unique
    }

    assert required <= defined


def test_optional_unique_indexes_use_partial_filters_not_sparse():
    optional_unique_indexes = [
        index
        for definition in COLLECTIONS.values()
        for index in definition.indexes
        if index.unique and index.partial_filter_expression is not None
    ]

    assert optional_unique_indexes
    assert all(
        index.partial_filter_expression is not None for index in optional_unique_indexes
    )


def test_ttl_indexes_exist_for_all_ephemeral_collections():
    ttl_collections = {
        collection_name
        for collection_name, definition in COLLECTIONS.items()
        if any(index.expire_after_seconds == 0 for index in definition.indexes)
    }

    assert ttl_collections == {"login_attempts", "idempotency_keys", "refresh_tokens"}


def test_workflow_documents_include_required_inventory_and_order_fields():
    purchase_fields = set(
        COLLECTIONS["purchase_orders"].validator["$jsonSchema"]["required"]
    )
    purchase_item_fields = set(
        COLLECTIONS["purchase_orders"].validator["$jsonSchema"]["properties"]["items"][
            "items"
        ]["required"]
    )
    product_fields = set(
        COLLECTIONS["products"].validator["$jsonSchema"]["required"]
    )
    movement_fields = set(
        COLLECTIONS["stock_movements"].validator["$jsonSchema"]["required"]
    )
    sales_fields = set(
        COLLECTIONS["sales_orders"].validator["$jsonSchema"]["required"]
    )

    assert {"quantity_ordered", "quantity_received"} <= purchase_item_fields
    assert "status_history" in purchase_fields
    assert "tax_rate" in purchase_fields
    assert (
        COLLECTIONS["purchase_orders"].validator["$jsonSchema"]["properties"][
            "tax_rate"
        ]["bsonType"]
        == "decimal"
    )
    receipt_schema = COLLECTIONS["purchase_receipts"].validator["$jsonSchema"]
    assert {"idempotency_key", "notes"} <= set(receipt_schema["required"])
    receipt_indexes = COLLECTIONS["purchase_receipts"].indexes
    order_idempotency_index = next(
        index
        for index in receipt_indexes
        if index.name == "uq_receipts_order_idempotency"
    )
    assert order_idempotency_index.unique is True
    assert order_idempotency_index.keys == (
        ("purchase_order_id", 1),
        ("idempotency_key", 1),
    )
    assert "min_stock_level" in product_fields
    assert {"quantity_change", "reserved_change", "performed_by"} <= movement_fields
    movement_properties = COLLECTIONS["stock_movements"].validator["$jsonSchema"][
        "properties"
    ]
    assert movement_properties["reserved_change"]["bsonType"] == ["int", "long"]
    assert {"return_status", "payment_status", "status_history"} <= sales_fields


def test_account_documents_require_security_and_rotation_fields():
    user_fields = set(COLLECTIONS["users"].validator["$jsonSchema"]["required"])
    refresh_fields = set(
        COLLECTIONS["refresh_tokens"].validator["$jsonSchema"]["required"]
    )

    assert {
        "email", "password_hash", "full_name", "role", "is_active",
        "token_version", "last_login_at", "created_at", "updated_at",
    } <= user_fields
    assert "employee_id" not in user_fields
    assert {
        "user_id", "token_hash", "family_id", "status", "expires_at",
        "revoked_at", "replaced_by", "user_agent", "ip",
    } <= refresh_fields


def test_audit_log_indexes_support_user_action_and_date_filters():
    indexes = {
        index.name: tuple(field for field, _ in index.keys)
        for index in COLLECTIONS["audit_logs"].indexes
    }

    assert indexes["ix_audit_actor_created"] == ("actor_id", "created_at")
    assert indexes["ix_audit_action_created"] == ("action", "created_at")
    assert indexes["ix_audit_created"] == ("created_at",)
