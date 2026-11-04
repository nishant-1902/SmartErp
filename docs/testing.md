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

## Run the Postman API collection

Import `docs/postman/SmartERP.postman_collection.json` and
`docs/postman/SmartERP.local.postman_environment.json` into Postman, then select
the **SmartERP local** environment. The local environment intentionally has
blank credentials and IDs; enter your local Super Admin email/password and an
Employee account email/password. Do not commit credentials, access tokens, or
an exported environment containing secrets.

Set `baseUrl` to the backend API root, normally
`http://localhost:8000/api`. The Auth folder's login requests save bearer
tokens in `accessToken` and `employeeAccessToken`. Login also puts the refresh
cookie in Postman's cookie jar. The refresh request relies on that jar and sends
the required `X-Requested-With: XMLHttpRequest` header; do not manually
copy the HttpOnly refresh cookie into an environment variable or request
header.

The collection has 15 folders covering health, authentication, user and
business resources, reports, and negative cases. Each request checks its
expected HTTP status and the standard success or error JSON envelope.
Idempotent stock adjustment, purchase receipt, fulfilment, and payment requests
generate a fresh UUID with Postman's `{{$guid}}` dynamic value. If testing a
retry, reuse the same `Idempotency-Key` and do not rerun its pre-request script.

For a complete successful workflow, create or configure a department, product,
supplier, and customer first. The product and supplier IDs are stored when
their create requests succeed; the employee request needs an active
`departmentId`. Stock adjustment adds initial inventory. Then create, submit,
and approve a purchase order, receive it in the Receipts folder, and run the
customer and sales-order workflow. The sales-order request uses the returned
customer/product IDs; confirm and fulfil it before recording a payment or
return. The collection's Reject and Cancel purchase-order examples require
separate eligible IDs. Optional IDs can instead be supplied manually in the
environment. Collection examples change data in the selected database, so use
a disposable local database when exercising write workflows.

### Expired-token negative test

With the backend virtual environment activated and a local user already
created, run from `backend\`:

```powershell
.\venv\Scripts\python.exe scripts\make_expired_token.py --email admin@example.com
```

Alternatively, select a user by MongoDB ID:

```powershell
.\venv\Scripts\python.exe scripts\make_expired_token.py --user-id 65a000000000000000000001
```

Copy the printed JWT into the environment's `expiredToken` value. The script
uses the configured local MongoDB and JWT settings, prints only the token on
success, and does not change the user or database.

### Collection Runner and Newman

Run the whole collection or selected folders with Postman's Collection Runner.
Run Auth login first when testing only selected requests. Some requests depend
on IDs saved by earlier create calls; requests with independent IDs must have
those IDs entered in the environment. The Employee permission test needs a
valid Employee token, which the second login request stores.

If Newman is already installed, run the collection from the repository root:

```powershell
newman run docs\postman\SmartERP.postman_collection.json `
  --environment docs\postman\SmartERP.local.postman_environment.json
```

Newman does not persist sensitive environment values unless explicitly
exported. Avoid `--export-environment` for the tracked local template.

Database-unavailable validation is documented as a manual step and is not a
runnable collection request. On an isolated local database only, stop MongoDB
or block the backend's MongoDB connection, call
`GET {{baseUrl}}/reports/dashboard/`, and verify that the dashboard returns
HTTP 200 with a standard success envelope and non-empty
`data.dashboard.widget_errors`; error messages must not disclose database
details. Restore MongoDB immediately afterward. Never stop or disrupt a shared
or production database for this check.
