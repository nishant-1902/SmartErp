"""Django settings for the SmartERP API."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _env_bool(name: str, default: bool = False) -> bool:
    """Read a boolean environment setting."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int) -> int:
    """Read an integer environment setting."""
    value = os.getenv(name)
    return int(value) if value is not None else default


def _env_csv(name: str, default: str = "") -> list[str]:
    """Read a comma-separated environment setting."""
    values = os.getenv(name, default).split(",")
    return [item.strip() for item in values if item.strip()]


SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = _env_bool("DEBUG")
ALLOWED_HOSTS = _env_csv("ALLOWED_HOSTS")

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "smarterp")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
JWT_ISSUER = os.getenv("JWT_ISSUER", "smarterp-api")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "smarterp-client")
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = _env_int(
    "JWT_ACCESS_TOKEN_LIFETIME_SECONDS", 900
)
JWT_REFRESH_TOKEN_LIFETIME_SECONDS = _env_int(
    "JWT_REFRESH_TOKEN_LIFETIME_SECONDS", 604800
)

CORS_ALLOWED_ORIGINS = _env_csv("CORS_ALLOWED_ORIGINS")
CORS_ALLOW_CREDENTIALS = True

REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "smarterp_refresh")
REFRESH_COOKIE_SECURE = _env_bool("REFRESH_COOKIE_SECURE")
REFRESH_COOKIE_HTTPONLY = _env_bool("REFRESH_COOKIE_HTTPONLY", True)
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_PATH = os.getenv("REFRESH_COOKIE_PATH", "/api/auth/")
REFRESH_COOKIE_DOMAIN = os.getenv("REFRESH_COOKIE_DOMAIN") or None

INSTALLED_APPS = [
    "rest_framework",
    "corsheaders",
    "common.apps.CommonConfig",
    "accounts.apps.AccountsConfig",
    "employees.apps.EmployeesConfig",
    "departments.apps.DepartmentsConfig",
    "inventory.apps.InventoryConfig",
    "suppliers.apps.SuppliersConfig",
    "purchases.apps.PurchasesConfig",
    "customers.apps.CustomersConfig",
    "sales.apps.SalesConfig",
    "reports.apps.ReportsConfig",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.dummy",
    }
}

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    "UNAUTHENTICATED_USER": None,
    "UNAUTHENTICATED_TOKEN": None,
    # Replace with the shared envelope handler when common exceptions are added.
    "EXCEPTION_HANDLER": "rest_framework.views.exception_handler",
    # Authentication and deny-by-default permissions are added in Phase 3.
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "DEFAULT_PERMISSION_CLASSES": [],
}

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True
BUSINESS_TIMEZONE = "Asia/Kolkata"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
