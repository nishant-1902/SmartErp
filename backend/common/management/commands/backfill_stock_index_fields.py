"""Backfill product stock values used by low-stock indexes."""

from typing import Any

from django.conf import settings
from django.core.management import BaseCommand, CommandError
from pymongo import MongoClient


class Command(BaseCommand):
    """Recalculate materialized product availability and low-stock values."""

    help = (
        "Backfill products.available_quantity and products.is_low_stock "
        "before deploying indexed low-stock queries."
    )

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--confirm-production",
            action="store_true",
            help="Required when running against a production database.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        mongo_uri = getattr(settings, "MONGO_URI", "")
        database_name = getattr(settings, "MONGO_DB_NAME", "")
        if not mongo_uri or not database_name:
            raise CommandError("MONGO_URI and MONGO_DB_NAME must be configured.")
        if (
            settings.SMARTERP_ENV == "production"
            and not options["confirm_production"]
        ):
            raise CommandError(
                "Production backfill requires --confirm-production."
            )

        with MongoClient(mongo_uri, serverSelectionTimeoutMS=5000) as client:
            client.admin.command("ping")
            result = client[database_name]["products"].update_many(
                {},
                [
                    {
                        "$set": {
                            "available_quantity": {
                                "$subtract": [
                                    "$quantity_on_hand",
                                    "$reserved_quantity",
                                ]
                            },
                            "is_low_stock": {
                                "$lte": [
                                    {
                                        "$subtract": [
                                            "$quantity_on_hand",
                                            "$reserved_quantity",
                                        ]
                                    },
                                    "$min_stock_level",
                                ]
                            },
                        }
                    }
                ],
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"Backfilled stock fields for {result.modified_count} product(s)."
            )
        )
