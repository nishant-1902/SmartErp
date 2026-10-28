from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import override_settings
from pymongo.errors import CollectionInvalid

from common.management.commands.init_db import initialize_database
from database.indexes import COLLECTIONS


class FakeCollection:
    def __init__(self):
        self.indexes = {"_id_": {"key": [("_id", 1)]}}
        self.created_indexes = []

    def index_information(self):
        return self.indexes.copy()

    def create_index(self, keys, **options):
        self.created_indexes.append((keys, options))
        name = options["name"]
        self.indexes[name] = {"key": keys, **options}
        return name


class FakeDatabase:
    def __init__(self):
        self.collections = {}
        self.created_collections = []
        self.commands = []
        self.options = {}

    def list_collection_names(self):
        return list(self.collections)

    def create_collection(self, name, **options):
        if name in self.collections:
            raise CollectionInvalid(name)
        self.collections[name] = FakeCollection()
        self.created_collections.append((name, options))
        self.options[name] = {
            "validator": options["validator"],
            "validationLevel": options["validationLevel"],
            "validationAction": options["validationAction"],
        }
        return self.collections[name]

    def list_collections(self):
        return [
            {"name": name, "options": options}
            for name, options in self.options.items()
        ]

    def command(self, command):
        self.commands.append(command)
        return {"ok": 1}

    def __getitem__(self, name):
        return self.collections[name]


def test_initialize_database_creates_collections_validators_and_indexes():
    database = FakeDatabase()
    output = []

    initialize_database(database, output.append)

    assert set(database.collections) == set(COLLECTIONS)
    assert len(database.created_collections) == len(COLLECTIONS)
    assert not database.commands
    assert all(
        options["validationLevel"] == "strict"
        and options["validationAction"] == "error"
        for _, options in database.created_collections
    )
    assert any(line.startswith("Created collection: users") for line in output)
    assert any(
        line.startswith("Created index: users.uq_users_email") for line in output
    )


def test_initialize_database_is_repeatable_without_modifying_current_validators():
    database = FakeDatabase()
    output = []
    initialize_database(database, output.append)
    first_index_count = sum(
        len(collection.created_indexes) for collection in database.collections.values()
    )

    output.clear()
    initialize_database(database, output.append)

    second_index_count = sum(
        len(collection.created_indexes) for collection in database.collections.values()
    )
    assert second_index_count == first_index_count * 2
    assert not database.commands
    assert any(line.startswith("Validator already current: users") for line in output)
    assert any(
        line.startswith("Already present: users.uq_users_email") for line in output
    )


def test_initialize_database_updates_a_stale_validator():
    database = FakeDatabase()
    initialize_database(database, lambda _: None)
    database.options["users"]["validator"] = {}

    initialize_database(database, lambda _: None)

    assert any(command.get("collMod") == "users" for command in database.commands)


@override_settings(MONGO_URI="", MONGO_DB_NAME="smarterp")
def test_command_requires_mongo_uri():
    with pytest.raises(CommandError, match="MONGO_URI is not configured"):
        call_command("init_db")


@override_settings(MONGO_URI="mongodb://localhost:27017", MONGO_DB_NAME="smarterp")
def test_command_pings_database_and_runs_initialization():
    database = FakeDatabase()
    client = FakeClient(database)

    with patch("common.management.commands.init_db.MongoClient", return_value=client):
        call_command("init_db", verbosity=0)

    assert client.admin.commands == ["ping"]
    assert set(database.collections) == set(COLLECTIONS)


class FakeAdmin:
    def __init__(self):
        self.commands = []

    def command(self, name):
        self.commands.append(name)
        return {"ok": 1}


class FakeClient:
    def __init__(self, database):
        self.admin = FakeAdmin()
        self.database = database
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.closed = True

    def __getitem__(self, name):
        assert name == "smarterp"
        return self.database
