# SmartERP Requirements and Permission Matrix

## Status and scope

This document turns the project brief into a testable requirements baseline. The brief does not explicitly assign letters A–J to its modules; the ten domains below are a clear grouping of the capabilities described in the brief. The owner confirmed the role permissions and workflow rules in this baseline on 2026-10-28.

The application is planned as a React (JavaScript) frontend and a Django REST Framework JSON API backed by MongoDB through PyMongo only. Django ORM, migrations, admin, and Django auth data models are not used for application data.

## Functional requirements by module (A–J)

### A. Accounts, authentication, and user administration

- Users have normalized lowercase email, password hash, full name, role, active state, token version, optional employee link, and UTC creation/update/login timestamps.
- Users with an allowed role can log in; login failures do not reveal whether an email exists.
- Access JWTs are short-lived and validated for signature, expiry, issuer, audience, and token type.
- Refresh credentials are opaque, stored only as hashes, delivered in an HttpOnly cookie, rotated on every successful refresh, and protected by reuse detection.
- Logout revokes the refresh-token family. Password change verifies the old password, applies the password policy, increments the token version, revokes refresh sessions, and writes an audit event.
- Password reset uses single-use, hashed, expiring tokens. Development may print the reset link to the server console; production must deliver it through a configured email service.
- Super Admin can create, edit, activate, deactivate, and initiate password reset for users. Password hashes and refresh credentials are never returned by APIs.
- An administrator cannot deactivate themselves or deactivate the last active Super Admin.
- Login attempts are rate-limited by email and client IP; after five failed attempts, reject attempts for 15 minutes and return `Retry-After`.

### B. Employees and HR

- HR Managers and Super Admins can create, list, view, update, and deactivate employee records.
- Employee records include immutable employee code, name, unique normalized email, validated phone, active department, designation, joining date, employment status, and timestamps.
- Lists support validated pagination, allow-listed sorting, escaped search, and department/status filters.
- An Employee-role user can read only their own linked employee profile and change their own password; they cannot enumerate or read another employee's record.
- Fixed routes such as `me/` and `designations/` are declared before any `<id>/` route.
- Changes are audited; employee records are deactivated rather than hard-deleted.

### C. Departments and organization structure

- HR Managers and Super Admins can create, list, view, update, and deactivate departments.
- Department code and name are unique. Optional department managers must refer to an existing active employee.
- A department cannot be deactivated while active employees are assigned to it.
- A department detail endpoint can list its employees with pagination.
- Invalid ObjectIds return a validation error, and all list filters and sort fields are validated.

### D. Product catalogue and inventory

- Inventory Managers and Super Admins can manage products; authorized roles can read products for their workflows.
- Products have unique uppercase SKU, name, description, category, unit, Decimal128 cost/selling prices, stock quantity, reserved quantity, minimum stock level, active state, and timestamps.
- Product create/update input cannot directly set or change on-hand or reserved quantities. SKU is immutable after creation.
- Product search, category/active/low-stock filters, pagination, and allow-listed sorting are supported.
- Low-stock means available quantity (`quantity_on_hand - reserved_quantity`) is at or below the minimum stock level.
- Every stock change is performed by a stock service and creates an append-only stock movement in the same transaction.
- Stock reductions use conditional atomic updates against available quantity; no read-then-write stock check is permitted.
- Stock adjustments require a reason and an idempotency key. Stock movement queries can filter by product, movement type, date, and user.

### E. Suppliers, purchasing, approvals, and receipts

- Purchase Managers and Super Admins can manage suppliers and purchase workflows; authorized roles can read the relevant supplier/order information.
- Supplier code is unique (generated when omitted); inactive suppliers cannot be used for new purchase orders.
- Purchase orders snapshot supplier/product identity and item prices, and calculate totals on the server with Decimal arithmetic and a documented rounding rule. Client totals are ignored.
- Purchase orders can be drafted, submitted, approved, rejected with a reason, cancelled, and received in full or in parts according to the transition table below.
- By default, the person who creates a purchase order cannot approve it. A Super Admin may approve their own order as an explicit, exceptional override; the action is audited.
- Receipts require an idempotency key. Each receipt validates ordered-vs-received quantities, records a unique receipt reference, updates stock and stock movements, and updates order status in one MongoDB transaction.
- Retried receipts with the same key and body return the original result. Reusing the key with a different body is rejected. Concurrent receipts cannot receive more than the ordered amount.
- Supplier purchase history includes purchase orders and outstanding quantities.

