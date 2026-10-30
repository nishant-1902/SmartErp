"""Strict request serializers for department endpoints."""

from collections.abc import Mapping

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


class DepartmentCreateSerializer(StrictSerializer):
    """Validate all writable fields for a new department."""

    code = serializers.CharField(max_length=40, trim_whitespace=True)
    name = serializers.CharField(max_length=120, trim_whitespace=True)
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=2000,
        default=None,
    )
    manager_employee_id = serializers.CharField(
        required=False,
        allow_null=True,
        trim_whitespace=True,
        default=None,
    )
    is_active = serializers.BooleanField(required=False, default=True)

    def validate_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value.strip()

    def validate_manager_employee_id(self, value):
        if value is None:
            return None
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc


class DepartmentPatchSerializer(StrictSerializer):
    """Validate a non-empty partial department update."""

    code = serializers.CharField(max_length=40, required=False, trim_whitespace=True)
    name = serializers.CharField(max_length=120, required=False, trim_whitespace=True)
    description = serializers.CharField(
        required=False,
        allow_null=True,
        allow_blank=True,
        trim_whitespace=True,
        max_length=2000,
    )
    manager_employee_id = serializers.CharField(
        required=False,
        allow_null=True,
        trim_whitespace=True,
    )
    is_active = serializers.BooleanField(required=False)

    def validate_code(self, value):
        normalized = value.strip().upper()
        if not normalized:
            raise serializers.ValidationError("This field may not be blank.")
        return normalized

    def validate_name(self, value):
        if not value.strip():
            raise serializers.ValidationError("This field may not be blank.")
        return value.strip()

    def validate_manager_employee_id(self, value):
        if value is None:
            return None
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate(self, attrs):
        if not attrs:
            raise serializers.ValidationError("At least one editable field is required.")
        return attrs


class DepartmentListQuerySerializer(StrictSerializer):
    """Validate department search, sorting, filters, and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
    )
    sort_by = serializers.ChoiceField(
        choices=("code", "name", "created_at", "updated_at", "is_active"),
        required=False,
    )
    sort_order = serializers.ChoiceField(
        choices=("asc", "desc"),
        required=False,
        default="asc",
    )


class DepartmentEmployeesQuerySerializer(StrictSerializer):
    """Validate employee search, sorting, and pagination."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(max_length=100, required=False, allow_blank=False)
    sort_by = serializers.ChoiceField(
        choices=(
            "employee_code",
            "first_name",
            "last_name",
            "email",
            "designation",
            "joining_date",
            "status",
            "created_at",
        ),
        required=False,
    )
    sort_order = serializers.ChoiceField(
        choices=("asc", "desc"),
        required=False,
        default="asc",
    )
