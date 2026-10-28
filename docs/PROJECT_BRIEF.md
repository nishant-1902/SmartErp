SmartERP
Step-by-Step AI Coding Prompts
A complete prompt playbook for Codex, Cline, Cursor, Claude Code, Copilot Agent and other AI coding assistants.
Stack: React + Django REST Framework + PyMongo + MongoDB + JWT
12 phases  |  40+ copy-paste prompts  |  Windows friendly
Part 0 - How to Use This Guide
Your original specification is very large. If you paste it into an AI coding tool in one go, the result will be shallow, inconsistent and hard to debug. This guide breaks it into small prompts. Each prompt produces one testable result. You verify it, commit it, and only then move to the next prompt.
The 6-step loop (repeat for every prompt)
1.	Open a fresh task/chat for each step (or each phase) so the AI does not drown in old context.
2.	Paste the prompt. Every prompt starts with 'Read AGENTS.md and docs/PROGRESS.md' so the AI re-loads the rules and the project history.
3.	Let the agent write code and run commands. In Cline/Codex, approve commands only after reading them.
4.	Verify yourself: run the tests, call the endpoint in Postman, click the screen. Do not trust 'it works' without output.
5.	Commit to Git on a feature branch (git add, git commit). Small commits let you roll back mistakes.
6.	Update docs/PROGRESS.md (the prompts ask the AI to do it) and go to the next prompt.
Tool differences
Tool	Rules file name	Best way to use this guide
OpenAI Codex (CLI / IDE)	AGENTS.md (root)	Keep AGENTS.md in the repo root. Paste one prompt per task. Use suggest/approval mode at first.
Cline (VS Code)	.clinerules (file or folder)	Copy the AGENTS.md text into .clinerules. Use Plan mode first, then Act mode. Auto-approve only file reads.
Cursor	.cursor/rules	Put the rules in an always-apply rule. Use Agent mode with one prompt per chat.
Claude Code	CLAUDE.md	Same text as AGENTS.md. Use plan mode for architecture steps.
GitHub Copilot Agent	.github/copilot-instructions.md	Paste the rules there. Use agent mode per step.

Golden rules
•	Never skip the verification step. Most project failures come from stacking unverified code.
•	If the AI goes off track, do not argue for 10 messages. Use git restore / git checkout, start a fresh task, and give a tighter prompt.
•	Keep prompts specific: goal, scope, requirements, out of scope, acceptance criteria (template below).
•	Never paste real secrets or customer data into any AI tool. Use .env and fake data.
•	Ask the AI to explain code you do not understand (Fix Prompt F4). You are building a portfolio piece, so you must be able to explain every line in an interview.
•	Before large phases (3, 7, 8) ask the AI for a plan first and approve it, then let it code.
Overview of phases
Phase	Result	Approx. prompts
1	Planning, repo, backend and frontend skeletons	5
2	MongoDB, indexes, health check, common utilities, test DB	5
3	JWT auth, refresh rotation, RBAC, user management	4
4	Departments and employees APIs	2
5	React auth, layout, employee, user and settings pages	4
6	Products, stock engine, inventory UI	3
7	Suppliers, purchase workflow, goods receipt, UI	4
8	Customers, sales, payments, invoices, returns, UI	4
9	Reports and dashboard	2
10	Postman collection and automated tests	2
11	Production setup and deployment	2
12	Security, performance, docs, portfolio	4
Part A - One-Time Setup (do this before Prompt 1.1)
A1. Create the project folder and save your specification
Create an empty folder named smarterp and open it in VS Code. Save your full original specification as docs/PROJECT_BRIEF.md. Prompt 1.1 tells the AI to read it. Run these commands in PowerShell:
mkdir smarterp
cd smarterp
mkdir docs
code .
# Save your full original specification into docs\PROJECT_BRIEF.md

A2. Create the rules file (AGENTS.md)
Create a file named AGENTS.md in the project root and paste the text below. For Cline copy it to .clinerules, for Claude Code to CLAUDE.md, for Cursor to .cursor/rules. This is the most important file: it is read at the start of every step and keeps the AI consistent.
Paste into AGENTS.md:
# SmartERP - Project Rules for AI Coding Agents
 
## Project
SmartERP is a full-stack ERP: React (JavaScript, Vite) frontend, Django + Django REST Framework backend, MongoDB database accessed ONLY through PyMongo. Developer is on Windows. Explain things in simple English.
 
## Architecture rules (never break these)
1. Django ORM, migrations, django.contrib.auth and django admin are NOT used for data. Do not create Django models. DATABASES uses the dummy backend.
2. All data access goes through repository functions in each app's repository.py using PyMongo.
3. Business logic lives in services.py. Views only parse input, call a service, and return a response.
4. Serializers (plain DRF serializers, not ModelSerializer) validate ALL input. Never pass request data directly into a Mongo query.
5. Reject any user-supplied key starting with "$" or containing "." in filters and bodies (NoSQL operator injection).
6. Validate every ObjectId from URL or body with a helper; invalid -> 400.
7. Money uses Python Decimal and is stored as BSON Decimal128. Never use float for money.
8. Timestamps are timezone-aware UTC datetimes stored as BSON dates.
9. Authorization is enforced on the backend with a permission matrix in code. Frontend hiding is only for UX.
10. Multi-collection operations (receive PO, fulfil sale, stock adjust) use MongoDB transactions (replica set) PLUS conditional updates, unique indexes and idempotency keys.
11. Stock quantity can only change through a service that also writes a stock_movements document.
12. Passwords: Django's hashers (Argon2 or PBKDF2) used standalone. JWT: PyJWT. Refresh token: HttpOnly cookie, rotated on every use, stored hashed in MongoDB, reuse detection.
13. Never expose DB errors, stack traces or secrets in responses. Use one consistent JSON envelope:
   success: {"success": true, "data": ..., "meta": {...}}
   error:   {"success": false, "error": {"code": "...", "message": "...", "details": {...}}}
14. Secrets only from environment variables (.env, never committed). Provide .env.example.
15. In urls.py declare fixed paths (me/, low-stock/, categories/, designations/) BEFORE the <id>/ path, otherwise they are parsed as an ObjectId and fail with 400.
 
## Code rules
- Python: PEP8, type hints, docstrings on public functions. JavaScript: functional components + hooks, one component per file.
- Each Django app: serializers.py, repository.py, services.py, views.py, urls.py, permissions (via common), tests in backend/tests/<app>/.
- Small focused changes. No unrelated refactors. No new dependency without telling me why.
- Windows-friendly commands (PowerShell). Use "py -m venv", ".\venv\Scripts\Activate.ps1".
 
## Workflow rules
- Work on ONE step at a time. Stop when the step is done.
- After each step: run tests, update docs/PROGRESS.md, suggest a git commit message.
- Never claim something works unless you ran it and saw the output.
- If a requirement is unclear or the requested stack is a poor fit, ask or explain the trade-off BEFORE coding.
- Clearly label: complete code / example only / needs my configuration / not implemented yet.

A3. Software to install first (Windows)
•	Python 3.12 or newer (tick 'Add to PATH'). Check: py --version
•	Node.js LTS. Check: node --version and npm --version
•	Git for Windows. Check: git --version
•	MongoDB Community Server (installed as a Windows service). Check: mongod --version
•	VS Code plus your AI extension (Cline) or the Codex CLI
•	MongoDB Compass (GUI), mongosh (shell) and MongoDB Database Tools (mongodump/mongorestore, separate download). Check: mongosh --version and mongodump --version
•	Postman
A4. Reusable prompt template
Use this template whenever you write your own prompt or want to add a feature. The detailed prompts in this guide already follow it.
Read AGENTS.md and docs/PROGRESS.md first.
 
GOAL: <one sentence: what this step must achieve>
SCOPE (only touch these): <folders/files>
REQUIREMENTS:
- <requirement 1>
- <requirement 2>
OUT OF SCOPE: <what NOT to do now>
ACCEPTANCE CRITERIA:
- <command that must pass / behaviour that must work>
WHEN FINISHED: run tests, show output, update docs/PROGRESS.md, list files changed, suggest commit message, then STOP.

Note: every detailed prompt in this guide ends with a standard closing block that tells the AI to run tests, show real output, update PROGRESS.md, list changed files and stop. It is included inside each prompt, so you can copy the whole box as it is.
Phase 1 - Requirements, Architecture, Project Setup, GitHub
Objective: A clean repo with backend and frontend skeletons, planning documents, and a first Git commit. No business features yet.
Prompt 1.1 Architecture planning (no code yet)
Goal: Get the AI to agree on the architecture before writing anything.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
This is PHASE 1, step 1. Do NOT write application code yet. Create only planning documents.
 
Read the project brief in docs/PROJECT_BRIEF.md (I have pasted my full SmartERP specification there).
 