### F. Customers

- Sales Managers and Super Admins can create, list, view, and update customers; authorized users can read customers needed for sales workflows.
- Customer code is unique. Records may include contact details, billing/shipping addresses, optional tax ID, status, optional Decimal128 credit limit, and timestamps.
- Customer search, status filters, pagination, and sales-order history are supported.
- Inactive customers cannot be used to create new sales orders.

### G. Sales, fulfilment, payments, invoices, and returns

- Sales Managers and Super Admins can manage sales workflows; authorized users can read sales orders, invoices, and payments needed for their work.
- A sales order number is allocated from an atomic yearly counter in `SO-YYYY-000001` format. Orders snapshot customer identity/address and product SKU/name; unit prices are always loaded from the product by the server.
- A sales order stores `order_number`, `customer_id`, `items[]`, `subtotal`, `discount_total`, `tax_total`, `grand_total`, status (`draft`, `confirmed`, `fulfilled`, `cancelled`), `return_status` (`none`, `partial`, `full`), `status_history`, `payment_status`, `created_at`, and `updated_at`. Each item stores `product_id`, SKU/name snapshots, quantity, server-derived `unit_price`, `discount_percent`, `tax_percent`, `line_subtotal`, `line_tax`, and `line_total`.
- For each line, calculate `line_subtotal = quantity × server product selling price`; round the discounted line amount to two decimals using `ROUND_HALF_UP`; calculate tax on that rounded discounted amount and round tax to two decimals using `ROUND_HALF_UP`; then `line_total = discounted line amount + line_tax`. Order subtotal, discount total, tax total, and grand total are sums of the rounded line values. Money and percentages use Python `Decimal` and are stored as BSON `Decimal128`. Client-supplied prices and totals are ignored.
- **Confirm reserves stock; it does not deduct stock.** The product update conditionally checks that the product is active and `available = quantity_on_hand - reserved_quantity` is at least the requested quantity. On success, increase `reserved_quantity` by the order quantity; leave `quantity_on_hand` unchanged. The reservation and `reservation` stock movement are committed in the same MongoDB transaction as Draft → Confirmed.
- **Fulfil deducts stock.** When a confirmed order is fulfilled, decrease both `quantity_on_hand` and `reserved_quantity` by the fulfilled quantity; create stock movements, invoice snapshot, and audit record in one transaction. Thus reserved units are deducted from on-hand only at fulfilment, not at confirmation.
- Draft cancellation has no stock effect. **Cancelling a Confirmed order releases its reservation:** decrease `reserved_quantity` by the order quantity, leave `quantity_on_hand` unchanged, write a `reservation_release` movement, and transition Confirmed → Cancelled in one transaction.
- Only Draft → Confirmed and Draft/Confirmed → Cancelled are implemented in Sales part 1. Fulfilment and subsequent sales workflows are planned separately.
- Fulfilment and other retryable critical writes require idempotency keys and are protected against duplicate processing.
- Payments cannot exceed the order's outstanding amount. The server computes unpaid/partial/paid status.
- Returns cannot exceed fulfilled quantities not already returned. Accepted returns restock through the stock service, record movements, update return status, and retain auditable credit-note data.
- Invoices are available through authorized list/detail endpoints. Printable/PDF invoice generation is optional future work unless separately approved.

### H. Reports and dashboard

