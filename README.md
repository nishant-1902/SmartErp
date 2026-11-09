# SmartERP

SmartERP is a full-stack ERP application with a React/Vite frontend, a Django
REST Framework API, and MongoDB accessed exclusively through PyMongo. Business
rules, validation, stock changes, and authorization are enforced by the
backend.

## Features

- JWT login, rotated HttpOnly refresh cookies, role-based permissions, user
  administration, audit logs, employee and department management.
- Product and supplier catalogues, stock adjustments and movement history,
  purchase orders, approvals, and partial/full goods receipts.
- Customers, sales orders, stock reservation and fulfilment, payments,
  invoices, and returns.
- Role-filtered dashboard and reports with date filters and safe CSV export.

## Technology stack

| Area | Technology |
| --- | --- |
| Web UI | React, React Router, Vite, Bootstrap, Axios |
| API | Python, Django, Django REST Framework |
| Database access | PyMongo only; MongoDB replica set for transactions |
| Authentication | PyJWT access tokens, rotated HttpOnly refresh cookie, Django password hashers |
| Frontend checks | Vitest, Testing Library, Oxlint, Vite production build |
| Backend checks | pytest, pytest-django, pytest-cov |

## Data flow

```text
User -> React screen -> Axios (JSON + bearer access token + refresh cookie)
     -> Django URL/view -> serializer validation -> permission check
     -> service business rules -> repository PyMongo operation -> MongoDB
     <- serialized response envelope <- service <- API <- React screen
```

The frontend is not an authorization boundary. Django's ORM, migrations,
`django.contrib.auth` data models, and Django admin are not used. All MongoDB
reads and writes belong in each app's repository; business workflows belong in
services. Stock changes also create stock movement records.

## Architecture

```text
React + Vite
    | JSON over HTTP; short-lived access JWT in memory; refresh cookie
    v
Django REST Framework
    | serializers -> permission checks -> services -> repositories
    v
MongoDB through PyMongo (replica set for transactional workflows)
```

The Django ORM, migrations, admin, and Django auth data models are not used.
The [architecture notes](docs/architecture.md), [requirements](docs/requirements.md),
[API reference](docs/api-documentation.md), and [testing guide](docs/testing.md)
describe the implementation in more detail.

## Windows development setup

Prerequisites: Python 3.12+, Node.js, npm, Git, and MongoDB configured as a
replica set. See [local MongoDB setup](docs/mongodb-local-setup.md).

1. From the repository root in PowerShell, configure the local environment:

   ```powershell
   Copy-Item backend\.env.example backend\.env
   Copy-Item frontend\.env.example frontend\.env
   ```

   Edit `backend\.env`: set `MONGO_URI`, `MONGO_DB_NAME`, `SECRET_KEY`,
   `JWT_SECRET_KEY`, and `CORS_ALLOWED_ORIGINS`. The example secrets are not
   usable; generate separate random values and keep `.env` files private.
   The frontend URL defaults to `http://localhost:8000/api`.

2. Install backend dependencies and initialize the application collections:

   ```powershell
   Set-Location backend
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   python manage.py init_db
   Set-Location ..
   ```

3. Install frontend dependencies:

   ```powershell
   Set-Location frontend
   npm ci
   Set-Location ..
   ```

## Start everything on Windows

The helper checks the MongoDB Windows service (starts it if stopped), then
opens the Django development API and Vite frontend in separate processes:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\start-dev.ps1
```

If MongoDB uses a non-default service name:

```powershell
.\scripts\start-dev.ps1 -MongoServiceName "YourMongoService"
```

Open `http://127.0.0.1:5173/`; the API health endpoint is
`http://127.0.0.1:8000/api/health/`. The public health endpoint is a liveness
check; database-backed requests use the configured `MONGO_URI`.

## Verify

From `backend\`:

```powershell
python manage.py check
python -m pytest -v
python -m pytest --cov=. --cov-report=term-missing
```

From `frontend\`:

```powershell
npm test
npm run lint
npm run build
```

Or run all backend and frontend checks from the repository root:

```powershell
.\scripts\run-tests.ps1
```

## Environment variables

Copy `backend/.env.example` and `frontend/.env.example`; replace placeholders
with your own settings. Keep `.env` files out of version control. `VITE_*`
settings are embedded in browser JavaScript and are public.

| Variable | Used by | Purpose |
| --- | --- | --- |
| `SMARTERP_ENV`, `DEBUG`, `ALLOWED_HOSTS` | Backend | Runtime mode and Django host/debug settings |
| `SECRET_KEY` | Backend | Django framework signing; use a strong private value |
| `MONGO_URI`, `MONGO_DB_NAME` | Backend | Application replica-set connection and database |
| `MONGO_TEST_URI`, `MONGO_TEST_DB_NAME` | Backend tests | Optional isolated test database; never point this at production |
| `JWT_SECRET_KEY`, `JWT_ISSUER`, `JWT_AUDIENCE` | Backend | JWT signing and claim validation |
| `JWT_ACCESS_TOKEN_LIFETIME_SECONDS`, `JWT_REFRESH_TOKEN_LIFETIME_SECONDS` | Backend | Token lifetimes |
| `CORS_ALLOWED_ORIGINS` | Backend | Exact browser origins permitted to call the API |
| `REFRESH_COOKIE_NAME`, `REFRESH_COOKIE_SECURE`, `REFRESH_COOKIE_HTTPONLY`, `REFRESH_COOKIE_SAMESITE`, `REFRESH_COOKIE_PATH`, `REFRESH_COOKIE_DOMAIN` | Backend | Refresh-cookie policy; Secure must be enabled over HTTPS |
| `SECURE_SSL_REDIRECT`, `SECURE_HSTS_SECONDS`, `TRUST_X_FORWARDED_PROTO` | Backend | Production HTTPS/proxy behavior; trust proxy headers only behind a configured trusted proxy |
| `LOG_FILE`, `LOG_LEVEL`, `LOG_MAX_BYTES`, `LOG_BACKUP_COUNT` | Backend | Rotating application log destination and policy |
| `VITE_API_BASE_URL` | Frontend | API base URL, normally `http://localhost:8000/api` locally |

