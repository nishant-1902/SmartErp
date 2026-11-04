"""Print an expired access token for a known SmartERP user account."""

import argparse
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

from pymongo import MongoClient
from pymongo.errors import PyMongoError

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
sys.path.insert(0, str(BACKEND_DIR.parent))

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")


def parse_arguments() -> argparse.Namespace:
    """Parse the one user identifier required by this development utility."""
    parser = argparse.ArgumentParser(
        description=(
            "Print an already-expired access JWT for a user in the configured "
            "MongoDB database. Use only with a local development environment."
        )
    )
    user_selector = parser.add_mutually_exclusive_group(required=True)
    user_selector.add_argument("--email", help="Email address of the target user")
    user_selector.add_argument("--user-id", help="MongoDB ObjectId of the target user")
    return parser.parse_args()


def main() -> int:
    """Load a user and print a token whose expiry is already in the past."""
    import django

    django.setup()

    from django.conf import settings

    from accounts.repository import find_user_by_email, find_user_by_id
    from accounts.tokens import create_access_token
    from common.exceptions import ValidationFailed
    from common.object_id import parse_object_id

    arguments = parse_arguments()
    if not settings.MONGO_URI or not settings.MONGO_DB_NAME:
        print("MONGO_URI and MONGO_DB_NAME must be configured.", file=sys.stderr)
        return 2

    try:
        with MongoClient(
            settings.MONGO_URI,
            serverSelectionTimeoutMS=5000,
        ) as client:
            database = client[settings.MONGO_DB_NAME]
            if arguments.email:
                user = find_user_by_email(database, arguments.email)
            else:
                user = find_user_by_id(database, parse_object_id(arguments.user_id))
    except PyMongoError:
        print("Could not connect to the configured MongoDB database.", file=sys.stderr)
        return 2
    except ValidationFailed as exc:
        print(f"Invalid user identifier: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(f"Invalid user identifier: {exc}", file=sys.stderr)
        return 2

    if user is None:
        print("No matching user was found.", file=sys.stderr)
        return 1
    if user.get("is_active") is not True:
        print("The selected user is inactive.", file=sys.stderr)
        return 1

    lifetime_seconds = settings.JWT_ACCESS_TOKEN_LIFETIME_SECONDS
    if (
        not settings.JWT_SECRET_KEY
        or not settings.JWT_ISSUER
        or not settings.JWT_AUDIENCE
        or lifetime_seconds <= 0
    ):
        print(
            "JWT signing settings and a positive lifetime must be configured.",
            file=sys.stderr,
        )
        return 2

    issued_at = datetime.now(timezone.utc) - timedelta(
        seconds=lifetime_seconds + 60
    )
    print(create_access_token(user, now=issued_at))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
