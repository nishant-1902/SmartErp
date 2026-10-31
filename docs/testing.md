# Backend testing

The backend tests use `pytest`. Unit tests can run without MongoDB. Tests that
request the `mongo_db` fixture use the real local MongoDB replica set; do not
replace it with mongomock because mongomock does not support transactions.

## Configure MongoDB integration tests

Create a local `backend/.env` from `backend/.env.example`, then set
`MONGO_TEST_URI` to the dedicated `smarterp_test_user` connection and
`MONGO_TEST_DB_NAME=smarterp_test`. The test URI must select the `smarterp_test`
database, use `authSource=smarterp_test` and `replicaSet=rs0`, and connect to a
writable primary. Never use your application or admin account in this setting.
The test fixtures reject any other database name, user, authentication source,
or replica-set setting before connecting.

The test account needs to be able to create the declared collections and
indexes on its first run. Each pytest session runs `manage.py init_db`; test
documents are removed between database-backed tests, and all documents are
removed again when the session ends. Collection definitions and indexes remain
in place. Do not put a real password in tracked files.

## Run tests (PowerShell)

Run these commands from `backend\` after activating the backend virtual
environment:

```powershell
# Activate the virtual environment if it is not already active.
.\venv\Scripts\Activate.ps1

# Run all discovered backend tests.
python -m pytest

# Run one test file.
python -m pytest tests\common\test_money.py

# Run one test by its node ID.
python -m pytest tests\common\test_money.py::test_line_total_uses_decimal_arithmetic

# Run tests and show line coverage.
python -m pytest --cov=. --cov-report=term-missing
```

Add `-m slow_transaction` to run only tests marked as slower transaction
tests, or `-m "not slow_transaction"` to skip those tests. Mark transaction
tests with `@pytest.mark.slow_transaction`; they must use the real replica set.

## Shared fixtures

`tests/conftest.py` provides:

- `mongo_test_database`: session-level safety checks and `init_db` setup.
- `mongo_db`: function-level cleanup before and after each database-backed test.
- `api_client`: a DRF test client.
- `create_user(role)`: a factory for valid test users.
- `auth_headers(role)`: a factory for short-lived JWT test authorization headers.
- `seed_department`, `seed_product`, `seed_supplier`, and `seed_customer`:
  factories for valid seed documents.

Each test that needs MongoDB should request `mongo_db` (directly or through a
factory fixture). This keeps pure unit tests independent from local MongoDB.
The auth fixture signs tokens with a test-only key and does not implement or
replace production authentication.

## Read a failure traceback

Read a pytest traceback from the bottom upward:

1. The final exception line names the failure, such as `AssertionError`,
   `ValidationError`, or a MongoDB connection error.
2. The nearest project file and line above it show where the failure occurred.
3. The displayed test name tells you which test was running.
4. The `E` lines show the expected and actual values or the exception message.
5. If the failure is a MongoDB connection/setup error, check the test URI,
   local MongoDB service, `rs.status()` (the member must be `PRIMARY`), and the
   test user's database permissions. Never paste passwords into logs or issue
   reports.

Run the named test alone with its node ID after fixing the cause, then rerun the
full suite.
