# SmartERP security review

**Review date:** 2026-11-07  
**Scope:** Repository-wide static review of backend, frontend, deployment
configuration, dependency lockfiles, tracked secrets/history, and available
automated tests. This review did not make code changes or test a deployed
system.

## Summary

- **Critical:** none identified.
- **High:** none identified.
- **Medium:** three findings: spoofable client IP weakens login lockout; sales
  returns do not enforce idempotency; two moderate React Router advisories
  affect locked dependency versions.
- **Low:** incomplete audit-event coverage.
- Route inventory: intended public authentication/reset/health endpoints are
  explicitly listed below. No unaccounted business route without a permission
  or ownership check was identified.
- No direct raw-request-data-to-Mongo-query/sort injection path was identified
  in the reviewed routes and repository/service flows.

Severity describes the reviewer's assessment of the application/configuration
impact. Dependency advisories are reported even though their vulnerable
features were not found in current app usage.

## Findings

### SEC-01 — Login lockout can be bypassed with a spoofed forwarded IP

**Severity:** Medium  
**Confidence:** High  
**Files and lines:** [accounts/views.py](/D:/smarterp/backend/accounts/views.py:73),
[accounts/services.py](/D:/smarterp/backend/accounts/services.py:571),
[accounts/repository.py](/D:/smarterp/backend/accounts/repository.py:527),
[deployment.md](/D:/smarterp/docs/deployment.md:194)

The login lockout counts failures by email and client IP, but the view trusts
the first `X-Forwarded-For` value. A client can supply or vary this header;
the example reverse-proxy configuration appends the incoming value rather
than demonstrating that untrusted input is overwritten. This lets an attacker
evade the intended per-IP lockout by changing the header. There is also no
general DRF/API throttling. The public password-reset request has no throttle;
production reset delivery is currently disabled by the service.

**Proposed fix:** Derive client addresses only from a configured trusted proxy
chain (have the edge proxy overwrite client-supplied forwarding headers) or
use the direct peer address when no trusted proxy is configured. Make failure
counters atomic. Add bounded login and password-reset throttles and suitable
general API controls before enabling production reset email. Avoid relying
only on IP limits.

**Remediation status:** Fixed in this review follow-up by using `REMOTE_ADDR`
instead of the untrusted forwarded header for lockout/audit attribution.
Regression-tested; see the remediation entry in [PROGRESS.md](/D:/smarterp/docs/PROGRESS.md).

### SEC-02 — Sales return operation is not idempotent

**Severity:** Medium  
**Confidence:** High  
**Files and lines:** [sales/views.py](/D:/smarterp/backend/sales/views.py:197),
[sales/services.py](/D:/smarterp/backend/sales/services.py:735)

`POST /api/sales-orders/{id}/returns/` checks `returns:process` and executes
the return in a transaction, but it does not require an idempotency key or use
the shared idempotency mechanism. Retrying a request can process another
return, increase stock again, and issue another credit note for the same
intended operation. The quantity cap does not prevent duplicate credits for
orders with enough units.

**Proposed fix:** Require a validated idempotency key, store/replay the result
through the shared idempotency mechanism, and bind the key to a hash of the
validated request body. Test replay and same-key/different-body cases against
a replica-set test database.

### SEC-03 — Locked React Router versions have two moderate advisories

**Severity:** Medium (dependency advisory; app exploitability not confirmed)  
**Confidence:** High for affected dependency versions; low for app-level
exploitation  
**Files and lines:** [package-lock.json](/D:/smarterp/frontend/package-lock.json:3062),
[package.json](/D:/smarterp/frontend/package.json:1)

`npm audit` reported:

1. `GHSA-wrjc-x8rr-h8h6` — open redirect via a backslash in `<Link>` and
   `useNavigate`; advisory range `>=6.0.0 <7.18.0`.
2. `GHSA-337j-9hxr-rhxg` — constructor injection via
   `deserializeErrors()` in React Router SSR hydration; advisory range
   `>=6.4.0 <7.18.0`.

The lockfile contains React Router 6.30.6. The reviewed SPA navigation targets
were fixed or built from server-generated ObjectIds, and no SSR hydration path
was found, so neither issue was confirmed exploitable through current
application behavior.

**Proposed fix:** Upgrade to a patched compatible React Router release,
review release notes, run navigation/authentication tests, and rerun
`npm audit`. Do not treat the absence of a demonstrated current exploit as a
reason to leave a known vulnerable version indefinitely.

### SEC-04 — Audit events do not cover all sensitive mutations and auth events

