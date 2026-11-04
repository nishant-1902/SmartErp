import json
import json
import os
import subprocess
import sys
from pathlib import Path


def test_allowed_hosts_are_loaded_from_environment():
    backend_directory = Path(__file__).resolve().parents[1]
    environment = os.environ.copy()
    environment.update(
        {
            "ALLOWED_HOSTS": "erp.example.test,api.example.test",
            "DJANGO_SETTINGS_MODULE": "config.settings",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, sys; from django.conf import settings; "
            "sys.stdout.write(json.dumps(settings.ALLOWED_HOSTS))",
        ],
        check=True,
        capture_output=True,
        cwd=backend_directory,
        env=environment,
        text=True,
    )

    assert json.loads(result.stdout.splitlines()[-1]) == [
        "erp.example.test",
        "api.example.test",
    ]


def test_production_settings_enforce_secrets_secure_cookies_and_rotating_logs(
    tmp_path,
):
    backend_directory = Path(__file__).resolve().parents[1]
    log_path = tmp_path / "logs" / "production.log"
    environment = os.environ.copy()
    environment.update(
        {
            "ALLOWED_HOSTS": "erp.example.test,api.example.test",
            "CSRF_COOKIE_SECURE": "False",
            "DEBUG": "False",
            "DJANGO_SETTINGS_MODULE": "config.settings",
            "JWT_SECRET_KEY": "jwt-production-secret-" + "x" * 40,
            "LOG_FILE": str(log_path),
            "MONGO_DB_NAME": "smarterp",
            "MONGO_URI": "mongodb://localhost:27017/smarterp",
            "REFRESH_COOKIE_SECURE": "False",
            "SECRET_KEY": "django-production-secret-" + "x" * 40,
            "SECURE_SSL_REDIRECT": "False",
            "SMARTERP_ENV": "production",
            "SESSION_COOKIE_SECURE": "False",
        }
    )
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import json, sys; from django.conf import settings; "
            "data = {name: getattr(settings, name) for name in "
            "('DEBUG', 'ALLOWED_HOSTS', 'REFRESH_COOKIE_SECURE', "
            "'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', "
            "'SECURE_HSTS_SECONDS', 'SECURE_CONTENT_TYPE_NOSNIFF', "
            "'SECURE_REFERRER_POLICY', 'X_FRAME_OPTIONS')}; "
            "data['log_handler'] = settings.LOGGING['handlers']['rotating_file']['class']; "
            "sys.stdout.write(json.dumps(data))",
        ],
        check=True,
        capture_output=True,
        cwd=backend_directory,
        env=environment,
        text=True,
    )

    production = json.loads(result.stdout.splitlines()[-1])
    assert production["DEBUG"] is False
    assert production["ALLOWED_HOSTS"] == [
        "erp.example.test",
        "api.example.test",
    ]
    assert production["REFRESH_COOKIE_SECURE"] is True
    assert production["SESSION_COOKIE_SECURE"] is True
    assert production["CSRF_COOKIE_SECURE"] is True
    assert production["SECURE_HSTS_SECONDS"] == 31_536_000
    assert production["SECURE_CONTENT_TYPE_NOSNIFF"] is True
    assert production["SECURE_REFERRER_POLICY"] == "same-origin"
    assert production["X_FRAME_OPTIONS"] == "DENY"
    assert production["log_handler"] == "logging.handlers.RotatingFileHandler"
    assert log_path.parent.is_dir()


def test_production_settings_reject_debug_and_wildcard_hosts():
    backend_directory = Path(__file__).resolve().parents[1]
    valid_environment = {
        "ALLOWED_HOSTS": "erp.example.test",
        "DEBUG": "False",
        "DJANGO_SETTINGS_MODULE": "config.settings",
        "JWT_SECRET_KEY": "jwt-production-secret-" + "x" * 40,
        "MONGO_DB_NAME": "smarterp",
        "MONGO_URI": "mongodb://localhost:27017/smarterp",
        "SECRET_KEY": "django-production-secret-" + "x" * 40,
        "SMARTERP_ENV": "production",
    }
    for name, value, message in (
        ("DEBUG", "True", "DEBUG must be false in production"),
        ("ALLOWED_HOSTS", "*", "Production ALLOWED_HOSTS"),
    ):
        environment = os.environ.copy()
        environment.update(valid_environment)
        environment[name] = value
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                "from django.conf import settings; settings.DEBUG",
            ],
            capture_output=True,
            cwd=backend_directory,
            env=environment,
            text=True,
        )

        assert result.returncode != 0
        assert message in result.stderr
