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

1. Copy `backend\.env.example` to `backend\.env` and set the local MongoDB
   application URI, Django/JWT secrets, and exact CORS origins. Copy
   `frontend\.env.example` to `frontend\.env`; the default API URL is
   `http://localhost:8000/api`.
2. In PowerShell, install backend dependencies:

   ```powershell
   cd backend
   py -m venv venv
   .\venv\Scripts\Activate.ps1
   python -m pip install -r requirements-dev.txt
   ```

3. Initialize the application collections and indexes once:

   ```powershell
   python manage.py init_db
   ```

4. In a separate PowerShell window, install frontend dependencies:

   ```powershell
   cd frontend
   npm ci
   ```

## Run locally

Start the backend from `backend\`:

```powershell
.\venv\Scripts\Activate.ps1
python manage.py runserver
```

Start the frontend from `frontend\`:

```powershell
npm run dev
```

The local API health endpoint is `http://localhost:8000/api/health/`.
The health endpoint is a liveness check; MongoDB connectivity is separately
configured through `MONGO_URI` and is required for database-backed operations.

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
