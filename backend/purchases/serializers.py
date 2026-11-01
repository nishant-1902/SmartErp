"""Strict request serializers for purchase-order endpoints."""

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
                "Send monetary values as decimal strings, not floating-point numbers."
            )
        return super().to_internal_value(data)


class PurchaseOrderItemSerializer(StrictSerializer):
    """Validate client-writable PO item fields and ignore server-owned totals."""

    product_id = serializers.CharField(trim_whitespace=True)
    quantity_ordered = serializers.IntegerField(min_value=1)
    unit_cost = ExactDecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        coerce_to_string=False,
    )
    line_total = ExactDecimalField(
        max_digits=18,
        decimal_places=2,
        read_only=True,
    )
    sku = serializers.CharField(read_only=True)
    name = serializers.CharField(read_only=True)
    quantity_received = serializers.IntegerField(read_only=True)

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and isinstance(data.get("quantity_ordered"), bool):
            raise serializers.ValidationError(
                {"quantity_ordered": "Must be a positive integer."}
            )
        return super().to_internal_value(data)

    def validate_product_id(self, value):
        """Parse product IDs before passing them to a service or query."""
        return parse_object_id(value)


class PurchaseOrderCreateSerializer(StrictSerializer):
    """Validate writable PO fields while making server totals read-only."""

    supplier_id = serializers.CharField(trim_whitespace=True)
    items = PurchaseOrderItemSerializer(many=True, allow_empty=False)
    tax_rate = ExactDecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        coerce_to_string=False,
    )
    subtotal = ExactDecimalField(max_digits=18, decimal_places=2, read_only=True)
    tax_total = ExactDecimalField(max_digits=18, decimal_places=2, read_only=True)
    grand_total = ExactDecimalField(max_digits=18, decimal_places=2, read_only=True)

    def validate_supplier_id(self, value):
        """Parse supplier IDs before passing them to a service or query."""
        return parse_object_id(value)


class PurchaseOrderPatchSerializer(PurchaseOrderCreateSerializer):
    """Validate a non-empty Draft update without accepting server-owned fields."""

    supplier_id = serializers.CharField(required=False, trim_whitespace=True)
    items = PurchaseOrderItemSerializer(many=True, allow_empty=False, required=False)
    tax_rate = ExactDecimalField(
        max_digits=5,
        decimal_places=2,
        min_value=Decimal("0"),
        max_value=Decimal("100"),
        required=False,
        coerce_to_string=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class PurchaseOrderListQuerySerializer(StrictSerializer):
    """Validate purchase-order filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(
        min_value=1,
        max_value=100,
        required=False,
        default=20,
    )
    status = serializers.ChoiceField(
        choices=(
            "draft",
            "pending_approval",
            "approved",
            "rejected",
            "partially_received",
            "received",
            "cancelled",
        ),
        required=False,
    )
    supplier_id = serializers.CharField(required=False, trim_whitespace=True)

    def validate_supplier_id(self, value):
        """Parse supplier IDs before passing them to a service or query."""
        return parse_object_id(value)


class RejectPurchaseOrderSerializer(StrictSerializer):
    """Require a non-empty reason when rejecting a PO."""

    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)

    def validate_reason(self, value):
        if not value:
            raise serializers.ValidationError("A rejection reason is required.")
        return value


class EmptyActionSerializer(StrictSerializer):
    """Reject unexpected request-body fields for argument-free actions."""


class PurchaseReceiptItemSerializer(StrictSerializer):
    """Validate one product receipt quantity."""

    product_id = serializers.CharField(trim_whitespace=True)
    quantity_received = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        if isinstance(data, Mapping) and isinstance(
            data.get("quantity_received"),
            bool,
        ):
            raise serializers.ValidationError(
                {"quantity_received": "Must be a positive integer."}
            )
        return super().to_internal_value(data)

    def validate_product_id(self, value):
        """Parse product IDs before passing them to a service or query."""
        return parse_object_id(value)


class PurchaseReceiptSerializer(StrictSerializer):
    """Validate receipt body fields."""

    items = PurchaseReceiptItemSerializer(many=True, allow_empty=False)
    notes = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        min_length=3,
        max_length=500,
        trim_whitespace=True,
        default=None,
    )

    def validate(self, attrs):
        product_ids = [item["product_id"] for item in attrs["items"]]
        if len(product_ids) != len(set(product_ids)):
            raise serializers.ValidationError(
                {"items": "A product may appear only once in a receipt."}
            )
        if attrs.get("notes") == "":
            attrs["notes"] = None
        return attrs
