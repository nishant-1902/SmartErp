"""DRF serializers for the auth endpoints."""

from collections.abc import Mapping

from rest_framework import serializers

from accounts.repository import USER_ROLES
from accounts.passwords import validate_password_strength
from common.exceptions import ValidationFailed
from common.object_id import parse_object_id


class StrictSerializer(serializers.Serializer):
    """Reject undeclared or unsafe keys instead of silently ignoring them."""

    def to_internal_value(self, data):
        if isinstance(data, Mapping):
            unknown_fields = set(data) - set(self.fields)
            unsafe_fields = {
                field
                for field in data
                if isinstance(field, str) and (field.startswith("$") or "." in field)
            }
            if unknown_fields or unsafe_fields:
                raise serializers.ValidationError(
                    {
                        "fields": (
                            "Unsupported or unsafe fields: "
                            + ", ".join(sorted(unknown_fields | unsafe_fields))
                        )
                    }
                )
        return super().to_internal_value(data)


class UserCreateSerializer(StrictSerializer):
    """Validate a new user and enforce password strength against their email."""

    email = serializers.EmailField(max_length=254)
    password = serializers.CharField(
        write_only=True,
        trim_whitespace=False,
        min_length=10,
        max_length=128,
    )
    full_name = serializers.CharField(max_length=200, trim_whitespace=True)
    role = serializers.ChoiceField(choices=sorted(USER_ROLES))
    employee_id = serializers.CharField(
        required=False,
        allow_null=True,
        trim_whitespace=True,
    )

    def validate_employee_id(self, value):
        if value is None:
            return None
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate(self, attrs):
        try:
            validate_password_strength(attrs["password"], attrs["email"])
        except ValidationFailed as exc:
            raise serializers.ValidationError(
                {"password": str(exc.detail)}
            ) from exc
        return attrs


class UserPatchSerializer(StrictSerializer):
    """Validate the allowlisted editable user fields."""

    email = serializers.EmailField(max_length=254, required=False)
    full_name = serializers.CharField(
        max_length=200,
        required=False,
        trim_whitespace=True,
    )
    role = serializers.ChoiceField(choices=sorted(USER_ROLES), required=False)
    employee_id = serializers.CharField(
        required=False,
        allow_null=True,
        trim_whitespace=True,
    )

    def validate_employee_id(self, value):
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


class UserListQuerySerializer(StrictSerializer):
    """Validate user-list filters and pagination query parameters."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    search = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
        default=None,
    )
    role = serializers.ChoiceField(
        choices=sorted(USER_ROLES),
        required=False,
        default=None,
    )
    is_active = serializers.BooleanField(
        required=False,
        allow_null=True,
        default=None,
    )


class AuditLogQuerySerializer(StrictSerializer):
    """Validate audit-log filtering and pagination query parameters."""

    page = serializers.IntegerField(min_value=1, required=False, default=1)
    page_size = serializers.IntegerField(min_value=1, max_value=100, required=False, default=20)
    user = serializers.CharField(
        required=False,
        trim_whitespace=True,
        default=None,
    )
    action = serializers.CharField(
        max_length=100,
        required=False,
        allow_blank=False,
        default=None,
    )
    start_date = serializers.DateTimeField(required=False, default=None)
    end_date = serializers.DateTimeField(required=False, default=None)

    def validate_user(self, value):
        try:
            return parse_object_id(value)
        except ValidationFailed as exc:
            raise serializers.ValidationError("Must be a valid ObjectId.") from exc

    def validate(self, attrs):
        start_date = attrs.get("start_date")
        end_date = attrs.get("end_date")
        if start_date is not None and end_date is not None and start_date > end_date:
            raise serializers.ValidationError(
                {"end_date": "Must be later than or equal to start_date."}
            )
        return attrs


class EmptyActionSerializer(StrictSerializer):
    """Reject unexpected payloads on state-transition actions."""


class EmailPasswordSerializer(serializers.Serializer):
    """Validate email and password payloads for auth endpoints."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, trim_whitespace=True)


class ChangePasswordSerializer(serializers.Serializer):
    """Validate the old and new password for a password change."""

    old_password = serializers.CharField(write_only=True, trim_whitespace=True)
    new_password = serializers.CharField(write_only=True, trim_whitespace=True)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        email = self.initial_data.get("email")
        if email is not None:
            try:
                validate_password_strength(attrs["new_password"], str(email))
            except ValidationFailed as exc:
                raise serializers.ValidationError({"new_password": str(exc.detail)}) from exc
        return attrs


class PasswordResetRequestSerializer(serializers.Serializer):
    """Validate a password-reset request."""

    email = serializers.EmailField()


class PasswordResetConfirmSerializer(serializers.Serializer):
    """Validate a password reset confirmation."""

    email = serializers.EmailField()
    token = serializers.CharField(trim_whitespace=True)
    password = serializers.CharField(write_only=True, trim_whitespace=True)
    confirm_password = serializers.CharField(write_only=True, trim_whitespace=True)

    def validate(self, attrs):
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})
        try:
            validate_password_strength(attrs["password"], attrs["email"])
        except ValidationFailed as exc:
            raise serializers.ValidationError({"password": str(exc.detail)}) from exc
        return attrs