**Severity:** Low  
**Confidence:** High  
**Files and lines:** [customers/services.py](/D:/smarterp/backend/customers/services.py:58),
[suppliers/services.py](/D:/smarterp/backend/suppliers/services.py:48),
[departments/services.py](/D:/smarterp/backend/departments/services.py:99),
[inventory/services.py](/D:/smarterp/backend/inventory/services.py:50),
[accounts/views.py](/D:/smarterp/backend/accounts/views.py:237),
[accounts/services.py](/D:/smarterp/backend/accounts/services.py:571)

Customer, supplier, department, and product create/update operations do not
consistently create actor-attributed audit events. Successful refresh-token
rotations are not audit-logged, and failed login events are recorded only
when the lockout threshold is reached. This reduces the ability to investigate
who changed business records or identify suspicious authentication activity.

**Proposed fix:** Add secret-free audit events with actor, action, resource,
outcome, and timestamp for security-relevant mutations and authentication
events. Where feasible, write mutation and audit records atomically. Never
include credentials, token values, or reset secrets.

## Route and permission inventory

“Public” below means no bearer-authenticated permission is required; where
applicable, a route still requires a refresh cookie, custom request header,
or one-time reset token. Permission names are the backend permission-matrix
capabilities. Methods are stated for each route.

### Health and authentication

