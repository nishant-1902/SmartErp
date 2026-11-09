# SmartERP Architecture

## Status and scope

This document describes the implemented SmartERP architecture and its intended boundaries. It is checked against the current backend and frontend source. Individual limits and unverified production behavior are called out where relevant; see `docs/PROGRESS.md` for current verification status.

## Final recommendation

Use a single-page React application built with Vite, a Django REST Framework (DRF) JSON API, PyMongo as the only database access layer, and MongoDB as the document database.

- **React + Vite** provides the browser interface and development/build tooling.
- **Axios** sends JSON requests to the API. Browser code uses an in-memory short-lived access token and sends a refresh token only as an HttpOnly cookie; it must not persist access or refresh tokens in local storage.
- **Django + DRF** provides URL routing, request parsing, authentication and permission hooks, serializer validation, and consistent HTTP responses. Django's ORM, migrations, admin, and Django auth data models are not used.
- **PyMongo** is the only way application code reads or writes MongoDB. Each app has a repository layer for database operations and a service layer for business rules and multi-document workflows.
- **MongoDB** stores application documents. Use a replica set (including local development) for multi-document transactions. Create and manage indexes explicitly and keep their definitions in version-controlled project code.

Keep the frontend, API, and database as distinct trust boundaries. The frontend is a user interface, not an authorization boundary. The backend validates and authorizes every operation before a repository accesses MongoDB.

## DRF without the Django ORM

DRF remains useful even when Django's ORM is not used. Django still handles HTTP, URL routing, middleware, settings, and the request/response lifecycle. DRF adds API-oriented parsing, serializers, authentication, permissions, and response support.

1. **Configure Django without ORM-backed applications.** Set `DATABASES["default"]["ENGINE"]` to Django's dummy backend. Do not install `django.contrib.auth`, `django.contrib.admin`, `django.contrib.contenttypes`, `django.contrib.sessions`, or `django.contrib.messages` as application data systems. Configure DRF's unauthenticated user and token values as `None` so defaults do not import Django auth models.
2. **Authenticate requests with a custom DRF authentication class.** For protected routes, read the bearer access token, verify its signature and claims, load the current user through an accounts repository, and reject inactive users or stale token versions. A custom lightweight authenticated-user value supplies the identity, role, and permissions expected by the permission layer. Public routes are explicitly limited to health and the intended authentication endpoints.
3. **Authorize on the server.** DRF permission classes use the code-defined role/permission matrix. UI visibility is only a usability aid and cannot grant access.
4. **Validate with plain DRF serializers.** Use `serializers.Serializer`, not `ModelSerializer`. Serializers validate and normalize every request field before any service is called. Reject user-controlled keys that begin with `$` or contain `.`; validate URL/body ObjectIds with a shared helper; allow only explicit fields for updates.
5. **Put business rules in services.** Views do little more than parse validated input, pass the authenticated identity and arguments to a service, and turn its result into the standard response envelope. Services implement workflows, permission-sensitive rules, transactions, idempotency, and audit events.
6. **Keep MongoDB access in repositories.** Each app's `repository.py` contains PyMongo operations and query construction from validated values. Views and serializers must never construct or execute MongoDB queries from raw request data.
7. **Return a stable JSON contract.** Successful responses use `{"success": true, "data": ..., "meta": {...}}`; errors use `{"success": false, "error": {"code": "...", "message": "...", "details": {...}}}`. Convert BSON values such as ObjectId, Decimal128, and datetimes to documented JSON-safe representations. Log internal failures server-side without exposing database errors, traces, or secrets.

The dummy database backend prevents Django ORM features from silently becoming a second application data store. It does not prevent Django or DRF from serving HTTP requests. Avoid ORM-oriented commands and features such as migrations, admin, and session-backed authentication.

## Main architectural risks and mitigations

