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
    for definition in COLLECTIONS.values():
        assert definition.purpose
        assert definition.validator["$jsonSchema"]["bsonType"] == "object"
        assert definition.indexes


def test_required_unique_indexes_are_defined():
    required = {
        ("users", ("email",)),
        ("employees", ("employee_code",)),
        ("products", ("sku",)),
        ("suppliers", ("code",)),
        ("customers", ("code",)),
        ("purchase_orders", ("po_number",)),
        ("sales_orders", ("order_number",)),
        ("invoices", ("invoice_number",)),
        ("purchase_receipts", ("receipt_reference",)),
        ("idempotency_keys", ("key", "scope")),
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
    assert "min_stock_level" in product_fields
    assert {"quantity_change", "reserved_change", "performed_by"} <= movement_fields
    assert {"return_status", "payment_status", "status_history"} <= sales_fields
