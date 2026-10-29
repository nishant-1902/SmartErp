"""Create a super-admin account directly in MongoDB."""

from getpass import getpass
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from pymongo import MongoClient
from pymongo.errors import DuplicateKeyError, PyMongoError

from accounts.passwords import hash_password, validate_password_strength
from accounts.repository import create_user, find_user_by_email, normalize_email
from common.exceptions import ValidationFailed


class Command(BaseCommand):
    """Interactively create a MongoDB-backed super-admin account."""

    help = "Create a super-admin user in MongoDB."

    def handle(self, *args: Any, **options: Any) -> None:
        mongo_uri = getattr(settings, "MONGO_URI", "")
        database_name = getattr(settings, "MONGO_DB_NAME", "")
        if not mongo_uri:
            raise CommandError("MONGO_URI is not configured.")
        if not database_name:
            raise CommandError("MONGO_DB_NAME is not configured.")

        try:
            email = normalize_email(input("Email: "))
        except ValueError as exc:
            raise CommandError("Email must not be empty.") from exc
        full_name = input("Full name: ").strip()
        if not full_name:
            raise CommandError("Full name must not be empty.")
        password = getpass("Password: ")
        confirmation = getpass("Confirm password: ")
        if password != confirmation:
            raise CommandError("The passwords do not match.")
        try:
            validate_password_strength(password, email)
        except ValidationFailed as exc:
            raise CommandError(str(exc.detail)) from exc

        try:
            with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
                client.admin.command("ping")
                database = client[database_name]
                if find_user_by_email(database, email) is not None:
                    raise CommandError("A user with that email already exists.")
                create_user(
                    database,
                    email=email,
                    password_hash=hash_password(password),
                    full_name=full_name,
                    role="super_admin",
                )
        except DuplicateKeyError as exc:
            raise CommandError("A user with that email already exists.") from exc
        except PyMongoError as exc:
            raise CommandError(
                "MongoDB operation failed; check the connection and database permissions."
            ) from exc

        self.stdout.write(self.style.SUCCESS("Super-admin account created."))
