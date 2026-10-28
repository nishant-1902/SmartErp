import pytest

from tests.conftest import validate_test_mongo_configuration

VALID_URI = (
    "mongodb://smarterp_test_user:encoded%40password@localhost:27017/"
    "smarterp_test?replicaSet=rs0&authSource=smarterp_test"
)


def test_accepts_the_dedicated_test_database_and_replica_set():
    validate_test_mongo_configuration(VALID_URI, "smarterp_test")


@pytest.mark.parametrize(
    ("uri", "database_name", "message"),
    [
        (VALID_URI, "smarterp", "MONGO_TEST_DB_NAME must be exactly"),
        (
            VALID_URI.replace("/smarterp_test?", "/smarterp?"),
            "smarterp_test",
            "MONGO_TEST_URI must select database",
        ),
        (
            VALID_URI.replace("smarterp_test_user", "smarterp_app"),
            "smarterp_test",
            "MONGO_TEST_URI must authenticate as",
        ),
        (
            VALID_URI.replace("replicaSet=rs0", "replicaSet=other"),
            "smarterp_test",
            "must include replicaSet=rs0",
        ),
        (
            VALID_URI.replace("authSource=smarterp_test", "authSource=admin"),
            "smarterp_test",
            "authSource must be",
        ),
        (
            VALID_URI + "&authSource=admin",
            "smarterp_test",
            "authSource must be",
        ),
        (
            VALID_URI.replace("mongodb://", "http://"),
            "smarterp_test",
            "must use the mongodb:// scheme",
        ),
        (
            VALID_URI.replace("localhost", "example.com"),
            "smarterp_test",
            "must connect to localhost:27017",
        ),
        (
            "mongodb://smarterp_test_user:password@[invalid:27017/"
            "smarterp_test?replicaSet=rs0&authSource=smarterp_test",
            "smarterp_test",
            "valid local MongoDB address",
        ),
    ],
)
def test_rejects_unsafe_test_database_configurations(uri, database_name, message):
    with pytest.raises(pytest.UsageError, match=message):
        validate_test_mongo_configuration(uri, database_name)


def test_requires_test_uri():
    with pytest.raises(pytest.UsageError, match="MONGO_TEST_URI is required"):
        validate_test_mongo_configuration("", "smarterp_test")
