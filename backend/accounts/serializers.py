"""DRF serializers for the auth endpoints."""

from rest_framework import serializers

from accounts.passwords import validate_password_strength
from common.exceptions import ValidationFailed


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