| Risk | Why it matters | Mitigation |
|---|---|---|
| No ORM or migrations | MongoDB document shape and indexes will not be managed by Django migrations; schema drift and unsafe index changes become operational risks. | Keep validators and index definitions in explicit, reviewed database initialization code; make initialization repeatable; document schema changes and duplicate cleanup; test initialization against a separate test database. |
| Transactions require a replica set | Multi-document transactions fail on a standalone MongoDB server, including workflows that update stock and write audit/movement records. | Configure local MongoDB as a single-node replica set or use an appropriately configured hosted replica set; verify the node is PRIMARY before transaction work; fail clearly when transaction capability is unavailable. |
| JWT storage in the browser | Persistent JavaScript-readable token storage increases the impact of XSS; cookie-based credentials introduce CSRF considerations. | Keep short-lived access tokens in memory only. Store refresh tokens only as rotated, hashed server-side values and deliver them in HttpOnly, Secure-in-production cookies with deliberate SameSite/path settings. Protect cookie-authenticated refresh/logout operations with a CSRF defense and exact-origin CORS. Apply a strong content-security policy and prevent XSS. |
| Overselling stock | Concurrent orders can each observe the same available quantity and consume more stock than exists. | Do not use read-then-write checks. Use conditional atomic updates that require sufficient available stock, alongside transactions and stock movement records. Test competing operations against a real replica set. |
| Duplicate receipts or other retried operations | Browser, proxy, or client retries may repeat a request after the first operation succeeded. | Require idempotency keys for critical mutations; store the scoped key, request hash, and result in the same transaction as the business operation; add unique indexes and receipt-specific uniqueness constraints. Reject reuse of a key with a different request body. |
| Money precision | Binary floating point cannot represent many decimal amounts exactly and can make totals inconsistent. | Use Python `Decimal` for calculations, a documented rounding rule, and BSON `Decimal128` for storage. Never calculate money with `float`; return money in a stable string representation. |
| NoSQL operator injection | Untrusted query keys or operators can alter filters, updates, or sort behavior. | Validate all input with plain serializers; reject keys beginning with `$` or containing `.`; construct query documents only in repositories from typed, allow-listed values; escape text used in regular expressions; allow-list sortable fields. |
| Index management | Missing indexes degrade list and report queries; unique-index creation can fail on existing duplicates; TTL cleanup is asynchronous. | Keep index definitions under source control, create them through a repeatable initialization command, document query patterns and index ownership, inspect query plans with representative data, and resolve duplicates before enforcing uniqueness. Do not treat TTL deletion as an exact-time guarantee. |
| Authorization drift | Frontend hiding can be bypassed, and route-specific permission gaps can expose data. | Deny by default in DRF, define a single permission matrix, explicitly assign permissions to each protected endpoint, and test the complete role/route matrix. Re-check sensitive permissions in services where workflows require it. |
| ORM assumptions in Django/DRF | Defaults such as anonymous users, sessions, auth middleware, or admin can import or require ORM-backed models. | Keep the installed apps and middleware minimal, explicitly disable DRF's ORM-dependent unauthenticated defaults, and verify startup and request handling without database migrations. |
| Secrets and operational exposure | Credentials, JWT keys, or database errors can leak through source control, logs, or responses. | Read secrets only from environment configuration; commit a placeholder-only `.env.example`, never a real `.env`; restrict MongoDB network access; redact credentials in logs; return generic error envelopes and log diagnostic details only on the server. |

## Request lifecycle

```text
Browser user
  -> React page/component
  -> Axios API client (base URL, JSON, credentials, bearer access token)
  -> HTTP request
  -> Django CORS middleware (preflight/origin policy; CORS is not authentication)
  -> Django URL router
  -> DRF request parsing
  -> DRF authentication (custom JWT class; public routes explicitly exempt)
  -> DRF permission check (backend role/permission matrix)
  -> Plain DRF serializer (validate and normalize all input)
  -> View (pass validated values and identity to service)
  -> Service (business rules, transaction, idempotency, audit/stock invariants)
  -> Repository (typed, allow-listed PyMongo operations)
  -> MongoDB (collections, validators, indexes; replica-set transaction if needed)
  <- Repository result
  <- Service result
  <- View serializes JSON-safe data into the standard response envelope
  <- DRF/Django HTTP response
  <- Axios response/interceptor
  <- React updates UI or displays an error
```

Successful API responses follow:

```json
{"success": true, "data": {}, "meta": {}}
```

Error responses follow:

```json
{"success": false, "error": {"code": "ERROR_CODE", "message": "Safe message", "details": {}}}
```

## Security boundaries

- **Browser and React UI:** untrusted. Client-side route guards, hidden buttons, and form validation improve usability only. A caller can bypass them and issue HTTP requests directly.
- **Network and CORS:** CORS controls which browser origins may read responses; it does not authenticate clients or protect the API from non-browser requests. Use HTTPS outside local development, exact allowed origins, and explicit credential/header configuration.
- **Django/DRF API boundary:** validate every input, authenticate protected requests, enforce backend permissions, limit request sizes/rates where appropriate, and return only safe response fields. Never trust a client-supplied role, price, total, stock quantity, or ownership claim.
- **Service boundary:** enforce business invariants, state transitions, separation of duties, idempotency, transactional writes, and audit requirements. Critical workflows must not be bypassable through another endpoint.
- **Repository/database boundary:** repositories alone build PyMongo queries from validated values. MongoDB users should have only the required database permissions; bind/firewall MongoDB to trusted interfaces and do not expose it publicly.
- **Secrets and operations:** use environment variables or a suitable secret store; keep real `.env` files and MongoDB key files outside version control; redact secrets in logs; back up data and test restoration.
- **Response and observability boundary:** expose stable error codes and safe messages, not raw database errors or stack traces. Keep detailed diagnostic logs server-side with access controls.

