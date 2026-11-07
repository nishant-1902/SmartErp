from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings


@override_settings(
    MONGO_URI="mongodb://localhost:27017",
    MONGO_DB_NAME="smarterp_test",
    SMARTERP_ENV="development",
)
def test_backfill_updates_derived_stock_values():
    products = MagicMock()
    products.update_many.return_value = SimpleNamespace(modified_count=12)
    client = MagicMock()
    client.__enter__.return_value = client
    client.__getitem__.return_value.__getitem__.return_value = products

    with patch(
        "common.management.commands.backfill_stock_index_fields.MongoClient",
        return_value=client,
    ):
        call_command("backfill_stock_index_fields", verbosity=0)

    client.admin.command.assert_called_once_with("ping")
    query, pipeline = products.update_many.call_args.args
    assert query == {}
    assert pipeline[0]["$set"]["available_quantity"] == {
        "$subtract": ["$quantity_on_hand", "$reserved_quantity"]
    }
    assert pipeline[0]["$set"]["is_low_stock"]["$lte"][1] == "$min_stock_level"


@override_settings(
    MONGO_URI="mongodb://localhost:27017",
    MONGO_DB_NAME="smarterp",
    SMARTERP_ENV="production",
)
def test_backfill_requires_production_confirmation():
    with pytest.raises(CommandError, match="--confirm-production"):
        call_command("backfill_stock_index_fields", verbosity=0)