Produce docs/architecture.md containing:
1. Final architecture recommendation (React + Django REST Framework + PyMongo + MongoDB).
2. Explanation of how DRF works WITHOUT the Django ORM (custom authentication class, repositories, services, plain serializers).
3. Top architectural risks and mitigation: no ORM/migrations, MongoDB transactions need a replica set, JWT storage in browser, overselling stock, duplicate receipts, money precision, NoSQL injection, index management.
4. Request lifecycle diagram in text (React -> Axios -> CORS -> DRF -> auth -> permission -> serializer -> service -> repository -> MongoDB -> response envelope).
5. Security boundaries.
6. The complete folder structure for smarterp/ (backend, frontend, docs, .gitignore, README.md) with one line explaining every folder.
7. Windows installation checklist (Python, Node LTS, Git, VS Code, MongoDB Community Server, MongoDB Compass, Postman) with how to verify each (version commands).
 
Then create docs/PROGRESS.md with sections: Files created, Files modified, Dependencies installed, Commands executed, Features completed, Tests passed, Known problems, Next step.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	docs/architecture.md exists and you understand every risk listed
•	docs/PROGRESS.md exists
•	Nothing was coded yet
Git commit suggestion:
git add .
git commit -m "docs(1.1): architecture planning"

Prompt 1.2 Repository scaffold and Git
Goal: Create folders, .gitignore, README stub, first commit.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Create the repository skeleton exactly as in docs/architecture.md:
 
smarterp/ -> backend/, frontend/, docs/, .gitignore, README.md
 