- Users with report permissions can access only report widgets and data allowed by their role.
- Dashboard/report APIs provide employee, department, product, low-stock, supplier, customer, purchase, and sales summaries, recent transactions, inventory statistics, and chart-ready monthly data as authorized.
- Sales statistics include fulfilled orders only, use fulfilment timestamps, account for returns, group months in the configured business timezone (`Asia/Kolkata`), and return money as strings derived from Decimal128 values.
- Date filters, pagination, and aggregation parameters are validated before query execution.
- Aggregation pipelines are backed by documented indexes and are checked with representative query plans.

### I. Audit trail and operational accountability

- Audit events record actor, action, resource, source IP, user agent, outcome, and timezone-aware UTC timestamp for security-sensitive and business-critical operations.
- At minimum, audit login success/failure, logout, password changes, token reuse, user activation/deactivation, employee changes, purchase-order actions/receipts, stock changes, sales state changes, payments, and returns.
- Audit records are append-only for application users. Only users with `audit:read` may query them; filters and pagination are validated.
- API errors and logs never reveal passwords, secrets, raw database exceptions, or stack traces to clients.

### J. API platform, data integrity, and quality

- All application persistence uses PyMongo repositories. Services own business rules; views parse requests, call services, and format responses; plain DRF serializers validate all request input.
- Reject any user-supplied object key that begins with `$` or contains `.`. Build queries from validated allow-listed fields; escape free-text regex input; allow-list sort keys.
- Validate each URL/body ObjectId and return a client-safe 400 response for invalid IDs.
- Use timezone-aware UTC datetimes and BSON dates. Use Python `Decimal` and BSON `Decimal128` for money; never use float for currency calculations.
- Multi-collection business operations use MongoDB transactions on a replica set, plus conditional updates, unique indexes, and idempotency keys where retries are possible.
- The API uses the standard response envelope:
  - Success: `{"success": true, "data": ..., "meta": {...}}`
  - Error: `{"success": false, "error": {"code": "...", "message": "...", "details": {...}}}`
- Collections, validators, and indexes are initialized through repeatable project tooling, not Django migrations. Tests use an explicitly isolated test database and must not mutate development data.
- Secrets come from environment configuration and are never committed. CORS uses explicit allowed origins; production traffic uses HTTPS and secure cookies.
- Automated tests cover validation, permissions, state transitions, money arithmetic, idempotency, concurrency/transactions, and API error responses. Frontend tests cover key routing, authentication request behavior, and representative forms as those features are implemented.

## Non-functional requirements

| Area | Requirement |
|---|---|
| Security | Enforce authentication and permission checks on the backend, deny protected routes by default, protect refresh-cookie operations against CSRF, use secure password hashing, rotate refresh credentials, and avoid returning sensitive internals. |
| Data integrity | Enforce unique constraints with MongoDB indexes; validate document shapes; use transactions and conditional updates for multi-document/stock operations; maintain immutable audit and stock movement histories. |
| Precision | Store currency as Decimal128 and compute with Decimal using a consistent documented rounding rule. |
| Reliability | Use idempotency keys for retryable critical operations; return stable error codes/envelopes; configure MongoDB timeouts; log diagnostic errors server-side. |
| Performance | Paginate collection lists, allow-list indexed sort/filter fields, avoid unbounded reads and N+1 query patterns, and validate report query plans on seeded data. |
| Privacy | Return only fields required by the caller's permissions; never return password hashes, refresh-token hashes, signing keys, or database credentials. |
| Maintainability | Keep serializers, views, services, repositories, and permission policy separate; use type hints/docstrings for public Python functions and focused React components/hooks. |
| Portability | Support Windows development commands and a replica-set local MongoDB setup; use a Windows-capable development/prod-test server such as Waitress, with Gunicorn reserved for supported non-Windows deployment. |
| Testability | Run backend tests against an isolated test database and frontend tests with Vitest/jsdom; test failure cases and concurrency-sensitive business rules. |
| Usability | Provide role-appropriate navigation, clear form validation and API errors, loading/empty states, and responsive screens. Frontend visibility is never an authorization substitute. |

## User roles

The following role names and responsibilities are the proposed initial RBAC roles:

