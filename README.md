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
