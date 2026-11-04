"""Strict request serializers for customer endpoints."""

from collections.abc import Mapping
from decimal import Decimal
import re

from rest_framework import serializers


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


class CustomerAddressSerializer(StrictSerializer):
    """Validate a bounded postal address."""

    line1 = serializers.CharField(max_length=200, trim_whitespace=True)
    line2 = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=200,
        trim_whitespace=True,
        default=None,
    )
    city = serializers.CharField(max_length=100, trim_whitespace=True)
    region = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
        default=None,
    )
    postal_code = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=30,
        trim_whitespace=True,
        default=None,
    )
    country = serializers.CharField(max_length=100, trim_whitespace=True)

    def validate_line1(self, value):
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_city(self, value):
        if not value:
            raise serializers.ValidationError("This field may not be blank.")
        return value

    def validate_country(self, value):
        if len(value) < 2:
            raise serializers.ValidationError(
                "Use a country name of at least 2 characters."
            )
        return value

    def validate(self, attrs):
        for field in ("line2", "region", "postal_code"):
            if attrs.get(field) == "":
                attrs[field] = None
        return attrs


class CustomerFieldsMixin:
    """Normalize customer identity and contact fields."""

    def validate_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_name(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_email(self, value):
        if value is None:
            return None
        return value.strip().lower() or None

    def validate_phone(self, value):
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if not re.fullmatch(r"\+?[0-9\s().-]+", normalized):
            raise serializers.ValidationError(
                "Use 7 to 15 digits with an optional leading + and common separators."
            )
        digits = re.sub(r"\D", "", normalized)
        if not 7 <= len(digits) <= 15:
            raise serializers.ValidationError(
                "Use a phone number containing 7 to 15 digits."
            )
        return ("+" if normalized.startswith("+") else "") + digits

    def validate_tax_id(self, value):
        if value is None:
            return None
        normalized = value.strip().upper()
        return normalized or None


class CustomerCreateSerializer(CustomerFieldsMixin, StrictSerializer):
    """Validate writable fields for a new customer."""

    code = serializers.CharField(max_length=40, trim_whitespace=True)
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    email = serializers.EmailField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=254,
        default=None,
    )
    phone = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=30,
        default=None,
    )
    billing_address = CustomerAddressSerializer(
        required=False, allow_null=True, default=None
    )
    shipping_address = CustomerAddressSerializer(
        required=False, allow_null=True, default=None
    )
    tax_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
        default=None,
    )
    status = serializers.ChoiceField(
        choices=("active", "inactive"),
        required=False,
        default="active",
    )
    credit_limit = ExactDecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
        default=None,
        coerce_to_string=False,
    )


class CustomerPatchSerializer(CustomerFieldsMixin, StrictSerializer):
    """Validate a non-empty partial customer update."""

    code = serializers.CharField(required=False, max_length=40, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    email = serializers.EmailField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=254,
    )
    phone = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=30,
    )
    billing_address = CustomerAddressSerializer(required=False, allow_null=True)
    shipping_address = CustomerAddressSerializer(required=False, allow_null=True)
    tax_id = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=100,
        trim_whitespace=True,
    )
    status = serializers.ChoiceField(choices=("active", "inactive"), required=False)
    credit_limit = ExactDecimalField(
        max_digits=18,
        decimal_places=2,
        min_value=Decimal("0"),
        required=False,
        allow_null=True,
        coerce_to_string=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class CustomerListQuerySerializer(StrictSerializer):
    """Validate customer search, filters, sorting, and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    status = serializers.ChoiceField(choices=("active", "inactive"), required=False)
    sort_by = serializers.ChoiceField(
        choices=("code", "name", "email", "phone", "status", "created_at", "updated_at"),
        required=False,
    )
    sort_order = serializers.ChoiceField(
        choices=("asc", "desc"),
        required=False,
        default="asc",
    )


class CustomerSalesOrdersQuerySerializer(StrictSerializer):
    """Validate customer sales-order history filters and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    status = serializers.ChoiceField(
        choices=("draft", "confirmed", "fulfilled", "cancelled"),
        required=False,
    )
