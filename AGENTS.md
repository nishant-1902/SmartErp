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