- **Super Admin:** full system administration and emergency override capabilities; all sensitive overrides must be audited.
- **HR Manager:** owns employee and department administration.
- **Inventory Manager:** owns product catalogue and stock-adjustment operations.
- **Purchase Manager:** owns suppliers and purchase-order workflow, including approval subject to separation of duties.
- **Sales Manager:** owns customers and sales, payment, invoice, and return workflows.
- **Employee:** self-service only: read their own employee profile and change their own password. No general list/read or write access to business modules.

Each user has exactly one assigned role in the initial model. Additional roles, scoped access, or custom permissions require a separate design decision.

## Confirmed permission matrix

`Yes` means the role receives the permission. `Own only` means it is limited to the authenticated user's linked profile/password. `Conditional` means the permission is permitted only when service-level rules pass; in particular a Purchase Manager cannot approve their own PO. `—` means no permission.

| Permission | Super Admin | HR Manager | Inventory Manager | Purchase Manager | Sales Manager | Employee |
|---|---:|---:|---:|---:|---:|---:|
| `users:manage` | Yes | — | — | — | — | — |
| `own-profile:read` | Yes | Yes | Yes | Yes | Yes | Own only |
| `own-password:change` | Yes | Yes | Yes | Yes | Yes | Own only |
| `employees:read` | Yes | Yes | Yes | Yes | Yes | Own only |
| `employees:write` | Yes | Yes | — | — | — | — |
| `departments:read` | Yes | Yes | Yes | Yes | Yes | — |
| `departments:write` | Yes | Yes | — | — | — | — |
| `products:read` | Yes | Yes | Yes | Yes | Yes | — |
| `products:write` | Yes | — | Yes | — | — | — |
| `stock:adjust` | Yes | — | Yes | — | — | — |
| `stock:read` | Yes | Yes | Yes | Yes | Yes | — |
| `suppliers:read` | Yes | — | Yes | Yes | — | — |
| `suppliers:write` | Yes | — | — | Yes | — | — |
| `purchase:create` | Yes | — | — | Yes | — | — |
| `purchase:read` | Yes | — | Yes | Yes | — | — |
| `purchase:submit` | Yes | — | — | Yes | — | — |
| `purchase:approve` | Conditional | — | — | Conditional | — | — |
| `purchase:reject` | Yes | — | — | Yes | — | — |
| `purchase:receive` | Yes | — | Yes | Yes | — | — |
| `purchase:cancel` | Yes | — | — | Yes | — | — |
| `customers:read` | Yes | — | — | — | Yes | — |
| `customers:write` | Yes | — | — | — | Yes | — |
| `sales:create` | Yes | — | — | — | Yes | — |
| `sales:read` | Yes | — | — | — | Yes | — |
| `sales:confirm` | Yes | — | — | — | Yes | — |
| `sales:fulfil` | Yes | — | Yes | — | Yes | — |
| `sales:cancel` | Yes | — | — | — | Yes | — |
| `payments:read` | Yes | — | — | — | Yes | — |
| `payments:record` | Yes | — | — | — | Yes | — |
| `invoices:read` | Yes | — | — | — | Yes | — |
| `returns:process` | Yes | — | — | — | Yes | — |
| `reports:read` | Yes | Yes | Yes | Yes | Yes | — |
| `audit:read` | Yes | — | — | — | — | — |

### Permission notes

- Managers receive read access to adjacent master data needed to perform their own workflows; they do not get write permissions outside their module.
- Inventory Manager can read suppliers/purchase records needed for receiving goods, and can fulfil confirmed sales because stock release/deduction is an inventory operation. Sales Manager can fulfil as well; the backend still executes the shared stock service. Confirm whether fulfilment should be Sales Manager only instead.
- All managers can read report endpoints, but the backend should filter widgets/data according to role. Confirm whether reports should instead be limited to Super Admin.
- Audit-log access is restricted to Super Admin in this proposal because audit events can include personal/security-sensitive activity.
- `Conditional` purchase approval does not mean an unconditional role grant; the service checks the order creator and current status on every approval attempt.

