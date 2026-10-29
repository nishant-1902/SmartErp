from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import override_settings

from tests.accounts.fakes import FakeDatabase


class FakeMongoClient:
    """Provide the small MongoClient interface used by the command."""

    def __init__(self, database):
        self.database = database
        self.admin = self

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def command(self, name):
        assert name == "ping"

    def __getitem__(self, name):
        assert name == "smarterp"
        return self.database


@override_settings(MONGO_URI="mongodb://localhost", MONGO_DB_NAME="smarterp")
def test_create_superuser_mongo_reads_credentials_and_creates_super_admin():
    database = FakeDatabase()
    stdout = StringIO()
    with (
        patch(
            "accounts.management.commands.create_superuser_mongo.MongoClient",
            return_value=FakeMongoClient(database),
        ),
        patch("builtins.input", side_effect=["ADMIN@example.com", "Example Admin"]),
        patch(
            "accounts.management.commands.create_superuser_mongo.getpass",
            side_effect=["violet-river-planet-482", "violet-river-planet-482"],
        ),
    ):
        call_command("create_superuser_mongo", stdout=stdout)

    user = database["users"].find_one({"email": "admin@example.com"})
    assert user is not None
    assert user["role"] == "super_admin"
    assert user["password_hash"] != "violet-river-planet-482"
    assert "Super-admin account created." in stdout.getvalue()
