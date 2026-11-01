"""Strict request serializers for supplier endpoints."""

from collections.abc import Mapping
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


class SupplierAddressSerializer(StrictSerializer):
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
            raise serializers.ValidationError("Use a country name of at least 2 characters.")
        return value

    def validate(self, attrs):
        for field in ("line2", "region", "postal_code"):
            if attrs.get(field) == "":
                attrs[field] = None
        return attrs


class SupplierFieldsMixin:
    """Normalize and validate supplier contact fields."""

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

    def validate_contact_person(self, value):
        return value.strip() or None if value is not None else None

    def validate_email(self, value):
        return value.strip().lower() or None if value is not None else None

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

    def validate_payment_terms(self, value):
        return value.strip() or None if value is not None else None


class SupplierCreateSerializer(SupplierFieldsMixin, StrictSerializer):
    """Validate all writable fields for a new supplier."""

    code = serializers.CharField(required=False, max_length=40, trim_whitespace=True)
    name = serializers.CharField(max_length=200, trim_whitespace=True)
    contact_person = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=150,
        trim_whitespace=True,
        default=None,
    )
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
    address = SupplierAddressSerializer(required=False, allow_null=True, default=None)
    status = serializers.ChoiceField(
        choices=("active", "inactive"),
        required=False,
        default="active",
    )
    payment_terms = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
        default=None,
    )


class SupplierPatchSerializer(SupplierFieldsMixin, StrictSerializer):
    """Validate a non-empty partial supplier update."""

    code = serializers.CharField(required=False, max_length=40, trim_whitespace=True)
    name = serializers.CharField(required=False, max_length=200, trim_whitespace=True)
    contact_person = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=150,
        trim_whitespace=True,
    )
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
    address = SupplierAddressSerializer(required=False, allow_null=True)
    status = serializers.ChoiceField(choices=("active", "inactive"), required=False)
    payment_terms = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        max_length=500,
        trim_whitespace=True,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class SupplierListQuerySerializer(StrictSerializer):
    """Validate supplier search, status filter, sorting, and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    status = serializers.ChoiceField(
        choices=("active", "inactive"),
        required=False,
    )
    sort_by = serializers.ChoiceField(
        choices=(
            "code",
            "name",
            "contact_person",
            "email",
            "status",
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


class SupplierPurchaseOrdersQuerySerializer(StrictSerializer):
    """Validate pagination for supplier purchase-order lists."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