## Business rules

1. **Backend authority:** frontend controls are for usability only. Every protected operation is checked on the backend using the permission matrix and, where needed, service-level ownership/state checks.
2. **Input safety:** validate all request bodies and query parameters with plain serializers. Reject MongoDB operator/dotted keys; never pass raw request input into a MongoDB query.
3. **ObjectIds:** parse every user-provided ObjectId with a shared validator. Invalid values return 400.
4. **No hard deletes for business history:** deactivate master records where appropriate. Preserve purchase, sales, movement, receipt, payment, invoice, and audit history.
5. **Money:** calculate with Decimal; round per line using `ROUND_HALF_UP` to two places unless the owner approves a different currency rule; persist Decimal128 and serialize money as strings.
6. **Time:** persist timezone-aware UTC BSON dates. Convert to `Asia/Kolkata` only for business-facing reporting/grouping.
7. **Stock availability:** available stock is on-hand minus reserved. Product CRUD cannot change either quantity. All stock changes use the stock service and append a stock movement.
8. **Concurrency:** stock reductions/reservations use conditional atomic updates and transactions; never rely on a separate read followed by a write.
9. **Idempotency:** retryable mutations (at minimum stock adjustment, purchase receipt, and sales fulfilment) require a scoped idempotency key. Same key/same body returns the stored result; same key/different body is rejected.
10. **Authentication:** passwords use Django hashers as a standalone utility; access JWTs are short-lived; refresh tokens are random, HttpOnly-cookie delivered, hashed at rest, rotated, and subject to reuse detection.
11. **Error handling:** errors have stable codes/messages in the common envelope; internal exceptions and secrets remain server-side.
12. **URL routing:** fixed paths (`me/`, `low-stock/`, `categories/`, `designations/`) precede parameterized `<id>/` routes.
13. **Purchase separation of duties:** the PO creator cannot approve that PO unless the approver is Super Admin. This is recommended to reduce fraud/error risk by requiring a second person to approve commitments. The exception is explicit and auditable, not an accidental bypass. A business may choose stricter two-person approval that even excludes Super Admin; confirm the proposed exception below.
14. **Sales stock timing:** **Confirm = reserve** (`reserved_quantity += quantity`; `available = quantity_on_hand - reserved_quantity`; on-hand is unchanged). **Fulfil = deduct** (`quantity_on_hand -= quantity` and `reserved_quantity -= quantity`). Cancelling a Confirmed order releases its reservation (`reserved_quantity -= quantity`; on-hand is unchanged). Each stock mutation and its stock-movement record are transactional.
15. **Transaction deployment:** transactions require MongoDB replica-set capability. Critical multi-collection workflows fail safely rather than silently running non-transactionally.

## Purchase order status machine

| Current state | Action | Next state | Conditions and effects |
|---|---|---|---|
| Draft | Submit | Pending Approval | PO has valid active supplier/products and server-calculated totals. |
| Draft | Cancel | Cancelled | Creator or authorized approver may cancel; no stock effect. |
| Pending Approval | Approve | Approved | Authorized approver; creator cannot approve unless Super Admin; conditional state update prevents double approval. |
| Pending Approval | Reject | Rejected | Authorized approver supplies a reason; no stock effect. |
| Pending Approval | Cancel | Cancelled | Authorized creator/manager may cancel; no stock effect. |
| Approved | Receive partial quantity | Partially Received | Receipt validates remaining quantities; transaction creates receipt, stock movements, and stock increase. |
| Approved | Receive all remaining quantity | Received | Same transactional rules; all PO lines become complete. |
| Partially Received | Receive partial quantity | Partially Received | Must be positive and no greater than the remaining quantity on each line. |
| Partially Received | Receive all remaining quantity | Received | Final quantities received atomically; no line can exceed ordered quantity. |
| Draft / Pending Approval | Edit | Same state | Draft may be edited; pending approval edits are not allowed in this proposal. |
| Approved / Partially Received / Received / Rejected / Cancelled | Any other transition | No transition | Return a conflict/invalid-state response; do not modify stock or order history. |