## Project folder structure

The structure below describes the repository organization for the current
implementation. It is a focused architecture map rather than a complete file
listing; consult the repository for the full inventory.

```text
smarterp/
|-- AGENTS.md                         # Persistent project and coding rules
|-- .gitignore                        # Excludes local environments, secrets, generated files, and data
|-- README.md                         # Project overview and developer entry point
|-- backend/
|   |-- manage.py                     # Django management command entry point
|   |-- requirements.txt              # Pinned runtime Python dependencies
|   |-- requirements-dev.txt          # Python test and development dependencies
|   |-- pytest.ini                    # Pytest/Django test configuration
|   |-- .env.example                  # Safe placeholder backend environment variables
|   |-- config/                       # Django project configuration package
|   |   |-- __init__.py
|   |   |-- settings.py               # Environment-driven settings; dummy Django database backend
|   |   |-- urls.py                   # Root API URL routing
|   |   |-- asgi.py                   # ASGI server entry point
|   |   |-- wsgi.py                   # WSGI server entry point
|   |-- database/                     # Shared PyMongo connection and explicit index/collection setup
|   |   |-- __init__.py
|   |   |-- connection.py             # Lazy MongoClient, database/collection access, health/transaction checks
|   |   |-- indexes.py                # Collection validators and index definitions
|   |-- common/                       # Shared API responses, exceptions, validation, serialization, and helpers
|   |   |-- __init__.py
|   |   |-- apps.py                   # Django app configuration and command discovery
|   |   |-- responses.py              # Standard success/error JSON envelopes
|   |   |-- exceptions.py             # Safe domain/DRF exception mapping
|   |   |-- object_id.py              # ObjectId validation
|   |   |-- sanitize.py               # Mongo-key rejection and safe text-search helpers
|   |   |-- serialization.py          # BSON-to-JSON conversion
|   |   |-- money.py                  # Decimal and Decimal128 helpers
|   |   |-- pagination.py              # Validated pagination and metadata
|   |   |-- permissions_matrix.py     # Code-defined role-to-permission mapping
|   |   |-- permissions.py            # DRF permission helpers
|   |   |-- idempotency.py             # Scoped, transactional idempotency support
|   |   |-- management/               # Django management-command package
|   |       |-- __init__.py
|   |       |-- commands/             # Django-discovered operational commands
|   |           |-- __init__.py
|   |           |-- init_db.py         # Idempotent collection/index initialization
|   |-- accounts/                     # Users, password hashing, JWT and refresh-token authentication
|   |-- employees/                    # Employee API and business rules
|   |-- departments/                  # Department API and business rules
|   |-- inventory/                    # Products, stock changes, and append-only stock movements
|   |-- suppliers/                    # Supplier API and business rules
|   |-- purchases/                    # Purchase orders, approvals, and transactional receipts
|   |-- customers/                    # Customer API and business rules
|   |-- sales/                        # Sales orders, reservations, fulfillment, invoices, and payments
|   |-- reports/                      # Permission-checked MongoDB aggregation/report APIs
|   |-- tests/                        # Shared fixtures and app-organized backend tests
|   |   |-- conftest.py                # Safe isolated test-database fixtures
|   |   |-- common/                    # Shared utility and permission tests
|   |   |-- accounts/                  # Authentication and user-management tests
|   |   |-- employees/                 # Employee API/service tests
|   |   |-- departments/               # Department API/service tests
|   |   |-- inventory/                 # Product, movement, and concurrency tests
|   |   |-- suppliers/                 # Supplier API/service tests
|   |   |-- purchases/                 # Purchase approval and receipt tests
|   |   |-- customers/                 # Customer API/service tests
|   |   |-- sales/                     # Sales, payment, fulfillment, and return tests
|   |   |-- reports/                   # Report aggregation and access tests
|   |-- scripts/                      # Explicit operational or development scripts
|-- frontend/
|   |-- package.json                  # Frontend dependencies and npm scripts
|   |-- package-lock.json             # Reproducible npm dependency resolution
|   |-- vite.config.js                # Vite development/build and test configuration
|   |-- .env.example                  # Safe public frontend API-base-URL example
|   |-- index.html                    # Vite HTML entry point
|   |-- src/
|       |-- assets/                   # Styles, images, and other bundled assets
|       |-- components/               # Reusable, focused UI components
|       |-- layouts/                  # Shared page layouts and navigation shells
|       |-- pages/                    # Route-level screens grouped by business area
|       |   |-- auth/                 # Login and password-reset screens
|       |   |-- employees/            # Employee list, detail, and profile screens
|       |   |-- departments/          # Department screens
|       |   |-- inventory/            # Product, stock, and movement screens
|       |   |-- suppliers/            # Supplier screens
|       |   |-- purchases/             # Purchase order and receipt screens
|       |   |-- customers/             # Customer screens
|       |   |-- sales/                 # Sales order, payment, and invoice screens
|       |   |-- reports/               # Dashboard and reporting screens
|       |-- services/                 # Axios client and API-specific request functions
|       |-- context/                  # App-wide state providers such as authentication and toasts
|       |-- hooks/                    # Reusable React hooks
|       |-- utils/                    # Small frontend formatting and validation helpers
|       |-- App.jsx                   # Route composition and top-level app component
|       |-- main.jsx                  # Browser entry point and global CSS/provider setup
|-- docs/
|   |-- PROJECT_BRIEF.md              # Full project specification and implementation prompt guide
|   |-- PROGRESS.md                   # Step-by-step implementation and verification record
|   |-- architecture.md               # This architecture decision and risk record
|   |-- requirements.md               # Functional requirements, permission matrix, and workflows
|   |-- database-design.md            # Collections, validators, indexes, and example documents
|   |-- api-documentation.md          # API routes, payloads, permissions, and response contracts
|   |-- authentication.md             # Authentication and token lifecycle guide
|   |-- testing.md                    # Test strategy, commands, and test database safety
|   |-- deployment.md                 # Production configuration and deployment guide
|   |-- user-manual.md                # User instructions organized by role
|   |-- maintenance.md                # Backup, monitoring, retention, and maintenance guidance
|   |-- postman/                      # Importable API collection and local environment
```