Source: [config/urls.py](/D:/smarterp/backend/config/urls.py:1),
[accounts/urls.py](/D:/smarterp/backend/accounts/urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/health/` | GET | Public liveness check; does not check MongoDB |
| `/api/auth/login/` | POST | Public; login lockout is present but its IP input can be spoofed (SEC-01) |
| `/api/auth/refresh/` | POST | Refresh cookie + `X-Requested-With`; no bearer permission |
| `/api/auth/logout/` | POST | Authenticated; `X-Requested-With`; no named capability |
| `/api/auth/me/` | GET | `own-profile:read` |
| `/api/auth/change-password/` | POST | `own-password:change` |
| `/api/auth/password-reset/request/` | POST | Public; reset delivery disabled in production; no request throttle |
| `/api/auth/password-reset/confirm/` | POST | Public to bearer auth; one-time reset-token gated |
| Unmatched paths | Any | JSON 404; no data access |

### Users and audit logs

Source: [user_urls.py](/D:/smarterp/backend/accounts/user_urls.py:1),
[audit_urls.py](/D:/smarterp/backend/accounts/audit_urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/users/` | GET, POST | `users:manage` |
| `/api/users/{id}/` | GET, PATCH | `users:manage` |
| `/api/users/{id}/activate/` | POST | `users:manage` |
| `/api/users/{id}/deactivate/` | POST | `users:manage` |
| `/api/users/{id}/reset-password/` | POST | `users:manage` |
| `/api/audit-logs/` | GET | `audit:read` |

### Departments and employees

Source: [departments/urls.py](/D:/smarterp/backend/departments/urls.py:1),
[employees/urls.py](/D:/smarterp/backend/employees/urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/departments/` | GET | `departments:read` |
| `/api/departments/` | POST | `departments:write` |
| `/api/departments/{id}/` | GET, PATCH | GET: `departments:read`; PATCH: `departments:write` |
| `/api/departments/{id}/employees/` | GET | `departments:read` |
| `/api/employees/` | GET | `employees:read`; employee role cannot list the directory |
| `/api/employees/` | POST | `employees:write` |
| `/api/employees/me/` | GET | Employee role plus linked-profile ownership check; no named capability |
| `/api/employees/designations/` | GET | `employees:read`; employee role excluded |
| `/api/employees/{id}/` | GET | `employees:read`; employee role limited to linked record |
| `/api/employees/{id}/` | PATCH, DELETE | `employees:write` |

### Customers and suppliers

Source: [customers/urls.py](/D:/smarterp/backend/customers/urls.py:1),
[suppliers/urls.py](/D:/smarterp/backend/suppliers/urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/customers/` | GET | `customers:read` |
| `/api/customers/` | POST | `customers:write` |
| `/api/customers/{id}/` | GET, PATCH | GET: `customers:read`; PATCH: `customers:write` |
| `/api/customers/{id}/sales-orders/` | GET | `customers:read` and `sales:read` |
| `/api/suppliers/` | GET | `suppliers:read` |
| `/api/suppliers/` | POST | `suppliers:write` |
| `/api/suppliers/{id}/` | GET, PATCH | GET: `suppliers:read`; PATCH: `suppliers:write` |
| `/api/suppliers/{id}/purchase-orders/` | GET | `purchase:read` |

### Products and stock

Source: [inventory/urls.py](/D:/smarterp/backend/inventory/urls.py:1),
[stock_urls.py](/D:/smarterp/backend/inventory/stock_urls.py:1),
[movement_urls.py](/D:/smarterp/backend/inventory/movement_urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/products/` | GET | `products:read` |
| `/api/products/` | POST | `products:write` |
| `/api/products/low-stock/` | GET | `products:read` |
| `/api/products/categories/` | GET | `products:read` |
| `/api/products/{id}/` | GET, PATCH | GET: `products:read`; PATCH: `products:write` |
| `/api/stock-adjustments/` | POST | `stock:adjust` |
| `/api/stock-movements/` | GET | `stock:read` |

### Purchase orders

Source: [purchases/urls.py](/D:/smarterp/backend/purchases/urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/purchase-orders/` | GET | `purchase:read` |
| `/api/purchase-orders/` | POST | `purchase:create` |
| `/api/purchase-orders/{id}/` | GET | `purchase:read` |
| `/api/purchase-orders/{id}/` | PATCH | `purchase:create` |
| `/api/purchase-orders/{id}/submit/` | POST | `purchase:submit` |
| `/api/purchase-orders/{id}/approve/` | POST | `purchase:approve` |
| `/api/purchase-orders/{id}/reject/` | POST | `purchase:reject` |
| `/api/purchase-orders/{id}/cancel/` | POST | `purchase:cancel` |
| `/api/purchase-orders/{id}/receive/` | POST | `purchase:receive` |

### Sales orders, payments, and invoices

Source: [sales/urls.py](/D:/smarterp/backend/sales/urls.py:1),
[payment_urls.py](/D:/smarterp/backend/sales/payment_urls.py:1),
[invoice_urls.py](/D:/smarterp/backend/sales/invoice_urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/sales-orders/` | GET | `sales:read` |
| `/api/sales-orders/` | POST | `sales:create` |
| `/api/sales-orders/{id}/` | GET | `sales:read` |
| `/api/sales-orders/{id}/` | PATCH | `sales:create` |
| `/api/sales-orders/{id}/confirm/` | POST | `sales:confirm` |
| `/api/sales-orders/{id}/cancel/` | POST | `sales:cancel` |
| `/api/sales-orders/{id}/fulfill/` | POST | `sales:fulfil` |
| `/api/sales-orders/{id}/payments/` | POST | `payments:record` |
| `/api/sales-orders/{id}/returns/` | POST | `returns:process`; missing idempotency (SEC-02) |
| `/api/payments/` | GET | `payments:read` |
| `/api/invoices/` | GET | `invoices:read` |
| `/api/invoices/{id}/` | GET | `invoices:read` |

### Reports

Source: [reports/urls.py](/D:/smarterp/backend/reports/urls.py:1).

| Route | Methods | Access |
|---|---|---|
| `/api/reports/dashboard/` | GET | `reports:read` |
| `/api/reports/sales/` | GET | `reports:read` and `sales:read` |
| `/api/reports/monthly-sales/` | GET | `reports:read` and `sales:read` |
| `/api/reports/inventory/` | GET | `reports:read`, `products:read`, and `stock:read` |
| `/api/reports/low-stock/` | GET | `reports:read`, `products:read`, and `stock:read` |
| `/api/reports/employees/` | GET | `reports:read` and `employees:read` |
| `/api/reports/departments/` | GET | `reports:read` and `departments:read` |
| `/api/reports/suppliers/` | GET | `reports:read` and `suppliers:read` |
| `/api/reports/purchases/` | GET | `reports:read` and `purchase:read` |

No unaccounted business route without a permission or ownership check was
identified. Public health/auth/reset routes are intentional; the employees
`/me/` route uses role and linked-record checks rather than a named matrix
capability. SEC-01 describes the identified weakness in the login defense.

## Control review

| Area | Review result |
|---|---|
| Authentication and access tokens | JWT uses pinned HS256, issuer/audience checks, short lifetime, current-user/token-version validation. |
| Refresh rotation/reuse | Opaque refresh tokens are stored hashed, rotated, and checked for reuse. Refresh/logout require the refresh cookie or authentication and `X-Requested-With` as applicable. Successful rotation is not audit-logged (SEC-04). |
| Cookies and CSRF | Production forces refresh cookie `Secure`; `HttpOnly` defaults true but is configurable and should remain true. Default `SameSite=Lax`. Cookie endpoints use a custom request header. Cross-site deployments need a separately reviewed CSRF design and browser testing. |
| Rate limiting | Login uses a five-failure/15-minute lockout keyed by email and IP, but forwarded IP spoofing can evade it (SEC-01). No general DRF or proxy throttle was found. Password-reset request has no throttle; production email is disabled currently. |
| RBAC | Business routes in the inventory above require a capability or ownership check. No unaccounted unprotected business route was found. Frontend hiding is not relied on as authorization. |
| NoSQL injection | No direct raw request-to-query/sort flow identified. Serializers validate inputs, filters reject operator-like keys, search escapes regex input, and sort fields are allowlisted in reviewed paths. |
| ObjectId validation | Reviewed URL/body ObjectIds are parsed with the shared validation helper before use. |
| PATCH mass assignment | Reviewed PATCH serializers constrain writable fields; no unrestricted request-body update flow identified. |
| Error leakage | API exception handling returns a generic error envelope for unexpected errors and logs server-side; no DB traceback/credential response path identified in reviewed handlers. |
| Secrets and git history | `.env.example` contains placeholders; `backend/.env` is not tracked. A credential-signature scan across 128 tracked commits found no matches. This is not a general entropy-based secret scan and cannot guarantee absence of all secrets. |
| CORS | Wildcard origins are rejected; credentials use configured exact origins. |
| Security headers | Production enables HTTPS redirect, HSTS, `nosniff`, same-origin referrer policy, COOP, and frame denial. CSP is not configured; no exploitable injection path was identified in this review. |
| Audit logging | Audit-log read route is permission-protected. Mutation and authentication event coverage is incomplete (SEC-04). |
| Transactions/idempotency | Stock adjustment, purchase receipt, sales fulfilment, and payment paths use shared idempotency and transactional safeguards. Sales returns are the exception (SEC-02). Live replica-set transaction behavior was not verified. |

## Commands and test results

The security-review agent ran:

- Backend: `.\venv\Scripts\python.exe -m pytest -q` from `backend\` — exit 0,
  `377 passed in 67.30s`.
- Frontend: `npm test -- --run` from `frontend\` — exit 1; 40 test files passed,
  1 failed, 115 tests passed and 1 failed. `PurchaseOrderForm.test.jsx` timed
  out at 5 seconds.
- Focused retry: `npx vitest run src/pages/PurchaseOrderForm.test.jsx` from
  `frontend\` — exit 0, `1 passed in 3.01s`.
- Django check: `.\venv\Scripts\python.exe manage.py check` from `backend\` —
  exit 0, `System check identified no issues (0 silenced).`
- Initial root `npm audit --json` — exit 1, `ENOLOCK` because the repository
  root has no lockfile. The audit was rerun from `frontend\`.
- `pip-audit` — not run: command not found. It was not installed.
- Git status was clean and `git diff --check` passed during the review.

This author also reran `npm audit --json` from `frontend\`; observed summary:

```text
npm audit exit code: 1
Vulnerability counts: {"info":0,"low":0,"moderate":2,"high":0,"critical":0,"total":2}
Package: react-router; severity: moderate; range: 6.0.0 - 7.17.0
Advisory: React Router: Open redirect via backslash in <Link> and useNavigate (CVE-2025-68470 bypass); range: >=6.0.0 <7.18.0; url: https://github.com/advisories/GHSA-wrjc-x8rr-rhxg
Advisory: React Router: Arbitrary Constructor Injection via deserializeErrors() in React Router SSR Hydration; range: >=6.4.0 <7.18.0; url: https://github.com/advisories/GHSA-337j-9hxr-rhxg
Package: react-router-dom; severity: moderate; direct: True; range: 6.0.0-alpha.0 - 7.17.0
pip-audit: command not found (not installed)
```

The full suite has one reported transient frontend timeout, followed by a
passing focused retry. Investigate/re-run the full frontend suite before
relying on a green CI result. No dependency was installed and no code fix was
made as part of this review.

## Follow-up and approval gate

No Critical or High findings were identified. Medium/Low findings and the
dependency advisories are documented above. **No fixes have been made.**
Per the requested workflow, wait for the user's approval before changing code;
if approved, address Critical/High findings one at a time with targeted tests.

This is a repository review, not a penetration test. Live MongoDB replica-set
behavior, production proxy/header configuration, deployed infrastructure,
browser-specific cookie behavior, and exhaustive secret entropy scanning
remain unverified.
