"""Print every resolved Django URL pattern, including included URLconfs."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Iterable

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import django

django.setup()

from django.urls import URLPattern, URLResolver, get_resolver


def walk(patterns: Iterable[URLPattern | URLResolver], prefix: str = "") -> None:
    """Print route paths in resolver order, including nested URL patterns."""
    for pattern in patterns:
        route = prefix + str(pattern.pattern)
        if isinstance(pattern, URLResolver):
            walk(pattern.url_patterns, route)
        else:
            print(route)


if __name__ == "__main__":
    walk(get_resolver().url_patterns)