Folder responsibilities, at a glance:

- `backend/` contains the Django/DRF API and Python dependencies.
- `backend/config/` contains Django project configuration and top-level HTTP routing.
- `backend/database/` contains shared MongoDB connection and database setup code.
- `backend/common/` contains cross-app API and data-safety helpers.
- `backend/common/management/commands/` contains Django-discovered management commands.
- `backend/accounts/`, `backend/employees/`, `backend/departments/`, `backend/inventory/`, `backend/suppliers/`, `backend/purchases/`, `backend/customers/`, `backend/sales/`, and `backend/reports/` are separate business-area packages. Each uses `serializers.py`, `repository.py`, `services.py`, `views.py`, and `urls.py` as appropriate; accounts also owns its authentication implementation. They contain no Django models or ORM migrations.
- `backend/tests/` contains tests grouped by app plus shared test configuration.
- `backend/scripts/` contains deliberate developer/operations scripts, not request handlers.
- `frontend/` contains the Vite-managed React browser application.
- `frontend/src/assets/` contains bundled styles and visual assets.
- `frontend/src/components/` contains reusable UI building blocks.
- `frontend/src/layouts/` contains shared page shells.
- `frontend/src/pages/` contains screens mapped to routes.
- `frontend/src/services/` contains HTTP clients and API functions.
- `frontend/src/context/` contains shared React providers.
- `frontend/src/hooks/` contains reusable hook logic.
- `frontend/src/utils/` contains UI-independent frontend helpers.
- `docs/` contains the specification's maintained project documentation.
- `docs/postman/` contains the Postman collection and environment files.

The target tree intentionally does not include Django model or migration folders. Do not create Django models or ORM migrations for application data. Individual Python package files such as `__init__.py`, `serializers.py`, `repository.py`, `services.py`, `views.py`, and `urls.py` are created in the implementation steps where applicable.

## Windows installation checklist

Install tools from their official Windows distributions. These commands verify the command-line tools when installed and available on `PATH`; MongoDB Compass and Postman desktop versions are best checked in each application's **Help > About** (their executable paths and command-line version support vary by installation).

| Tool | Purpose | Verification |
|---|---|---|
| Python 3.12 or newer | Runs the Django/DRF backend and Python tools. Enable the Python launcher/PATH option in the installer. | `py --version` |
| Node.js LTS and npm | Runs Vite and builds the React frontend. Install the current LTS release. | `node --version` and `npm --version` |
| Git for Windows | Source control and project history. | `git --version` |
| Visual Studio Code | Project editor; install the chosen AI coding extension separately. | `code --version` |
| MongoDB Community Server | Local MongoDB service; configure it as a replica set before transactional workflow steps. | `mongod --version`; check service state with `Get-Service MongoDB` |
| MongoDB Compass | GUI for inspecting local collections, documents, and indexes. | Open Compass and check **Help > About MongoDB Compass**. `mongosh --version` verifies the separate MongoDB shell, not Compass. |
| Postman | Sends and inspects API requests during development. | Open Postman and check **Help > About**. The desktop app does not have a consistent version command across Windows installs. |

Optional MongoDB command-line tools used by later backup/setup steps are separate from the server and Compass; verify them, when installed, with `mongosh --version`, `mongodump --version`, and `mongorestore --version`.