Requirements:
- .gitignore must cover: Python (venv, __pycache__, .pytest_cache, .coverage), Node (node_modules, dist), .env files (but NOT .env.example), IDE files, OS files, local MongoDB data folders, logs.
- README.md: project name, one-paragraph description, planned tech stack, "Status: Phase 1 in progress".
- Create empty docs files listed in the brief (requirements.md, database-design.md, api-documentation.md, authentication.md, testing.md, deployment.md, user-manual.md, maintenance.md) each with a title and "TODO" only.
- Give me the exact PowerShell commands to: git init, set main branch, first commit, create a GitHub repo, add remote, push, and create the develop branch.
- Suggest the branching strategy (main, develop, feature/*) and 5 example commit messages in Conventional Commits style.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	git status is clean after commit
•	Repo visible on GitHub
•	.env is ignored by git
Git commit suggestion:
git add .
git commit -m "chore(1.2): repository scaffold and git"

Prompt 1.3 Backend skeleton (Django + DRF, no ORM)
Goal: Django project that starts, uses env variables, and does not depend on a SQL database.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Create the backend skeleton in backend/.
 
Tasks:
1. Give PowerShell commands for: creating and activating the virtual environment (py -m venv venv, then .\venv\Scripts\Activate.ps1; if PowerShell blocks scripts run Set-ExecutionPolicy -Scope CurrentUser RemoteSigned), upgrading pip, installing dependencies, freezing versions.
2. requirements.txt with pinned, compatible, supported versions: Django 5.2 LTS (check djangoproject.com for the current LTS and check Django REST Framework compatibility on PyPI before pinning), djangorestframework, pymongo, PyJWT, python-dotenv, django-cors-headers, argon2-cffi, waitress, and gunicorn with the marker "; sys_platform != 'win32'" (gunicorn does not run on Windows). Put pytest, pytest-django and pytest-cov in requirements-dev.txt. Explain each package in one line.
3. Run django-admin startproject config . inside backend/ so manage.py is in backend/ and the settings package is backend/config/. Create the apps with python manage.py startapp and delete models.py, admin.py and migrations from each: common, accounts, employees, departments, inventory, suppliers, purchases, customers, sales, reports. IMPORTANT: common must be a real Django app listed in INSTALLED_APPS, because management commands (init_db later) are only discovered in installed apps. database is a plain Python package (just __init__.py) and is NOT in INSTALLED_APPS. Also create backend/tests/.
4. settings.py - read everything from environment with python-dotenv (DEBUG, SECRET_KEY, ALLOWED_HOSTS, MONGO_URI, MONGO_DB_NAME, JWT secret/issuer/audience/lifetimes, CORS_ALLOWED_ORIGINS, cookie settings):
   - INSTALLED_APPS: only rest_framework, corsheaders and our apps. Do NOT include django.contrib.admin, auth, contenttypes, sessions or messages.
   - MIDDLEWARE: SecurityMiddleware, CorsMiddleware, CommonMiddleware only (no session, authentication or messages middleware - they need the ORM).
   - DATABASES = {"default": {"ENGINE": "django.db.backends.dummy"}}.
   - REST_FRAMEWORK: JSON renderer and parser only; UNAUTHENTICATED_USER = None and UNAUTHENTICATED_TOKEN = None (DRF's default AnonymousUser lives in django.contrib.auth.models, which cannot be imported when the auth app is not installed - this is a common crash); EXCEPTION_HANDLER placeholder; authentication and permission classes are added in Phase 3.
   - PASSWORD_HASHERS with Argon2 first (used standalone from django.contrib.auth.hashers in Phase 3).
   - TIME_ZONE / USE_TZ = True, and BUSINESS_TIMEZONE = Asia/Kolkata (used by reports later).
5. .env.example with every variable and a safe placeholder (never real secrets).
6. pytest.ini with DJANGO_SETTINGS_MODULE for pytest-django.
7. Verify with: python manage.py check and python manage.py runserver, and a simple GET to / returning 404 JSON/HTML without crashing.
 
Explain in simple English why DATABASES is dummy, why the auth and admin apps are removed, and what that means for the project.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	python manage.py check passes with no errors
•	runserver starts without any database error
•	A request to any URL does not raise a django.contrib.auth RuntimeError
•	.env is not committed
Git commit suggestion:
git add .
git commit -m "chore(1.3): backend skeleton"

Prompt 1.4 Frontend skeleton (React + Vite)
Goal: Running React app with Bootstrap, Router and Axios installed.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Create the frontend in frontend/ using Vite + React (JavaScript, not TypeScript).
 
Tasks:
1. Commands to create the project (npm create vite@latest frontend -- --template react) and install: react-router-dom, axios, bootstrap, react-bootstrap (an addition to my list: it gives accessible Modal, Offcanvas and Toast components without custom Bootstrap JavaScript - explain this to me), react-hook-form, yup, @hookform/resolvers, recharts. Dev dependencies: vitest, jsdom, @testing-library/react, @testing-library/jest-dom (used in Phase 10). Configure vitest in vite.config.js and add npm scripts dev, build, test.
2. Create the folder structure: src/assets, components, layouts, pages, services, context, hooks, utils, App.jsx, main.jsx.
3. Import Bootstrap CSS in main.jsx. Add a minimal App with BrowserRouter and a placeholder Home page.
4. frontend/.env.example with VITE_API_BASE_URL=http://localhost:8000/api (never hard-code URLs in code).
5. src/services/apiClient.js: Axios instance reading import.meta.env.VITE_API_BASE_URL, withCredentials true, JSON headers. (Interceptors come in a later phase.)
6. Verify with npm run dev and npm run build.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	npm run dev opens the app
•	npm run build succeeds
Git commit suggestion:
git add .
git commit -m "chore(1.4): frontend skeleton"

Prompt 1.5 Requirements and permission matrix documents
Goal: Write requirements.md and a detailed role/permission matrix that later code will follow.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Write docs/requirements.md with: functional requirements per module (A-J), non-functional requirements, user roles, business rules, acceptance criteria.
 
Then design the permission matrix as a table: rows = permissions (for example employees:read, employees:write, departments:read, departments:write, products:read, products:write, stock:adjust, suppliers:*, purchase:create, purchase:submit, purchase:approve, purchase:receive, customers:*, sales:create, sales:confirm, sales:fulfil, sales:cancel, reports:*, users:manage, audit:read) and columns = Super Admin, HR Manager, Inventory Manager, Purchase Manager, Sales Manager, Employee.
 
Rules to apply: Super Admin has all; each manager owns their module; Employee can only read own profile and change own password; separation of duties (the user who creates a PO should not approve it unless Super Admin - explain your recommendation).
 
Also write the PO status machine (Draft -> Pending Approval -> Approved -> Partially Received -> Received, plus Rejected and Cancelled) and the Sales order status machine, including WHEN stock is reserved and WHEN it is deducted. Put them in docs/requirements.md as allowed-transition tables.
 
Ask me to confirm the rules before continuing.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	You have read and agree with the permission matrix
•	Status transition tables are clear
Git commit suggestion:
git add .
git commit -m "docs(1.5): requirements and permission matrix documents"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 2 - MongoDB Connectivity, Indexes, Health Checks
Objective: Reliable PyMongo connection, shared helpers, index script, and a working health endpoint.
Prompt 2.1 Local MongoDB replica set on Windows (needed for transactions)
Goal: Local MongoDB that supports transactions.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Set up MongoDB for local development on Windows.
 
1. Give instructions to install MongoDB Community Server (as a Windows service), mongosh, MongoDB Compass, and MongoDB Database Tools (mongodump and mongorestore are a separate download). Show how to verify: mongod --version, mongosh --version, mongodump --version.
2. Convert the standalone install into a single-node replica set, in this EXACT order, and explain why the order matters:
   a) Stop the MongoDB Windows service. Open the service config file mongod.cfg (in the MongoDB Server bin folder; needs an Administrator editor). Keep bindIp 127.0.0.1 and add replication: replSetName: rs0. Start the service.
   b) In mongosh run rs.initiate({_id: "rs0", members: [{_id: 0, host: "localhost:27017"}]}) (explicit localhost host so the driver can always resolve it) and confirm rs.status() shows PRIMARY.
   c) Create an admin user with the root role, an application user smarterp_app with readWrite on the smarterp database only, and a test user smarterp_test_user with readWrite on the smarterp_test database only.
   d) Generate a keyFile (give the exact PowerShell command that writes 756 random bytes as base64), store it OUTSIDE the repository (for example C:\data\mongo-keyfile), then add to mongod.cfg: security: keyFile: <path> and authorization: enabled. Explain that MongoDB REQUIRES a keyFile when authorization is enabled on a replica set member, otherwise mongod refuses to start. Restart the service and test login with mongosh.
3. Explain in simple English: what a replica set is, why MongoDB transactions need one, standalone vs replica set vs MongoDB Atlas (as an alternative; do not assume it is free), and the limitations of transactions (time limit, performance cost, keep them short, collections must exist before use inside a transaction).
4. Show the MONGO_URI format, for example mongodb://smarterp_app:<password>@localhost:27017/smarterp?replicaSet=rs0&authSource=smarterp, and put it with placeholders in backend/.env.example. Never write real passwords in any file in the repository.
5. Give commands to start, stop and check the service (Start-Service MongoDB, Stop-Service MongoDB, Get-Service MongoDB), and to back up and restore with mongodump and mongorestore.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	mongosh connects as smarterp_app
•	rs.status() shows PRIMARY
•	Data is still there after restarting the MongoDB service
•	mongod.cfg and keyFile are NOT inside the git repository
Git commit suggestion:
git add .
git commit -m "chore(2.1): local mongodb replica set on windows"

Prompt 2.2 Common utilities
Goal: Shared building blocks used by every module.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/common/ with these files (complete code and tests):
 
1. responses.py - success_response(data, meta=None, status=200) and error_response(code, message, details=None, status) using the envelope from AGENTS.md.
2. exceptions.py - custom exceptions (NotFoundError, ConflictError, ValidationFailed, PermissionDeniedError, InvalidStateTransition, InsufficientStock, DuplicateOperation) and a DRF exception handler that maps them and DRF errors to the envelope. Unknown exceptions -> 500 generic message, logged server-side only. DuplicateKeyError -> 409 without leaking index names.
3. object_id.py - parse_object_id(value) raising a 400 error; is_valid_object_id.
4. sanitize.py - reject keys starting with $ or containing dots in dict input; escape user text used in regex search (re.escape).
5. serialization.py - convert BSON documents to JSON-safe dicts (ObjectId->str, datetime->ISO 8601 UTC, Decimal128->string).
6. money.py - Decimal helpers: to_decimal(), quantize_money() with ROUND_HALF_UP to 2 places, to_decimal128(), from_decimal128(), line_total(), apply_discount(), apply_tax().
7. pagination.py - parse page/page_size (default 20, max 100), sort whitelist, returns skip/limit and builds meta {page, page_size, total, total_pages}.
8. time.py - utc_now().
Write unit tests for every file, including money edge cases (0.1+0.2, rounding, tax on discounted price) and injection attempts like {"$ne": null}.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	pytest passes for common/
•	Money tests prove no float errors
Git commit suggestion:
git add .
git commit -m "feat(2.2): common utilities"

Prompt 2.3 Database connection manager, health check and repository helper
Goal: One shared MongoClient, safe startup, /api/health/.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/database/connection.py and a health endpoint.
 
Requirements:
- A single MongoClient created lazily (thread-safe) from settings; timeouts (serverSelectionTimeoutMS, connectTimeoutMS), retryWrites on, UuidRepresentation configured, tz_aware=True.
- Functions: get_client(), get_db(), get_collection(name), close_client(), ping().
- Never log the URI with password.
- Endpoint GET /api/health/ (public, no auth) using the response helpers from Prompt 2.2: 200 with data {"status":"ok","database":"up"}, or 503 with an error envelope (code SERVICE_UNAVAILABLE) when Mongo is unreachable. No internal error text in the response.
- A base repository helper find_paginated(collection, filter, sort, page, page_size) that uses the pagination helper from Prompt 2.2 and returns (items, total).
- Add a second check for replica-set/transaction support (used later) but do not expose details publicly.
- Tests: ping success, health 200, health 503 with a bad URI (monkeypatch). Show pytest output.
Explain each part in simple English.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	GET http://localhost:8000/api/health/ returns 200
•	Stopping Mongo makes it return 503 without a stack trace
Git commit suggestion:
git add .
git commit -m "feat(2.3): database connection manager, health check and repository helper"

Prompt 2.4 Index creation and initialisation script
Goal: Create the 13 required collections plus 4 supporting ones (17 total) with validators and indexes.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Create backend/database/indexes.py and a Django management command (backend/common/management/commands/init_db.py) named init_db.
 
Collections: users, employees, departments, products, stock_movements, suppliers, purchase_orders, purchase_receipts, customers, sales_orders, payments, invoices, audit_logs, plus refresh_tokens, login_attempts, idempotency_keys, counters (for human-readable numbers like PO-2026-000001).
 
For each collection define: purpose, JSON-Schema validator (collMod/createCollection with validationLevel), and indexes based on real query patterns:
- unique: users.email (lowercase), employees.employee_code, products.sku, suppliers.code, customers.code, purchase_orders.po_number, sales_orders.order_number, invoices.invoice_number, purchase_receipts.receipt_reference, idempotency_keys.(key, scope)
- compound for list/filter queries (e.g. employees department_id+status, stock_movements product_id+created_at desc, purchase_orders status+created_at, sales_orders customer_id+created_at)
- TTL indexes: login_attempts, idempotency_keys, expired refresh_tokens
- text/regex search strategy for names (explain trade-off, pick one)
- for optional fields that must be unique only when present, use a partial unique index with partialFilterExpression (not sparse)
The command must be idempotent (safe to run many times) and print what it created.
Also write docs/database-design.md sections for each collection: purpose, full example document, fields with types, required/optional, validation, unique constraints, indexes, relationships, embed-vs-reference reasoning, sample queries.
Explain how to handle duplicate-key errors and how to clean existing duplicates before creating a unique index.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	python manage.py init_db runs twice without errors
•	Compass shows all collections and indexes
•	docs/database-design.md has all collections
Git commit suggestion:
git add .
git commit -m "feat(2.4): index creation and initialisation script"

Prompt 2.5 Test database strategy
Goal: Tests that never touch real data.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Create the pytest test infrastructure in backend/tests/.
 
- conftest.py: a session fixture that uses a separate, fixed database named smarterp_test (connect with the smarterp_test_user from Prompt 2.1), runs init_db against it, and empties it at the end. Refuse to run if the configured database name is not exactly smarterp_test. Tests run against the real local MongoDB replica set because transactions are tested (mongomock does not support transactions - do not use it).
- A function-scoped fixture that clears all collections between tests.
- Fixtures: api_client, create_user(role), auth_headers(role), seed_department, seed_product, seed_supplier, seed_customer.
- Mark slow transaction tests with a custom marker.
- Explain how to run: all tests, one file, one test, with coverage, and how to read a failure traceback in simple English.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	pytest -q passes
•	Dev database is untouched after running tests
Git commit suggestion:
git add .
git commit -m "test(2.5): test database strategy"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 3 - Authentication, JWT, Refresh Tokens, RBAC
Objective: Secure login, token rotation, logout, rate limiting, audit log, and backend-enforced permissions.
Prompt 3.1 Users, password hashing, JWT service
Goal: Core security building blocks.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement the foundations in backend/accounts/.
 
1. repository.py for users and refresh_tokens (create, find by email/id, update, deactivate). User document: email (lowercase, trimmed), password_hash, full_name, role, is_active, token_version, employee_id (optional ObjectId link to the employees collection, used by the Employee role), last_login_at, created_at, updated_at.
2. passwords.py using django.contrib.auth.hashers (Argon2 first, PBKDF2 fallback) standalone: hash_password, verify_password, needs_rehash; password strength validation (min 10 chars, not common, not equal to email).
3. tokens.py using PyJWT: create_access_token (15 min, claims: sub, role, token_version, jti, iat, exp, iss, aud, type=access), decode_access_token validating signature, exp, iss, aud, type and algorithms=["HS256"] explicitly. No secrets or passwords inside the payload.
4. Refresh tokens: random 256-bit opaque string (secrets.token_urlsafe), only the SHA-256 hash stored in refresh_tokens with family_id, user_id, expires_at, revoked_at, replaced_by, user_agent, ip. Rotation on every refresh; if a revoked token is reused, revoke the whole family (theft detection). Add a short grace window (about 10 seconds): if the immediately previous token of a family is presented again within the window, answer 401 with code REFRESH_RACE but do NOT revoke the family, because two browser tabs (or React StrictMode in development) can legitimately send the same refresh request twice and the browser will already hold the new cookie so a retry succeeds.
5. Users have token_version; incrementing it invalidates all access tokens immediately (used on password change/deactivation).
6. Management command create_superuser_mongo that reads email/password interactively.
Write tests: hash/verify, wrong password, expired token, tampered token, wrong audience, wrong algorithm "none", rotation, reuse detection.
Explain in simple English why refresh tokens are hashed and why access tokens are short-lived.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	All token tests pass
•	You can create a super admin from the command line
Git commit suggestion:
git add .
git commit -m "feat(3.1): users, password hashing, jwt service"

Prompt 3.2 Auth endpoints
Goal: login, refresh, logout, me, change-password.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement the auth API in backend/accounts/ (serializers, services, views, urls).
 
Endpoints (all under /api/auth/):
- POST login/ - validate email+password, check is_active, generic error "Invalid email or password" for every failure (no user enumeration; do a dummy hash check for unknown emails to keep timing similar). Return access token in JSON; set refresh token as HttpOnly, Secure (configurable for local dev), SameSite=Lax/Strict cookie scoped to /api/auth/.
- POST refresh/ - read cookie, rotate, return new access token + new cookie. CSRF protection: require a custom header (X-Requested-With) or double-submit token; explain your choice.
- POST logout/ - revoke the refresh token family, clear cookie, write audit log.
- GET me/ - current user profile.
- POST change-password/ - verify old password, validate new one, bump token_version, revoke all refresh tokens, audit log.
- Password reset (request + confirm) with a single-use, hashed, expiring token; in development print the link to the console instead of sending email, and say what must change for production.
Rate limiting: login_attempts collection with TTL; lock after 5 failures per email+IP for 15 minutes; return 429 with Retry-After.
Audit logging: audit_logs service writing user, action, resource, ip, user_agent, outcome, timestamp for login success/failure, logout, password change, token reuse.
Provide Postman requests for each endpoint with expected status codes, and explain browser security implications of token storage (memory vs localStorage vs cookie).
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Login works in Postman and sets the cookie
•	6th wrong password returns 429
•	Refresh rotates the cookie
•	Logout makes the old refresh token fail
Git commit suggestion:
git add .
git commit -m "feat(3.2): auth endpoints"

Prompt 3.3 DRF authentication class and RBAC
Goal: Every endpoint protected on the backend.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement authentication and authorization.
 
1. accounts/authentication.py: MongoJWTAuthentication (DRF BaseAuthentication). Reads Authorization: Bearer, decodes the token, loads the user from MongoDB on every request, rejects inactive users and mismatched token_version. Returns a lightweight AuthUser object (id, email, role, permissions) with is_authenticated = True. Define authenticate_header() returning "Bearer" so DRF answers 401 (not 403) for missing or invalid tokens.
2. common/permissions_matrix.py: the permission matrix from docs/requirements.md as Python dictionaries (ROLE_PERMISSIONS). Single source of truth.
3. common/permissions.py: HasPermission class factory, usage: permission_classes = [IsAuthenticatedMongo, require("employees:write")]. Also a helper has_permission(user, perm) for services.
4. Set DEFAULT_AUTHENTICATION_CLASSES and DEFAULT_PERMISSION_CLASSES in REST_FRAMEWORK to deny by default (permission classes must handle request.user being None, because UNAUTHENTICATED_USER is None in this project); only health and login/refresh are public.
5. Tests: missing token (401), invalid token (401), expired token (401), revoked/deactivated user (401), wrong role (403), correct role (200), and a parametrized test that walks the whole matrix for a sample protected endpoint.
Explain 401 vs 403 in simple English.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Every route needs a token unless explicitly public
•	Matrix tests pass
Git commit suggestion:
git add .
git commit -m "feat(3.3): drf authentication class and rbac"

Prompt 3.4 User management API
Goal: Super Admin manages users.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement user management in backend/accounts/:
GET/POST /api/users/, GET/PATCH /api/users/{id}/, POST /api/users/{id}/activate/, POST /api/users/{id}/deactivate/, POST /api/users/{id}/reset-password/ (admin-initiated).
Rules: only users:manage permission; cannot deactivate yourself; cannot remove the last active Super Admin; role must be from the allowed list; deactivation bumps token_version and revokes refresh tokens; every action is audit-logged; list supports pagination, search by email/name, filter by role and is_active; never return password hashes.
Also GET /api/audit-logs/ (audit:read, filters by user, action, date range, paginated).
Write tests including the last-super-admin rule and privilege-escalation attempts (PATCH role by a non-admin).
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Deactivated user's existing access token stops working immediately
Git commit suggestion:
git add .
git commit -m "feat(3.4): user management api"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 4 - Employee and Department APIs
Objective: First complete business module built the right way; it becomes the pattern for all later modules.
Prompt 4.1 Departments module
Goal: CRUD with referential integrity.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/departments/ completely (serializers, repository, services, views, urls, tests).
 
Endpoints: GET/POST /api/departments/, GET/PATCH /api/departments/{id}/, GET /api/departments/{id}/employees/.
Fields: code (unique), name, description, manager_employee_id (optional ObjectId), is_active, created_at, updated_at.
Rules: unique code and name (409 on duplicate); manager must be an existing active employee; no hard delete - deactivation is blocked while active employees reference the department; pagination, search, sort whitelist.
Permissions: departments:read (HR, Super Admin, managers read-only as per matrix), departments:write (HR, Super Admin).
Also write the Postman requests (success + negative) and update docs/api-documentation.md for these endpoints in the standard format: method, URL, purpose, role, request body, success response, error response, validation, status codes.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	CRUD works in Postman
•	Duplicate code returns 409
•	Invalid ObjectId returns 400
Git commit suggestion:
git add .
git commit -m "feat(4.1): departments module"

Prompt 4.2 Employees module
Goal: Full employee management.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/employees/ following exactly the same structure as departments.
 
Fields: employee_code (unique), first_name, last_name, email (unique, lowercase), phone (validated), department_id (must exist and be active), designation, joining_date (BSON date, not in the far future), status (active/inactive/on_leave), created_at, updated_at.
Endpoints: GET/POST /api/employees/, GET/PATCH/DELETE /api/employees/{id}/ (DELETE = deactivate, never remove the document), GET /api/employees/me/ for the Employee role (uses users.employee_id) and GET /api/employees/designations/ (distinct designation list for dropdowns). Declare these two routes BEFORE the <id> route, otherwise "me" is parsed as an ObjectId and returns 400.
List: pagination, search (name/email/code, regex-escaped), filter by department_id and status, sort whitelist.
Rules: PATCH must whitelist updatable fields (employee_code immutable); Employee role can read only their own profile; every change writes an audit log.
Write tests for validation, duplicates, department reference, deactivation, permissions per role, and pagination meta.
Add Postman requests and update docs/api-documentation.md.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	All employee tests pass
•	Employee role cannot read others
Git commit suggestion:
git add .
git commit -m "feat(4.2): employees module"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 5 - React Login, Routing, Layout, Employee Pages
Objective: A secure React shell that talks to the real backend.
Prompt 5.1 Auth context and Axios interceptors
Goal: Safe token lifecycle in the browser.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement frontend authentication.
 
1. Store the access token in memory only (React context + module variable), NOT in localStorage. Refresh token is the HttpOnly cookie handled by the browser.
2. src/services/apiClient.js: request interceptor adds Authorization header; response interceptor (never for requests to /auth/login/ or /auth/refresh/ themselves - avoids infinite loops) on 401 calls POST /auth/refresh/ ONCE (queue parallel failed requests behind a single refresh promise), retries the original request, and on failure logs out and redirects to /login. Add the X-Requested-With header required by the backend.
3. src/context/AuthContext.jsx: user, role, permissions, login(), logout(), loading state, silent session restore on page load by calling refresh then /auth/me/, implemented as a module-level single-flight promise so React StrictMode (which runs effects twice in development) does not send two refresh requests; if refresh fails on boot just show the login page (no redirect loop).
4. src/services/authService.js.
5. src/components/ProtectedRoute.jsx (redirects to /login) and RoleRoute/permission check helper. Note in comments that this is UX only; the backend enforces security.
6. src/hooks/useAuth.js.
7. Configure CORS on the backend (exact allowed origin from env - no wildcard, CORS_ALLOW_CREDENTIALS = True, CORS_ALLOW_HEADERS including authorization, content-type, x-requested-with and idempotency-key, because custom headers trigger a preflight request) and explain how CORS and credentials cookies work in simple English.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Refresh page keeps you logged in
•	Expired access token silently refreshes
•	No token in localStorage (check DevTools)
Git commit suggestion:
git add .
git commit -m "feat(5.1): auth context and axios interceptors"

Prompt 5.2 Layout and reusable components
Goal: Professional ERP look.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build the UI foundation using React + Bootstrap 5 (custom CSS in src/assets for polish: consistent colours, spacing, cards with soft shadows).
 
Layouts: AuthLayout (login) and MainLayout (collapsible Sidebar + Navbar + content area, responsive: sidebar becomes an offcanvas menu on mobile).
Components (one file each, documented with JSDoc): Navbar (user menu, logout), Sidebar (role-aware links from a config array with required permission), DashboardCard, DataTable (columns config, loading and empty states, sortable headers), SearchBar (debounced), Pagination, LoadingSpinner, ErrorMessage, ConfirmDialog, FormInput (works with React Hook Form, shows validation errors, accessible labels and aria attributes), Modal wrapper (react-bootstrap), Toast notifications (context + hook, react-bootstrap Toast).
Pages: Login (React Hook Form + Yup, generic error message, loading state), NotFound, Forbidden (403).
Routes in App.jsx with React Router v6 and lazy loading.
Do not build business pages yet.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Login page works against the real API
•	Layout is usable on a phone-width screen
Git commit suggestion:
git add .
git commit -m "feat(5.2): layout and reusable components"

Prompt 5.3 Employees and departments pages
Goal: First end-to-end feature.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build the pages that use the real backend API.
 
- src/services/employeeService.js and departmentService.js (no Axios calls inside components).
- pages/Employees: DataTable with search, department filter, status filter, server-side pagination, sorting; Create/Edit in a modal using React Hook Form + Yup (rules must mirror backend rules); deactivate with ConfirmDialog; success/error toasts; handle 400/409/403 messages from the backend envelope.
- pages/EmployeeProfile (detail view).
- pages/Departments: list, create/edit modal, view employees in the department, manager selector.
- Hide buttons the role cannot use, but remember the backend is the real guard.
- Avoid duplicate requests (cancel stale requests with AbortController, debounce search) and stale data (refetch after mutation).
Create a custom hook usePaginatedList to avoid duplicating code.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Create, edit, deactivate employee from the UI
•	Duplicate employee code shows a friendly error
Git commit suggestion:
git add .
git commit -m "feat(5.3): employees and departments pages"

Prompt 5.4 User management, profile, settings and audit pages
Goal: Remaining account screens from the Phase 3 API.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build the remaining account pages using the Phase 3 API.
 
- pages/Users (users:manage, Super Admin): list with search, role and active filters, pagination; create-user modal (role select, optional employee link); edit; activate/deactivate with ConfirmDialog; admin password reset.
- pages/Profile and pages/Settings: show the current user; change-password form (React Hook Form + Yup, strength rules mirror the backend). On success the backend revokes all sessions, so log the user out and send them to /login with a success message.
- pages/ForgotPassword and pages/ResetPassword (token read from the URL) for the password-reset flow.
- pages/AuditLogs (audit:read): filterable, paginated table (user, action, date range).
- Add them to the Sidebar using permission checks. Services: userService.js and auditService.js.
Use the shared components, hooks and toasts. Remember: hiding menu items is only UX; the backend is the real guard.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Deactivating a user in the UI makes that user's next API call fail with 401
•	Changing your password logs you out
•	Non-admin users get 403 on /users even by typing the URL
Git commit suggestion:
git add .
git commit -m "feat(5.4): user management, profile, settings and audit pages"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 6 - Products, Inventory, Stock Movements
Objective: Auditable inventory where stock can only change through a movement record.
Prompt 6.1 Products and categories
Goal: Catalogue management.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/inventory/ products part.
 
Fields: sku (unique, uppercase), name, description, category, unit, cost_price (Decimal128), selling_price (Decimal128), quantity_on_hand (int, default 0, NOT settable via create/update), reserved_quantity (int, default 0), min_stock_level, is_active, created_at, updated_at.
Endpoints: GET/POST /api/products/, GET/PATCH /api/products/{id}/, GET /api/products/low-stock/ (quantity_on_hand - reserved_quantity <= min_stock_level), GET /api/products/categories/ (declare low-stock/ and categories/ BEFORE the <id> route).
Rules: PATCH rejects any attempt to change quantity fields (400 with clear message); prices > 0; SKU immutable after creation; deactivated products cannot be used on new orders; search by name/SKU; filter by category, active, low-stock; pagination.
Permissions: products:read, products:write (Inventory Manager, Super Admin; others read per matrix).
Tests, Postman requests, and api-documentation updates.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Cannot change quantity through PATCH
•	Duplicate SKU returns 409
Git commit suggestion:
git add .
git commit -m "feat(6.1): products and categories"

Prompt 6.2 Stock movements and adjustments (atomic)
Goal: The most important inventory service.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement the stock engine in backend/inventory/services.py and a reusable idempotency helper in backend/common/idempotency.py.
 
1. One internal function apply_stock_change(session, product_id, quantity_delta, reserved_delta, movement_type, reason, reference_type, reference_id, user_id) used by EVERY module that touches stock. It must: (a) update the product with ONE conditional find_one_and_update (return_document=AFTER) - never read-then-write. Filter rules: for reductions that are not fulfilment, require enough AVAILABLE stock using $expr (quantity_on_hand - reserved_quantity) >= amount; for fulfilment (consumes a reservation) require reserved_quantity >= qty and quantity_on_hand >= qty; for releasing a reservation require reserved_quantity >= qty. (b) compute quantity_before from the returned document and the delta, (c) insert a stock_movements document (product_id, movement_type, quantity_change, reserved_change, quantity_before, quantity_after, reason, reference_type, reference_id, performed_by, created_at) with the same session. Raise InsufficientStock when the conditional update matches nothing. Add reserved_change to the stock_movements validator from Prompt 2.4.
2. Transactions: use client.start_session() with session.with_transaction() (read concern majority/snapshot, write concern majority). PyMongo may re-run the callback after a TransientTransactionError, so the callback must only do database work through the session (no external calls). Keep transactions short.
3. common/idempotency.py: scope = user id + endpoint; the idempotency record (scope, key, request body hash, stored response) is inserted INSIDE the same transaction with a unique index on (scope, key). A repeated request with the same key and same body returns the stored response; same key with a different body returns 422; a concurrent duplicate fails on the unique index or a write conflict and is answered from the stored response after the retry.
4. POST /api/stock-adjustments/ (stock:adjust): body product_id, quantity_change (non-zero integer), reason (required, minimum length); header Idempotency-Key (UUID) required.
5. GET /api/stock-movements/ with filters (product, type, date range, user), pagination, newest first. Movements are append-only: no update or delete endpoints.
6. Tests: adjustment up and down, reduction below available stock rejected (including stock reserved by others), idempotent replay, same key with different body, concurrent adjustments using threads (final quantity must be correct), movement document correctness (quantity_before + change == quantity_after).
Explain race conditions and how conditional updates prevent overselling in simple English.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Concurrency test passes
•	Replaying the same Idempotency-Key does not change stock twice
•	Every stock change has exactly one movement document
Git commit suggestion:
git add .
git commit -m "feat(6.2): stock movements and adjustments"

Prompt 6.3 Inventory pages
Goal: UI for products and stock.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build React pages: Products (list, search, filters, create/edit modal, activate/deactivate), ProductDetail (stock summary + movement history table), Inventory (low-stock highlight, adjustment modal that generates a UUID Idempotency-Key per submit and disables the button while submitting), StockMovements (filterable log). Use services, hooks, toasts and the shared components. Show reserved vs available quantity. Display money values from strings safely (Intl.NumberFormat, never parseFloat arithmetic for totals).
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Double-clicking Adjust does not create two movements
Git commit suggestion:
git add .
git commit -m "feat(6.3): inventory pages"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 7 - Suppliers and Purchase Workflow
Objective: Purchase orders with approval workflow and safe partial goods receipt.
Prompt 7.1 Suppliers module
Goal: Supplier CRUD and history.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/suppliers/ like the other modules. Fields: code (unique, auto-generated via counters if not supplied), name, contact_person, email, phone, address, status, payment_terms, created_at, updated_at. Endpoints: GET/POST /api/suppliers/, GET/PATCH /api/suppliers/{id}/, GET /api/suppliers/{id}/purchase-orders/ (purchase history and outstanding POs). Search, filter by status, pagination, permissions (Purchase Manager, Super Admin write). Inactive suppliers cannot receive new POs. Tests, Postman, docs.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Supplier history endpoint works (empty is fine for now)
Git commit suggestion:
git add .
git commit -m "feat(7.1): suppliers module"

Prompt 7.2 Purchase order creation and approval workflow
Goal: State machine with correct money maths.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/purchases/ part 1.
 
PO document: po_number (generated atomically from counters, format PO-YYYY-000001), supplier_id, items[] (product_id, sku snapshot, name snapshot, quantity_ordered, quantity_received=0, unit_cost Decimal128, line_total), subtotal, tax_total, grand_total (ALL calculated on the server with Decimal; ignore any totals sent by the client), status, status_history[] (status, by, at, note), created_by, approved_by, timestamps.
Endpoints: GET/POST /api/purchase-orders/, GET /api/purchase-orders/{id}/, PATCH (only in Draft), POST {id}/submit/, {id}/approve/, {id}/reject/ (reason required), {id}/cancel/.
Rules: implement an explicit TRANSITIONS dictionary; invalid transition -> 409 InvalidStateTransition; use conditional update {_id, status: expected} so two simultaneous approvals cannot both succeed; the creator cannot approve their own PO unless Super Admin (as in the matrix); products and supplier must exist and be active; duplicate products in one PO are merged or rejected (choose and document); quantities are positive integers.
Tests: every valid transition, every invalid transition (parametrized), total calculation, permission checks, double-approve race.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Invalid transitions return 409
•	Totals ignore client values
Git commit suggestion:
git add .
git commit -m "feat(7.2): purchase order creation and approval workflow"

Prompt 7.3 Goods receipt (transactional, idempotent)
Goal: Only real receipts increase stock.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement POST /api/purchase-orders/{id}/receive/ and the purchase_receipts collection.
 
Body: items[] (product_id, quantity_received), notes; header Idempotency-Key required.
Implement the 11-step flow from my brief inside ONE MongoDB transaction:
1) load PO, 2) check purchases:receive, 3) status must be Approved or Partially Received, 4) each product must be on the PO and quantity_received > 0 and <= (ordered - already received), 5) create unique receipt_reference (RCPT-YYYY-000001) using counters, 6) idempotency check (use common/idempotency.py from Prompt 6.2), 7) insert purchase_receipts document, 8) call apply_stock_change for each line (movement type purchase_receipt, reference = receipt id), 9) update each PO line with update_one: filter {_id, items: {$elemMatch: {product_id, quantity_received: {$lte: quantity_ordered - qty}}}} and update {$inc: {"items.$.quantity_received": qty}} (the filter makes over-receipt impossible even under concurrency; if modified_count is not 1, abort the transaction), 10) set PO status to Partially Received or Received depending on whether all lines are complete, append status_history, 11) write audit log. If any step fails, everything rolls back.
Prevent duplicate receipt processing through the idempotency key AND a unique index on (purchase_order_id, idempotency_key) in purchase_receipts.
Tests: full receipt, partial then final receipt, over-receipt rejected, receive on wrong status, duplicate request with same key returns the same receipt, rollback when one line fails (stock unchanged), two concurrent receipts cannot exceed ordered quantity.
Explain MongoDB transaction limitations and why we also use conditional updates.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Partial receipt gives status Partially Received
•	Failure mid-way leaves stock unchanged
•	Duplicate receipt prevented
Git commit suggestion:
git add .
git commit -m "feat(7.3): goods receipt"

Prompt 7.4 Supplier and purchase pages
Goal: Purchase UI.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build React: Suppliers page (CRUD modal, status), SupplierDetail (purchase history), Purchases list (status badges, filters by status/supplier/date), PurchaseOrderForm (dynamic line items using useFieldArray, product picker with search, live total PREVIEW only with a note that the server calculates the final total), PurchaseOrderDetail (status timeline, action buttons shown by permission and status: Submit, Approve, Reject with reason modal, Receive modal with per-line quantities limited to remaining, Cancel). Generate an Idempotency-Key per receive attempt. Show backend validation errors clearly.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Run the whole flow: create -> submit -> approve -> receive -> stock increased
Git commit suggestion:
git add .
git commit -m "feat(7.4): supplier and purchase pages"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 8 - Customers and Sales Workflow
Objective: Sales orders with reservation, fulfilment, payments, invoices and returns.
Prompt 8.1 Customers module
Goal: Customer CRUD and history.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/customers/: fields code (unique), name, email, phone, billing_address, shipping_address, tax_id (optional), status, credit_limit (optional Decimal128), created_at, updated_at. Endpoints GET/POST /api/customers/, GET/PATCH /api/customers/{id}/, GET /api/customers/{id}/sales-orders/. Search, filters, pagination, permissions (Sales Manager, Super Admin write). Tests, Postman, docs.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Customer CRUD works
Git commit suggestion:
git add .
git commit -m "feat(8.1): customers module"

Prompt 8.2 Sales orders: totals, confirm with reservation
Goal: Decimal-safe calculation and stock reservation.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/sales/ part 1.
 
Define clearly (and write in docs/requirements.md): stock is RESERVED at Confirm (reserved_quantity increases, available = on_hand - reserved) and DEDUCTED at Fulfil (on_hand decreases and reservation is released). Cancel after confirm releases the reservation.
Sales order: order_number (counters, SO-YYYY-000001), customer_id, items[] (product_id, sku, name snapshot, quantity, unit_price taken from the PRODUCT on the server, discount_percent, line_subtotal, line_tax, line_total), subtotal, discount_total, tax_total, grand_total, status (Draft, Confirmed, Fulfilled, Cancelled), return_status (none, partial, full), status_history, payment_status, timestamps.
Calculation order: line subtotal = qty x price; discount applied; tax on discounted amount; ROUND_HALF_UP per line; grand total = sum of lines. Use the common/money.py helpers and Decimal128 storage. Ignore any prices or totals from the client.
Endpoints: GET/POST /api/sales-orders/, GET/PATCH(draft only) /api/sales-orders/{id}/, POST {id}/confirm/ and {id}/cancel/.
Confirm: transaction; for each item conditional update on products: filter {_id, is_active: true, $expr available >= qty}, $inc reserved_quantity; record stock_movements of type reservation through apply_stock_change (quantity_change 0, reserved_change +qty); cancelling a confirmed order records type reservation_release (reserved_change -qty); conditional status update Draft -> Confirmed. Insufficient stock -> 409 with product details.
Tests: totals with several discount/tax combinations, oversell attempt with parallel confirms of the last unit (only one wins), cancel releases reservation, invalid transitions.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Two parallel confirms for the last unit: one succeeds, one fails
Git commit suggestion:
git add .
git commit -m "feat(8.2): sales orders: totals, confirm with reservation"

Prompt 8.3 Fulfilment, payments, invoices, returns
Goal: Complete the sales lifecycle.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/sales/ part 2.
 
1. POST /api/sales-orders/{id}/fulfill/ (Idempotency-Key required): transaction; verify status Confirmed (conditional update to Fulfilled prevents duplicate fulfilment); for each line decrement on_hand and reserved_quantity together with conditional filters; write stock_movements through apply_stock_change (type sale_fulfilment, quantity_change -qty and reserved_change -qty, reference = order id); generate an invoice (invoices collection, INV-YYYY-000001, snapshot of customer and lines, totals, due date); audit log.
2. Payments: POST /api/sales-orders/{id}/payments/ (amount Decimal, method, reference); cannot overpay; payment_status becomes unpaid/partial/paid computed on the server; GET /api/payments/.
3. GET /api/invoices/ and GET /api/invoices/{id}/ (and optionally a printable HTML or PDF later - mark as not implemented if skipped).
4. Returns: POST /api/sales-orders/{id}/returns/ with items, quantities (cannot exceed fulfilled minus already returned), reason; restock creates stock_movements of type sale_return and updates return_status on the order (order status stays Fulfilled); credit note data recorded; fully auditable.
5. Tests: fulfil once, duplicate fulfil rejected, fulfil unconfirmed rejected, partial payments, overpayment rejected, return flow and stock correctness, full integration test: create -> confirm -> fulfil -> pay -> return.
Update api-documentation.md and Postman requests.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Integration test of whole sales flow passes
•	Stock matches movement history
Git commit suggestion:
git add .
git commit -m "feat(8.3): fulfilment, payments, invoices, returns"

Prompt 8.4 Customer and sales pages
Goal: Sales UI.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build React: Customers (CRUD, history), Sales list (filters, status and payment badges), SalesOrderForm (customer select, product picker showing AVAILABLE stock, live total preview only), SalesOrderDetail (status timeline, Confirm, Fulfil, Cancel, Record payment modal, Return modal, link to invoice), InvoiceView page with a clean print stylesheet (window.print). Use idempotency keys on fulfil and payment submissions.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Full UI sales flow works end to end
Git commit suggestion:
git add .
git commit -m "feat(8.4): customer and sales pages"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 9 - Reports, Charts and Dashboard
Objective: All dashboard numbers come from real MongoDB aggregation queries.
Prompt 9.1 Report APIs with aggregation pipelines
Goal: Backend analytics.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Implement backend/reports/ using MongoDB aggregation pipelines (in repository.py, parameters validated first).
 
Endpoints (all permission-checked; date filters date_from/date_to validated; pagination where lists are returned):
- GET /api/reports/dashboard/: total employees (active), departments, products, low-stock count, suppliers, customers, pending purchase orders, monthly sales (current month), purchase statistics, recent transactions (last 10 merged from sales/purchases), sales chart data (last 12 months), inventory statistics. Only return widgets the role may see.
- GET /api/reports/sales/, /inventory/, /low-stock/, /employees/, /departments/, /suppliers/, /purchases/, /monthly-sales/ (group by year-month).
Monthly sales and sales reports count only Fulfilled orders (by fulfilled_at), net of returns. Group by calendar month in BUSINESS_TIMEZONE (Asia/Kolkata) using the timezone option of $dateToString or $dateTrunc. Use Decimal128 aggregation ($sum on Decimal128), return money as strings. Explain which indexes support each pipeline and check with explain().
Tests with seeded data verifying exact numbers, empty-data behaviour, date filters, and role access.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Numbers match hand-calculated test data
Git commit suggestion:
git add .
git commit -m "feat(9.1): report apis with aggregation pipelines"

Prompt 9.2 Dashboard and report pages
Goal: Charts and report UI.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Build React: Dashboard page with DashboardCard widgets and Recharts (monthly sales line/bar chart, purchases vs sales, inventory by category, low-stock list, recent transactions table). Everything comes from /api/reports/dashboard/ - no hard-coded numbers. Reports page with tabs (Sales, Inventory, Purchases, Employees), date range filters, pagination, and CSV export done safely client-side from the returned data. Loading skeletons and error states for each widget; widgets fail independently.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Dashboard has no hard-coded numbers (search the code)
Git commit suggestion:
git add .
git commit -m "feat(9.2): dashboard and report pages"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 10 - Postman Collection and Automated Tests
Objective: Complete test coverage plus a ready-to-import Postman collection.
Prompt 10.1 Postman collection and environments
Goal: A JSON file you can import.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Generate docs/postman/SmartERP.postman_collection.json and SmartERP.local.postman_environment.json (valid Postman v2.1 format).
 
Folders: Health, Auth, Users, Employees, Departments, Products, Stock, Suppliers, Purchase Orders, Receipts, Customers, Sales Orders, Payments and Invoices, Reports, Negative Tests.
Each request: method, URL using {{baseUrl}}, headers, bearer auth using {{accessToken}}, example body, and test scripts asserting the expected status code and response envelope. Login request saves accessToken to the environment; refresh uses the cookie jar; use pre-request scripts to generate {{idempotencyKey}} (pm.variables.replaceIn("{{$guid}}")).
Negative tests: missing token, invalid token, expired token, insufficient permissions, invalid data, duplicate identifiers, invalid ObjectId, duplicate purchase receipt, insufficient inventory, invalid status transition, database unavailable (documented manual step). For the expired-token test add backend/scripts/make_expired_token.py that prints an already-expired access token for a given user and store it in the Postman variable {{expiredToken}}.
Add docs/testing.md section explaining how to import, set environment variables, run the collection with the Collection Runner or newman.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Collection imports into Postman and the runner passes
Git commit suggestion:
git add .
git commit -m "test(10.1): postman collection and environments"

Prompt 10.2 Coverage review and gap filling
Goal: Find missing tests.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Run: pytest --cov=. --cov-report=term-missing. Show the output. Identify untested business rules by comparing code to docs/requirements.md. Then add missing tests, especially: password verification, JWT validation, role matrix, employee and department validation, product validation, stock adjustments, duplicate SKU, purchase approval, receipt processing, sales fulfilment, inventory consistency (sum of stock_movements == on_hand for every product), duplicate transaction prevention, and API response codes. Add two full integration tests: purchase lifecycle and sales lifecycle. Target at least 80 percent coverage on services and permissions. Write docs/testing.md (install, run, interpret failures, test DB strategy). Also add frontend tests for ProtectedRoute, the Axios refresh interceptor, and one form (Vitest + React Testing Library).
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Coverage report shown, key business rules covered
Git commit suggestion:
git add .
git commit -m "test(10.2): coverage review and gap filling"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 11 - Production Setup and Deployment
Objective: Run the app with a production-grade server setup and have a documented deployment process.
Prompt 11.1 Production configuration and run scripts
Goal: Production-ready settings and one-command local start.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Prepare the project for production.
 
1. Backend: split settings into base/dev/prod (or use env switches). Production: DEBUG off, strict ALLOWED_HOSTS, secure cookies, HSTS and security headers, logging to file with rotation, no print statements.
2. Production server: explain that gunicorn does not run on Windows. Give a Windows-friendly option for local production testing (waitress) and the gunicorn setup for a Linux server. Never use runserver in production.
3. Frontend: npm run build, and explain how to serve the dist folder (static hosting or a web server) with SPA fallback to index.html. Explain that VITE_* variables are baked in at build time (set VITE_API_BASE_URL before building) and are public - never put secrets in them.
4. PowerShell helper scripts in scripts/: start-dev.ps1 (starts MongoDB service check, backend, frontend), run-tests.ps1, backup-db.ps1 (mongodump with timestamp).
5. Update README with the exact commands to start everything on Windows.
6. Explain in simple English the difference between development and production configuration.
Verify: backend runs under waitress with prod settings, frontend build is served, /api/health/ returns 200.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Backend runs with the production server and prod settings
•	Frontend build opens in the browser
•	start-dev.ps1 starts the project
Git commit suggestion:
git add .
git commit -m "chore(11.1): production configuration and run scripts"

Prompt 11.2 Deployment guide
Goal: Production documentation.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Write docs/deployment.md. Cover: development vs production configuration; hosting options for frontend, backend and MongoDB (a Linux VPS with systemd, a PaaS, MongoDB Atlas) as neutral trade-offs without assuming anything is free; production environment variables table; running the backend as a service (systemd + gunicorn) behind a reverse proxy (Caddy or nginx) with HTTPS via Let's Encrypt; ALLOWED_HOSTS; CORS; secure cookies and SameSite choices when frontend and API are on different domains; MongoDB authentication, replica set and firewall/network restrictions; running init_db; backup and restore with mongodump/mongorestore and a restore test; logging; monitoring and health checks; error tracking; dependency update policy; a complete pre-launch checklist with checkboxes. Never suggest exposing MongoDB publicly.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Checklist is complete and understandable
Git commit suggestion:
git add .
git commit -m "docs(11.2): deployment guide"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Phase 12 - Final Documentation, Security and Performance Review
Objective: Portfolio-ready project with all documents finished and a hardening pass.
Prompt 12.1 Security review
Goal: Independent audit pass.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Act as a security reviewer. Do NOT change code yet. Audit the whole repository and write docs/security-review.md covering: authentication and token handling, refresh rotation and reuse detection, cookie flags and CSRF, rate limiting, RBAC coverage (list every route and its permission - flag any route without one), NoSQL injection (search for places where request data reaches a query or sort), ObjectId validation, mass-assignment in PATCH endpoints, error leakage, secrets in code or git history, dependency vulnerabilities (pip-audit, npm audit - run them), CORS, security headers, audit log completeness, transaction and idempotency coverage. Rate each finding Critical/High/Medium/Low with file and line and a proposed fix. Then wait for my approval and fix Critical and High findings one at a time with tests.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	Every route has a permission
•	Critical and High issues fixed
Git commit suggestion:
git add .
git commit -m "test(12.1): security review"

Prompt 12.2 Performance review
Goal: Indexes and queries.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Review performance. For every list endpoint and report, run explain("executionStats") against seeded data (generate 10,000+ products/orders with a script in backend/scripts/seed_demo.py using the Faker library as a dev-only dependency in requirements-dev.txt, fake data only). Report any COLLSCAN, missing or unused indexes, N+1 query patterns (loops that call the database), and unbounded queries. Fix them with indexes or $lookup/batched queries, re-measure, and document before/after in docs/maintenance.md (index management section). Check React for unnecessary re-renders and large bundles (lazy loading, code splitting).
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	No COLLSCAN on main list endpoints
Git commit suggestion:
git add .
git commit -m "test(12.2): performance review"

Prompt 12.3 Final documentation set
Goal: Complete all docs.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Complete every document with real content (no TODO left): README.md (introduction, features, stack, architecture diagram, installation on Windows, environment variables table, running, testing, deployment, screenshots placeholder list, troubleshooting), docs/requirements.md, architecture.md, database-design.md, api-documentation.md (verify against the real URL list by running a script that dumps all routes), authentication.md, testing.md, deployment.md, user-manual.md (step-by-step per role with the real screens), maintenance.md (backup/restore, audit-log retention, user deactivation, dependency updates, monitoring, troubleshooting, security maintenance, monthly checklist). Add CONTRIBUTING.md and a CHANGELOG.md. Cross-check docs against the code and list any mismatch you found.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	A new developer could run the project only from README
Git commit suggestion:
git add .
git commit -m "docs(12.3): final documentation set"

Prompt 12.4 Portfolio and interview preparation
Goal: Present the work.
Copy this prompt:
Read AGENTS.md and docs/PROGRESS.md first. Follow the rules in AGENTS.md.
 
Prepare portfolio material in docs/portfolio.md: a 150-word project summary, a resume bullet list (5 strong bullets with measurable details taken from the actual repo such as number of endpoints, tests, coverage), an architecture talking-points sheet, a 5-minute demo script (what to click and say), 25 likely interview questions with concise model answers about this project (transactions, idempotency, JWT rotation, overselling, PyMongo vs ORM trade-offs, RBAC), known limitations and future improvements, and a GitHub profile README snippet. Use only facts that are true of the repository.
 
When finished:
1) Run the tests/commands and show me the real output (never claim success without it).
2) Explain in simple English: what each file does, why it is needed, how data flows frontend -> backend -> MongoDB, common mistakes and how to debug them.
3) Update docs/PROGRESS.md (files created, files modified, dependencies installed, commands run, features completed, tests passed, known problems, next step).
4) List every file you created or changed, and clearly label anything NOT implemented yet.
5) Repeat the acceptance criteria and say whether each one passed.
6) Suggest a git commit message. Then STOP and wait. Do NOT start the next step.
Verify before moving on:
•	You can explain every design decision in the project
Git commit suggestion:
git add .
git commit -m "docs(12.4): portfolio and interview preparation"

Phase gate: do not start the next phase until all checks above pass and your work is pushed to GitHub.
Part B - Fix, Review and Recovery Prompts
Keep these handy. They solve the situations that happen in every AI-assisted project.
F1. Fix a failing test or error
Read AGENTS.md first.
Problem: <paste the FULL error / traceback / failing test output>
What I ran: <command>
Rules: First explain the root cause in simple English. Do not guess - inspect the relevant code and, if needed, add a temporary print or log to confirm. Fix the cause, not the symptom. Do not change unrelated files. Re-run the failing command and show the passing output. If the fix reveals a missing test, add it.

F2. Code review before commit
Read AGENTS.md first. Review ALL uncommitted changes (git diff). Check against AGENTS.md rules: layering (view/service/repository), input validation, injection safety, authorization on every endpoint, Decimal money, transactions and idempotency where required, error leakage, test coverage, naming and duplication. Report issues by severity with file and line. Do not modify code until I approve.

F3. Resume in a new session (context lost)
Read AGENTS.md, docs/PROGRESS.md, docs/architecture.md and docs/requirements.md. Run git log --oneline -15 and git status. Summarise: what is done, what is in progress, known problems, and what the next step should be. Do not write code. Wait for my instruction.

F4. Explain code in simple English (for learning)
Read the files <list files>. Explain them to me like I understand Python, Django and JavaScript but I am new to PyMongo and enterprise architecture. Cover: what each file does, why it exists, how data flows from the request to MongoDB and back, common mistakes, and how to debug. Use short examples. Do not change any code.

F5. Add a missing feature safely
Read AGENTS.md and docs/PROGRESS.md. I want to add: <feature>. First write a short plan: files to change, new collections/indexes, permissions, API contract, tests. Wait for my approval. After approval implement it in small steps, tests first for business rules, update docs/api-documentation.md and Postman collection.

F6. Refactor without breaking behaviour
Read AGENTS.md. Refactor <file/module> to <goal>. Rules: no behaviour change; run the full test suite before and after and show both results; make small commits-worth of changes; if tests are missing for this code, write characterization tests first.

When the AI keeps failing
•	Stop and run git status and git diff to see what changed.
•	Undo bad changes: git restore . (unstaged) or git reset --hard HEAD (everything since the last commit - careful).
•	Start a NEW task. Give a smaller scope: one file, one function, one test.
•	Paste the exact error and the exact file content. Never describe errors from memory.
•	Ask for a plan first and approve it before coding.
•	If it invents libraries or APIs, ask it to cite the official documentation page for the version in requirements.txt.
Common beginner problems with this stack
Problem	Likely cause	Fix
Transactions fail: 'Transaction numbers are only allowed on a replica set'	MongoDB running standalone	Add replication.replSetName rs0 to mongod.cfg and run rs.initiate() (Prompt 2.1), or use MongoDB Atlas
Django complains about database/auth tables	ORM-based apps still enabled	Keep DATABASES dummy; remove admin/sessions/auth apps (Prompt 1.3)
Refresh cookie not sent from React	CORS credentials / SameSite / withCredentials missing	CORS_ALLOW_CREDENTIALS, exact origin (no *), withCredentials: true, correct SameSite and Secure flags
Backend cannot connect to MongoDB	Service stopped, wrong port, or wrong credentials/authSource in MONGO_URI	Check the MongoDB Windows service is running; test the same URI in mongosh
Unique index creation fails	Existing duplicate data	Find and fix duplicates with an aggregation before creating the index
Stock goes negative or double counts	Read-then-write logic, no idempotency	Conditional updates, transactions, Idempotency-Key (Prompts 6.2, 7.3, 8.2)
mongod will not start after enabling authorization	security.keyFile is required when authorization is on for a replica set member	Generate a keyFile and set security.keyFile in mongod.cfg (Prompt 2.1)
RuntimeError about django.contrib.auth.models.Permission / app_label	DRF default UNAUTHENTICATED_USER imports the auth models	Set UNAUTHENTICATED_USER = None and UNAUTHENTICATED_TOKEN = None (Prompt 1.3)
Missing token returns 403 instead of 401	Authentication class has no authenticate_header	Return 'Bearer' from authenticate_header() (Prompt 3.3)
User randomly logged out after page reload (development)	StrictMode runs effects twice -> two refresh calls -> reuse detection	Single-flight refresh promise and the refresh grace window (Prompts 3.1, 5.1)
Browser blocks request with Idempotency-Key header	Header missing from CORS_ALLOW_HEADERS	Add idempotency-key to CORS_ALLOW_HEADERS (Prompt 5.1)
/api/employees/me/ returns 400 invalid ObjectId	Route declared after <id>/	Declare fixed routes before <id>/ routes
ObjectId is not JSON serializable	Raw BSON returned	Use common/serialization.py for every response
Final checklist (end of project)
•	All 12 phases committed and pushed; main branch protected; tags for releases.
•	pytest passes with good coverage; Postman collection passes; frontend builds.
•	The project runs on a fresh Windows machine from a clean clone using only the README.
•	No secrets in git history (check with git log -p or a secret scanner).
•	You can explain the architecture, JWT rotation, transactions, idempotency and overselling prevention without notes.
Part C - Git and GitHub Workflow
Use this workflow for the whole project. It matches the commit suggestions after every prompt.
C1. Branching strategy
Branch	Purpose
main	Always working and releasable. Only receives merges from develop (or hotfix branches). Protect it on GitHub.
develop	Integration branch. Feature branches merge here through pull requests.
feature/<name>	One branch per prompt or small group of prompts, for example feature/auth-jwt, feature/purchase-receipt.
fix/<name>	Bug fixes. Hotfixes for main use hotfix/<name>.

C2. Daily commands
# start a feature
git switch develop
git pull
git switch -c feature/auth-jwt
 
# after each verified prompt
git status
git add .
git commit -m "feat(3.2): auth endpoints"
 
# publish the branch
git push -u origin feature/auth-jwt

C3. Pull request and merge
•	Open a pull request on GitHub from feature/<name> into develop. Title: same style as the commit message. Description: what changed, how you tested it, screenshots for UI.
•	Read the diff yourself (and run Prompt F2, the AI code review) before merging.
•	Merge with 'Squash and merge' or 'Merge commit' (choose one and stay consistent). Delete the branch after merging.
•	Tag releases from main: git tag v0.1.0 then git push origin v0.1.0.
C4. Resolving a merge conflict
git fetch origin
git switch feature/auth-jwt
git merge origin/develop
# Git lists conflicted files. Open each one and look for:
# <<<<<<< HEAD   (your version)
# =======
# >>>>>>> origin/develop   (their version)
# Keep the correct code, delete the three marker lines, then:
git add <file>
git commit
# run the tests again before pushing
git push

C5. Issues
•	Create one GitHub issue per bug or feature. Use labels: bug, feature, docs, security, good first step.
•	Reference issues in pull requests with 'Closes #12' so they close automatically.
•	Keep a small backlog board (GitHub Projects) with columns Backlog, In progress, Review, Done.
C6. Secrets must never be committed
If a .env file or key was committed by mistake: first rotate (change) the secret, then remove the file from tracking with git rm --cached .env, add it to .gitignore, and commit. Removing it from history is not enough on its own because the old value was exposed.
C7. Prompt: create GitHub project files
Read AGENTS.md and docs/PROGRESS.md first.
Create: .github/ISSUE_TEMPLATE/bug_report.md and feature_request.md, .github/pull_request_template.md (checklist: tests pass, docs updated, no secrets, permissions checked), CONTRIBUTING.md (branching strategy, commit message style, how to run tests), and a recommended list of GitHub labels. Explain how to enable branch protection on main in simple English. Do not change application code.
When finished: list files created, update docs/PROGRESS.md, suggest a commit message, then STOP.