See the example files for the exact supported defaults and production settings.

## Deployment

Build the frontend with the production API URL set before `npm run build`; serve
`frontend/dist` from static hosting with an SPA fallback. Run Django behind a
TLS-terminating proxy, use HTTPS, set explicit hosts/origins and strong secrets,
and connect only to a restricted MongoDB replica set. Initialize collections
and indexes with `python manage.py init_db` before deployment. Follow
[docs/deployment.md](docs/deployment.md) for platform and operations details.

## Screenshots

No screenshots are committed yet. Add current, redacted screenshots here when
captured; never include customer records, credentials, or tokens.

- `docs/screenshots/login.png` — login
- `docs/screenshots/dashboard.png` — role-filtered dashboard
- `docs/screenshots/inventory.png` — inventory and stock movements
- `docs/screenshots/purchase-orders.png` — purchase workflow
- `docs/screenshots/sales-orders.png` — sales workflow
- `docs/screenshots/reports.png` — reports

## Troubleshooting

- **MongoDB connection or transaction error:** confirm the Windows service is
  running, the URI credentials are URL-encoded, and `rs.status()` shows a
  PRIMARY member. Transactions require a replica set; see
  [docs/mongodb-local-setup.md](docs/mongodb-local-setup.md).
- **401 after a period idle:** the access token expires; refresh the page or
  sign in again. Confirm browser credentials are allowed for the exact CORS
  origin and refresh-cookie path.
- **403 on a screen or API call:** the signed-in role may lack the required
  permission. Check backend permission rules; hiding a link does not grant
  access.
- **Frontend cannot reach the API:** check `VITE_API_BASE_URL`, backend port
  8000, and `CORS_ALLOWED_ORIGINS`; restart Vite after changing `.env`.
- **Route returns 404 or 400:** compare the path with the API reference and
  route inventory; detail identifiers must be valid MongoDB ObjectIds.
- **Tests fail locally:** activate the backend venv, install
  `backend/requirements-dev.txt`, run `npm ci` under `frontend`, and inspect
  the first failing assertion before changing fixtures.

## Contribution and release notes

See [CONTRIBUTING.md](CONTRIBUTING.md) for the change workflow and
[CHANGELOG.md](CHANGELOG.md) for documented releases and current work.

## Production settings and servers

Set `SMARTERP_ENV=production` in the backend environment after replacing the
placeholder secrets and setting explicit `ALLOWED_HOSTS`. Production settings
refuse `DEBUG=True`, missing/weak secrets, wildcard hosts, and a zero HSTS
duration. Secure cookies, HTTPS redirect, one-year HSTS, security headers, and
rotating file logs are enabled by default. See
[production deployment guidance](docs/deployment.md).

Gunicorn does **not** run on Windows. For a local Windows production-settings
smoke test, use Waitress (installed from `requirements.txt`), never Django's
`runserver`:

```powershell
$env:SMARTERP_ENV = "production"
$env:DEBUG = "False"
$env:ALLOWED_HOSTS = "127.0.0.1,localhost"
# HTTP is allowed only for this local smoke test; production must use HTTPS.
$env:SECURE_SSL_REDIRECT = "False"
Set-Location backend
.\venv\Scripts\waitress-serve.exe --listen=127.0.0.1:8000 config.wsgi:application
```

Serve `frontend\dist\` from static hosting or a web server configured with an
SPA fallback to `index.html`. Set `VITE_API_BASE_URL` **before** `npm run build`;
Vite embeds it in the generated JavaScript. Any `VITE_*` value is public and
must never contain secrets. The frontend build is static; it does not require
Node.js on the production web server.

On Linux, use Gunicorn behind a TLS-terminating reverse proxy:

```bash
cd backend
SMARTERP_ENV=production gunicorn config.wsgi:application \
  --bind 127.0.0.1:8000 --workers 3 --access-logfile - --error-logfile -
```

Do not expose Waitress/Gunicorn or MongoDB directly to the public Internet.

Tests using the in-memory PyMongo-shaped fake do not prove live MongoDB
transaction isolation. Use only a dedicated `smarterp_test` replica-set account
for MongoDB integration tests; those fixtures clear test-database documents.
See [testing instructions](docs/testing.md).

## Project status

The ten requested application phases have core implementations. Automated
verification passed, but live replica-set transaction tests and credentialed
Postman execution remain outstanding. See [docs/PROGRESS.md](docs/PROGRESS.md)
and the [final project verification report](docs/FINAL_PROJECT_VERIFICATION_REPORT.md).
The local development configuration requires user-provided MongoDB credentials
and JWT/Django secrets; no secrets are committed.
