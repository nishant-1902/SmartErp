"""Strict request serializers for product catalogue endpoints."""

from collections.abc import Mapping
from decimal import Decimal

from rest_framework import serializers

from common.exceptions import ValidationFailed
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


class ProductCreateSerializer(StrictSerializer):
    """Validate all client-writable fields for a new product."""

    sku = serializers.CharField(max_length=64, trim_whitespace=True)
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=2000,
        default=None,
    )
    category = serializers.CharField(max_length=100, trim_whitespace=True)
    unit = serializers.CharField(max_length=30, trim_whitespace=True)
    cost_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        coerce_to_string=False,
    )
    selling_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        coerce_to_string=False,
    )
    min_stock_level = serializers.IntegerField(min_value=0)
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_sku(self, value):
        """Store SKUs in uppercase and reject values containing only spaces."""
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_name(self, value):
        """Reject blank product names."""
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_category(self, value):
        """Reject blank product categories."""
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_unit(self, value):
        """Reject blank product units."""
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized


class ProductPatchSerializer(ProductCreateSerializer):
    """Validate editable fields without permitting stock changes or SKU edits."""

    sku = None
    name = serializers.CharField(
        max_length=200,
        required=False,
        trim_whitespace=True,
    )
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=2000,
    )
    category = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    unit = serializers.CharField(max_length=30, required=False, trim_whitespace=True)
    cost_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        coerce_to_string=False,
    )
    selling_price = serializers.DecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0.01"),
        required=False,
        coerce_to_string=False,
    )
    min_stock_level = serializers.IntegerField(min_value=0, required=False)
    is_active = serializers.BooleanField(required=False)

    def to_internal_value(self, data):
        """Give explicit errors for immutable SKU and service-owned stock fields."""
        if isinstance(data, Mapping):
            stock_fields = {"quantity_on_hand", "reserved_quantity"} & set(data)
            if stock_fields:
                fields = ", ".join(sorted(stock_fields))
                raise serializers.ValidationError(
                    {
                        "fields": (
                            f"{fields} can only be changed through stock operations."
                        )
                    }
                )
            if "sku" in data:
                raise serializers.ValidationError(
                    {"sku": "SKU is immutable and cannot be changed."}
                )
        return super().to_internal_value(data)

    def validate(self, attrs):
        """Require at least one editable field."""
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class ProductListQuerySerializer(StrictSerializer):
    """Validate product search, filters, sorting, and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    category = serializers.CharField(max_length=100, required=False, allow_blank=False)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)
    low_stock = serializers.BooleanField(required=False, allow_null=True, default=None)
    sort_by = serializers.ChoiceField(
        choices=(
            "sku",
            "name",
            "category",
            "unit",
            "cost_price",
            "selling_price",
            "quantity_on_hand",
            "reserved_quantity",
            "min_stock_level",
            "is_active",
            "created_at",
            "updated_at",
        ),
        required=False,
    )
    sort_order = serializers.ChoiceField(
        choices=("asc", "desc"),
        required=False,
        default="asc",
    )

    def validate_category(self, value):
        """Normalize category filter whitespace."""
        return value.strip()


class ProductLowStockQuerySerializer(ProductListQuerySerializer):
    """Validate low-stock list filters without a redundant low_stock flag."""

    low_stock = None


class ProductCategoriesQuerySerializer(StrictSerializer):
    """Reject unrecognized query parameters on the categories endpoint."""


class StockAdjustmentSerializer(StrictSerializer):
    """Validate a stock adjustment request body."""

    product_id = serializers.CharField(trim_whitespace=True)
    quantity_change = serializers.IntegerField()
    reason = serializers.CharField(min_length=3, max_length=500, trim_whitespace=True)

    def to_internal_value(self, data):
        """Reject booleans rather than treating them as integer stock deltas."""
        if isinstance(data, Mapping):
            quantity_change = data.get("quantity_change")
            if isinstance(quantity_change, bool):
                raise serializers.ValidationError(
                    {"quantity_change": "Must be a non-zero integer."}
                )
        return super().to_internal_value(data)

    def validate_product_id(self, value):
        """Parse product IDs before passing them to a service or query."""
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate_quantity_change(self, value):
        """Reject no-op adjustments."""
        if value == 0:
            raise serializers.ValidationError("Must be a non-zero integer.")
        return value


class StockMovementsQuerySerializer(StrictSerializer):
    """Validate stock movement filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    product = serializers.CharField(required=False, trim_whitespace=True)
    type = serializers.ChoiceField(
        choices=(
            "purchase_receipt",
            "sale_fulfilment",
            "sale_return",
            "adjustment",
            "reservation",
            "reservation_release",
        ),
        required=False,
    )
    start_date = serializers.DateTimeField(required=False)
    end_date = serializers.DateTimeField(required=False)
    user = serializers.CharField(required=False, trim_whitespace=True)

    def validate_product(self, value):
        """Parse the optional product filter ObjectId."""
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate_user(self, value):
        """Parse the optional actor filter ObjectId."""
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate_start_date(self, value):
        """Require an explicit timezone on movement date filters."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise serializers.ValidationError("Must include a timezone.")
        return value

    def validate_end_date(self, value):
        """Require an explicit timezone on movement date filters."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise serializers.ValidationError("Must include a timezone.")
        return value

    def validate(self, attrs):
        """Reject date ranges whose end precedes their start."""
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start is not None and end is not None and end < start:
            raise serializers.ValidationError(
                {"end_date": "Must be greater than or equal to start_date."}
            )
        return attrs