Receipt processing is atomic: insert receipt, update stock through the stock service, update received quantities and status, write audit record, and commit together. A failed operation leaves all these collections unchanged.

## Sales order status machine and stock timing

| Current state | Action | Next state | Stock effect |
|---|---|---|---|
| Draft | Edit | Draft | No stock effect. |
| Draft | Confirm | Confirmed | **Reserve stock now:** for each active product, conditionally require `quantity_on_hand - reserved_quantity >= quantity`, then increase `reserved_quantity`; write a `reservation` movement. Do not change `quantity_on_hand`. All lines and the order transition commit atomically. |
| Draft | Cancel | Cancelled | No stock effect. |
| Confirmed | Fulfil | Fulfilled | **Deduct stock now:** decrease both `quantity_on_hand` and `reserved_quantity` by fulfilled quantity; create movements and invoice in one transaction. (Fulfilment is not part 1.) |
| Confirmed | Cancel | Cancelled | **Release the reservation:** decrease `reserved_quantity`; leave `quantity_on_hand` unchanged; write a `reservation_release` movement in the same transaction as the status transition. |
| Fulfilled | Process partial return | Fulfilled | Restock accepted return quantity through the stock service; set return status to partial. |
| Fulfilled | Process final return | Fulfilled | Restock returned quantities; set return status to full. |
| Cancelled | Any transition | No transition | Terminal state; no stock effect. |
| Fulfilled | Confirm / fulfil / cancel | No transition | Terminal for order state; only valid return/payment operations may continue. |

Sales order `return_status` is separate from the main order status: `none`, `partial`, or `full`. Payment status is separately computed by the server as `unpaid`, `partial`, or `paid`. All confirmation, fulfilment, cancellation, and return stock effects use transactions, conditional updates, and stock movement records. A duplicate fulfilment request must not deduct stock twice.

## Acceptance criteria

These are project-level acceptance criteria to implement and verify across later phases:

1. A new developer can configure the app by following the Windows setup instructions without using Django ORM migrations or admin.
2. No protected API action succeeds without backend authentication and the required permission; an Employee can access only their own profile and password change.
3. Invalid request fields, MongoDB operator/dotted keys, and malformed ObjectIds are rejected with safe, consistent error envelopes.
4. Stock on-hand and reserved quantities can only change through the stock service and every change has a corresponding append-only movement.
5. Concurrent reservations, fulfilments, receipts, and adjustments cannot oversell stock or receive more units than ordered.
6. Replaying a critical request with the same idempotency key does not repeat the operation; reusing the key with a different request body is rejected.
7. PO and sales state transitions match the tables above; invalid transitions return a conflict and do not leave partial writes.
8. Money calculations use Decimal/Decimal128 and match hand-calculated totals under the agreed line-rounding rule.
9. User, authentication, stock, purchase, sales, payment, return, and administrative actions are auditable without exposing credentials or internal errors.
10. Backend and frontend tests, production frontend build, API smoke tests, and documented Postman flows pass before release.
11. The owner has approved this role matrix and workflow baseline before RBAC implementation begins.

## Confirmation record

The owner confirmed the complete permission matrix and workflow proposal on 2026-10-28:

1. Managers have the adjacent-module read access shown in the matrix; all managers have role-filtered report access; audit-log access is Super Admin-only.
2. A Super Admin may approve their own purchase order; all other creators require a different approver.
3. Both Sales Manager and Inventory Manager may fulfil sales.
4. Sales follow Draft → Confirmed → Fulfilled; cancellation is allowed before fulfilment; returns are tracked separately.

These are approved requirements. The backend implements customer read/write endpoints and Sales part 1 currently implements Draft sales-order CRUD plus Confirm/Cancel stock reservation workflows. Fulfilment, payments, invoices, returns, and remaining report workflows are not implemented yet.
