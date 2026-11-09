# Contributing to SmartERP

## Before changing code

Read `AGENTS.md`, `docs/PROGRESS.md`, and the relevant module documentation.
Keep each change focused on one step. Explain any stack trade-off before
implementation. Do not add dependencies without stating why.

## Architecture rules

- Use PyMongo through the app's `repository.py`; do not add Django models,
  migrations, admin data, ORM access, or `django.contrib.auth` data.
- Put business workflows in `services.py`; keep views thin.
- Validate all input with plain DRF serializers. Reject Mongo operators and
  dotted keys, validate every ObjectId, and never construct a query from raw
  request data.
- Use `Decimal`/BSON `Decimal128` for money and timezone-aware UTC timestamps.
- Enforce permissions on the backend. Stock changes must write stock movement
  records; multi-document workflows use transactions and idempotency controls.
- Keep secrets in environment files, never in source control. Preserve the
  standard JSON response envelope and avoid leaking database errors.
- Keep fixed URL paths before `<id>/` routes.

## Change process

1. Describe the behavior being changed and inspect its frontend, API, service,
   repository, and tests as applicable.
2. Implement the smallest complete change. Update relevant docs and
   `docs/PROGRESS.md` with files changed, dependencies, commands, results,
   known issues, and the next step.
3. Run checks appropriate to the change. For a full local verification, run
   `scripts/run-tests.ps1` from PowerShell. Do not state that a check passed
   unless it was run and its output observed.
4. Review `git diff --check`, inspect the final diff, and provide a suggested
   commit message. Do not claim production integration behavior based only on
   mocked or in-memory tests.

## Windows development commands

```powershell
Set-Location backend
py -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements-dev.txt
python manage.py check
python -m pytest
Set-Location ..\frontend
npm ci
npm test
npm run lint
npm run build
```

For MongoDB integration tests, use only the dedicated test replica-set
connection. Those fixtures may clear documents in the test database. Do not
point test settings at development or production data.

## Documentation and review

Keep API endpoint documentation synchronized with the URL resolver output from
`backend/scripts/dump_routes.py`. Describe current implementation separately
from proposals and unverified operations. Use synthetic data in screenshots
and examples. Review authorization, validation, error envelopes, transaction
boundaries, indexes, and user-facing failure messages for relevant changes.
