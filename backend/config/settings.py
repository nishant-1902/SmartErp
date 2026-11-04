"""Django settings for the SmartERP API."""

import os
from pathlib import Path

from corsheaders.defaults import default_headers
from dotenv import load_dotenv
from django.core.exceptions import ImproperlyConfigured

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


SMARTERP_ENV = os.getenv("SMARTERP_ENV", "development").strip().lower()
if SMARTERP_ENV not in {"development", "production"}:
    raise ImproperlyConfigured(
        "SMARTERP_ENV must be either 'development' or 'production'."
    )
IS_PRODUCTION = SMARTERP_ENV == "production"

SECRET_KEY = os.getenv("SECRET_KEY", "")
DEBUG = _env_bool("DEBUG", default=not IS_PRODUCTION)
if IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DEBUG must be false in production.")
ALLOWED_HOSTS = _env_csv("ALLOWED_HOSTS", "localhost,127.0.0.1")
if IS_PRODUCTION:
    if not ALLOWED_HOSTS or "*" in ALLOWED_HOSTS:
        raise ImproperlyConfigured(
            "Production ALLOWED_HOSTS must contain explicit hostnames."
        )
    if len(SECRET_KEY) < 50 or SECRET_KEY.startswith("replace-with-"):
        raise ImproperlyConfigured(
            "Production SECRET_KEY must be a unique value of at least 50 characters."
        )

MONGO_URI = os.getenv("MONGO_URI", "")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "smarterp")
MONGO_TEST_URI = os.getenv("MONGO_TEST_URI", "")
MONGO_TEST_DB_NAME = os.getenv("MONGO_TEST_DB_NAME", "smarterp_test")
if IS_PRODUCTION and (not MONGO_URI or not MONGO_DB_NAME):
    raise ImproperlyConfigured(
        "Production MONGO_URI and MONGO_DB_NAME must be configured."
    )

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "")
if IS_PRODUCTION and (
    len(JWT_SECRET_KEY) < 32 or JWT_SECRET_KEY.startswith("replace-with-")
):
    raise ImproperlyConfigured(
        "Production JWT_SECRET_KEY must be a unique value of at least 32 characters."
    )
JWT_ISSUER = os.getenv("JWT_ISSUER", "smarterp-api")
JWT_AUDIENCE = os.getenv("JWT_AUDIENCE", "smarterp-client")
JWT_ACCESS_TOKEN_LIFETIME_SECONDS = _env_int(
    "JWT_ACCESS_TOKEN_LIFETIME_SECONDS", 900
)
JWT_REFRESH_TOKEN_LIFETIME_SECONDS = _env_int(
    "JWT_REFRESH_TOKEN_LIFETIME_SECONDS", 604800
)

CORS_ALLOWED_ORIGINS = _env_csv("CORS_ALLOWED_ORIGINS")
if "*" in CORS_ALLOWED_ORIGINS:
    raise ValueError("CORS_ALLOWED_ORIGINS must contain exact origins, not '*'.")
CORS_ALLOW_CREDENTIALS = True
CORS_ALLOW_HEADERS = (*default_headers, "idempotency-key")

REFRESH_COOKIE_NAME = os.getenv("REFRESH_COOKIE_NAME", "smarterp_refresh")
REFRESH_COOKIE_SECURE = IS_PRODUCTION or _env_bool("REFRESH_COOKIE_SECURE")
REFRESH_COOKIE_HTTPONLY = _env_bool("REFRESH_COOKIE_HTTPONLY", True)
REFRESH_COOKIE_SAMESITE = os.getenv("REFRESH_COOKIE_SAMESITE", "Lax")
REFRESH_COOKIE_PATH = os.getenv("REFRESH_COOKIE_PATH", "/api/auth/")
REFRESH_COOKIE_DOMAIN = os.getenv("REFRESH_COOKIE_DOMAIN") or None
SESSION_COOKIE_SECURE = IS_PRODUCTION
CSRF_COOKIE_SECURE = IS_PRODUCTION

SECURE_SSL_REDIRECT = _env_bool("SECURE_SSL_REDIRECT", IS_PRODUCTION)
SECURE_HSTS_SECONDS = _env_int(
    "SECURE_HSTS_SECONDS",
    31_536_000 if IS_PRODUCTION else 0,
)
if IS_PRODUCTION and SECURE_HSTS_SECONDS <= 0:
    raise ImproperlyConfigured(
        "Production SECURE_HSTS_SECONDS must be greater than zero."
    )
SECURE_HSTS_INCLUDE_SUBDOMAINS = _env_bool(
    "SECURE_HSTS_INCLUDE_SUBDOMAINS",
    IS_PRODUCTION,
)
SECURE_HSTS_PRELOAD = _env_bool("SECURE_HSTS_PRELOAD")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
SECURE_PROXY_SSL_HEADER = (
    ("HTTP_X_FORWARDED_PROTO", "https")
    if _env_bool("TRUST_X_FORWARDED_PROTO")
    else None
)

LOG_FILE = Path(
    os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "smarterp.log"))
).resolve()
if IS_PRODUCTION:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "standard": {
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "standard",
            },
            "rotating_file": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": str(LOG_FILE),
                "maxBytes": _env_int("LOG_MAX_BYTES", 10_485_760),
                "backupCount": _env_int("LOG_BACKUP_COUNT", 5),
                "encoding": "utf-8",
                "formatter": "standard",
            },
        },
        "root": {
            "handlers": ["console", "rotating_file"],
            "level": os.getenv("LOG_LEVEL", "INFO").upper(),
        },
    }
else:
    LOGGING = {
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
            },
        },
        "root": {
            "handlers": ["console"],
            "level": os.getenv("LOG_LEVEL", "INFO").upper(),
        },
    }

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
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
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
    "EXCEPTION_HANDLER": "common.exceptions.api_exception_handler",
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "accounts.authentication.MongoJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "common.permissions.IsAuthenticatedMongo",
    ],
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
