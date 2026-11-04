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
            "import json; from django.conf import settings; "
            "print(json.dumps(settings.ALLOWED_HOSTS))",
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
