"""Strict request serializers for employee endpoints."""

from collections.abc import Mapping
import re

from rest_framework import serializers

from common.exceptions import ValidationFailed
from common.object_id import parse_object_id
from common.time import utc_now


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


class EmployeeFieldsMixin:
    """Shared field validation and normalization for employee write serializers."""

    def validate_employee_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_first_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value.strip()

    def validate_last_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value.strip()

    def validate_email(self, value):
        return value.strip().lower()

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

    def validate_department_id(self, value):
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate_designation(self, value):
        normalized = value.strip()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_joining_date(self, value):
        if value > utc_now().date():
            raise serializers.ValidationError("Joining date cannot be in the future.")
        return value


class EmployeeCreateSerializer(EmployeeFieldsMixin, StrictSerializer):
    """Validate all writable fields required to create an employee."""

    employee_code = serializers.CharField(max_length=40, trim_whitespace=True)
    first_name = serializers.CharField(max_length=100, trim_whitespace=True)
    last_name = serializers.CharField(max_length=100, trim_whitespace=True)
    email = serializers.EmailField(max_length=254)
    phone = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=30,
        default=None,
    )
    department_id = serializers.CharField(trim_whitespace=True)
    designation = serializers.CharField(max_length=100, trim_whitespace=True)
    joining_date = serializers.DateField(input_formats=["%Y-%m-%d"])
    status = serializers.ChoiceField(
        choices=("active", "inactive", "on_leave"),
        required=False,
        default="active",
    )


class EmployeePatchSerializer(EmployeeFieldsMixin, StrictSerializer):
    """Validate the allowlisted mutable fields for an employee."""

    first_name = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    last_name = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    email = serializers.EmailField(max_length=254, required=False)
    phone = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=30,
    )
    department_id = serializers.CharField(required=False, trim_whitespace=True)
    designation = serializers.CharField(
        max_length=100,
        required=False,
        trim_whitespace=True,
    )
    joining_date = serializers.DateField(
        input_formats=["%Y-%m-%d"],
        required=False,
    )
    status = serializers.ChoiceField(
        choices=("active", "inactive", "on_leave"),
        required=False,
    )

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class EmployeeListQuerySerializer(StrictSerializer):
    """Validate employee list filters, search, pagination, and sort."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    department_id = serializers.CharField(required=False, trim_whitespace=True)
    status = serializers.ChoiceField(
        choices=("active", "inactive", "on_leave"),
        required=False,
    )
    sort_by = serializers.ChoiceField(
        choices=(
            "employee_code",
            "first_name",
            "last_name",
            "email",
            "department_id",
            "designation",
            "joining_date",
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

    def validate_department_id(self, value):
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc


class EmptyActionSerializer(StrictSerializer):
    """Reject unexpected bodies for action endpoints."""
