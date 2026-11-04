"""Strict request serializers for sales-order endpoints."""

from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers

from common.object_id import parse_object_id


class StrictSerializer(serializers.Serializer):
    """Reject undeclared or unsafe request keys."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            unsafe_fields = {
                field
                for field in data
                if isinstance(field, str) and (field.startswith("$") or "." in field)
            }
            if unknown_fields or unsafe_fields:
                rejected = sorted(unknown_fields | unsafe_fields)
                raise serializers.ValidationError(
                    {"fields": "Unsupported or unsafe fields: " + ", ".join(rejected)}
                )
        return super().to_internal_value(data)


class ExactDecimalField(serializers.DecimalField):
    """Require exact decimal input rather than a JSON floating-point value."""

    def to_internal_value(self, data):
        if isinstance(data, float):
            raise serializers.ValidationError(
                "Send percentages as decimal strings, not floating-point numbers."
            )
        return super().to_internal_value(data)


class SalesOrderItemSerializer(StrictSerializer):
    """Validate client-editable item fields and ignore all server-owned values."""

    product_id = serializers.CharField(trim_whitespace=True)
    quantity = serializers.IntegerField(min_value=1)
    discount_percent = ExactDecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        default=Decimal("0"),
        coerce_to_string=False,
    )
    tax_percent = ExactDecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        default=Decimal("0"),
        coerce_to_string=False,
    )
    sku = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    unit_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    line_subtotal = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    line_tax = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    line_total = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and isinstance(data.get("quantity"), bool):
            raise serializers.ValidationError(
                {"quantity": "Must be a positive integer."}
            )
        return super().to_internal_value(data)

    def validate_product_id(self, value):
        """Parse product IDs before passing them to a service or query."""
        return parse_object_id(value)


class SalesOrderCreateSerializer(StrictSerializer):
    """Validate a new sales order while ignoring client-calculated values."""

    customer_id = serializers.CharField(trim_whitespace=True)
    items = SalesOrderItemSerializer(many=True, allow_empty=False)
    order_number = serializers.CharField(read_only=True)
    subtotal = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )
    discount_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )
    tax_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )
    grand_total = serializers.DecimalField(
        max_digits=18, decimal_places=2, read_only=True
    )

    def validate_customer_id(self, value):
        """Parse customer IDs before passing them to a service or query."""
        return parse_object_id(value)

    def validate_items(self, items):
        """Reject duplicate products so each product has one stock line."""
        product_ids = [item["product_id"] for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "A product may appear only once in a sales order."
            )
        return items


class SalesOrderPatchSerializer(SalesOrderCreateSerializer):
    """Validate a non-empty Draft edit."""

    customer_id = serializers.CharField(required=False, trim_whitespace=True)
    items = SalesOrderItemSerializer(many=True, allow_empty=False, required=False)

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class SalesOrderListQuerySerializer(StrictSerializer):
    """Validate sales-order list filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
    )
    status = serializers.ChoiceField(
        choices=("draft", "confirmed", "fulfilled", "cancelled"),
        required=False,
    )
    payment_status = serializers.ChoiceField(
        choices=("unpaid", "partial", "paid"),
        required=False,
    )
    customer_id = serializers.CharField(required=False, trim_whitespace=True)

    def validate_customer_id(self, value):
        """Parse customer IDs before passing them to a service or query."""
        return parse_object_id(value)


class EmptyActionSerializer(StrictSerializer):
    """Reject unexpected request-body fields for argument-free actions."""


class PaymentCreateSerializer(StrictSerializer):
    """Validate an exact payment amount, method, and optional reference."""

    amount = ExactDecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        coerce_to_string=False,
    )
    method = serializers.ChoiceField(
        choices=("cash", "bank_transfer", "card", "other")
    )
    reference = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=200,
        trim_whitespace=True,
        default=None,
    )

    def validate_reference(self, value):
        return value.strip() or None if value is not None else None


class SalesReturnItemSerializer(StrictSerializer):
    """Validate one product and positive return quantity."""

    product_id = serializers.CharField(trim_whitespace=True)
    quantity = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and isinstance(data.get("quantity"), bool):
            raise serializers.ValidationError(
                {"quantity": "Must be a positive integer."}
            )
        return super().to_internal_value(data)

    def validate_product_id(self, value):
        return parse_object_id(value)


class SalesReturnCreateSerializer(StrictSerializer):
    """Validate a return request and its required reason."""

    items = SalesReturnItemSerializer(many=True, allow_empty=False)
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("A return reason is required.")
        return value

    def validate_items(self, items):
        product_ids = [item["product_id"] for item in items]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                "A product may appear only once in a return."
            )
        return items


class PaymentListQuerySerializer(StrictSerializer):
    """Validate payment history filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
    )
    customer_id = serializers.CharField(required=False, trim_whitespace=True)
    sales_order_id = serializers.CharField(required=False, trim_whitespace=True)
    method = serializers.ChoiceField(
        choices=("cash", "bank_transfer", "card", "other"),
        required=False,
    )
    status = serializers.ChoiceField(
        choices=("pending", "completed", "refunded", "failed"),
        required=False,
    )

    def validate_customer_id(self, value):
        return parse_object_id(value)

    def validate_sales_order_id(self, value):
        return parse_object_id(value)


class InvoiceListQuerySerializer(StrictSerializer):
    """Validate invoice history filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
    )
    customer_id = serializers.CharField(required=False, trim_whitespace=True)
    sales_order_id = serializers.CharField(required=False, trim_whitespace=True)

    def validate_customer_id(self, value):
        return parse_object_id(value)

    def validate_sales_order_id(self, value):
        return parse_object_id(value)
