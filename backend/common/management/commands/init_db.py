"""Initialize MongoDB application collections, validators, and indexes."""

from collections.abc import Callable
from typing import Any

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from pymongo import MongoClient
from pymongo.database import Database
from pymongo.errors import CollectionInvalid

from database.indexes import COLLECTIONS


def initialize_database(
    database: Database[Any],
    write: Callable[[str], None],
) -> None:
    """Create missing collections and idempotently ensure validators and indexes."""
    existing_collections = set(database.list_collection_names())

    for collection_name, definition in COLLECTIONS.items():
        if collection_name not in existing_collections:
            try:
                database.create_collection(
                    collection_name,
                    validator=definition.validator,
                    validationLevel="strict",
                    validationAction="error",
                )
                write(f"Created collection: {collection_name}")
            except CollectionInvalid:
                if collection_name not in database.list_collection_names():
                    raise
                write(f"Collection already exists: {collection_name}")
            existing_collections.add(collection_name)
        else:
            database.command(
                {
                    "collMod": collection_name,
                    "validator": definition.validator,
                    "validationLevel": "strict",
                    "validationAction": "error",
                }
            )
            write(f"Updated validator: {collection_name}")

        collection = database[collection_name]
        existing_indexes = collection.index_information()
        for index in definition.indexes:
            options: dict[str, Any] = {"name": index.name, "unique": index.unique}
            if index.partial_filter_expression is not None:
                options["partialFilterExpression"] = index.partial_filter_expression
            if index.expire_after_seconds is not None:
                options["expireAfterSeconds"] = index.expire_after_seconds
            collection.create_index(list(index.keys), **options)
            action = (
                "Already present"
                if index.name in existing_indexes
                else "Created index"
            )
            write(f"{action}: {collection_name}.{index.name}")


class Command(BaseCommand):
    """Create or update SmartERP's MongoDB collections and indexes."""

    help = "Create or update SmartERP MongoDB collections, validators, and indexes."

    def handle(self, *args: Any, **options: Any) -> None:
        mongo_uri = getattr(settings, "MONGO_URI", "")
        database_name = getattr(settings, "MONGO_DB_NAME", "")
        if not mongo_uri:
            raise CommandError("MONGO_URI is not configured.")
        if not database_name:
            raise CommandError("MONGO_DB_NAME is not configured.")

        try:
            with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
                client.admin.command("ping")
                database = client[database_name]
                initialize_database(database, self.stdout.write)
        except Exception as exc:
            raise CommandError(f"MongoDB initialization failed: {exc}") from exc

        self.stdout.write(self.style.SUCCESS("MongoDB initialization complete."))
