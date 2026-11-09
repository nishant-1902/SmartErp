# SmartERP Portfolio Material

> **Evidence note:** Metrics below describe the repository and its latest local
> verification, not production usage. Automated backend tests use PyMongo-shaped
> fakes; they do not prove live MongoDB transaction behavior.

## Project summary (150 words)

SmartERP is a full-stack ERP application for managing people, departments, inventory, suppliers, purchasing, customers, sales, payments, invoices, and reports. Its interface uses React and Vite, while Django REST Framework serves a JSON API. MongoDB is accessed through PyMongo repositories; Django’s ORM and admin are not used for application data. Plain DRF serializers validate all incoming requests, services enforce rules, and repositories perform database operations. Backend permissions govern access independently of frontend navigation. Stock writes use conditional transactional updates; money uses Python Decimal and BSON Decimal128. Authentication uses short-lived JWT access tokens and rotated, hashed refresh tokens delivered in HttpOnly cookies. The repository includes 59 resolved API route patterns, 384 backend tests, 116 frontend tests, and 92% measured backend test coverage. A synthetic 10,000-record benchmark informed index/query changes. Repository docs cover Windows setup, deployment, database design, testing, and maintenance. Live replica-set transaction behavior and production email delivery still need deployment-level verification.

## Resume bullets

- Built a React/Vite ERP interface and Django REST Framework API spanning nine business apps, with **59 URL patterns** verified from Django’s resolver.
- Implemented a PyMongo-only persistence architecture with app repositories, service-layer workflows, serializer validation, and a backend role/permission matrix.
- Added transactional purchasing, sales, and inventory workflows with conditional stock updates, movement records, and idempotency controls for supported operations; tests cover reservation races and duplicate requests.
- Implemented JWT access authentication and HttpOnly refresh-cookie rotation with hashed server-side refresh tokens and reuse detection.
- Verified **384 backend tests**, **116 frontend tests**, and **92% backend coverage**; benchmarked synthetic datasets of **10,000 products, 10,000 sales orders, and 10,000 purchase orders** to guide indexes and list/report query changes.

## Architecture talking points

### Request and data flow

```text
React screen
  -> Axios JSON request (bearer access token; refresh cookie when needed)
  -> Django URL resolver and DRF request handling
  -> authentication and backend permission checks
  -> plain serializer validates/normalizes input
  -> view calls service
  -> service enforces workflow rules and transaction boundary
  -> repository issues typed PyMongo operations
  -> MongoDB collections, validators, and indexes
  <- service result, JSON-safe serialization, standard response envelope
  <- React updates the screen
```

### Points to explain in an interview

- **Django without ORM data:** Django and DRF provide HTTP routing, middleware,
  parsing, serializers, and response handling. `DATABASES` uses the dummy
  backend; PyMongo repositories are the only application data access path.
- **Layering:** serializers validate transport input; views stay thin; services
  own business rules; repositories own database queries.
- **Stock correctness:** confirmations reserve rather than deduct stock. A
  conditional update checks available quantity, and fulfillment changes
  on-hand/reserved quantities while writing movements inside a transaction.
- **Retry safety:** the shared idempotency helper scopes keys, binds them to
  validated request content, and stores the result transactionally for
  supported actions. Sales returns are a known exception and do not currently
  enforce an idempotency key.
- **Money and time:** monetary calculations use `Decimal` and BSON `Decimal128`;
  persisted timestamps are timezone-aware UTC datetimes.
- **Security:** frontend route/link hiding is UX only. The backend permission
  matrix is authoritative. Inputs reject unsafe Mongo keys and validate IDs.
- **Operational limit:** transactions require MongoDB replica-set support.
  Standard test runs use fakes, so live transaction behavior still needs
  integration verification against a dedicated replica set.

## Five-minute demo script

**Prepare before the demo:** start the configured backend, MongoDB replica set,
and Vite frontend. Use a disposable demo account and synthetic customer,
product, supplier, and order data. Confirm the account’s role and that the demo
environment is not connected to production.

| Time | Click / show | Suggested narration |
| --- | --- | --- |
| 0:00–0:35 | Open **Login**, sign in, land on **Overview**. | “This is a React single-page app backed by a DRF API. The dashboard data is fetched from the backend and filtered by permission.” |
| 0:35–1:20 | Open **Products**, then a product detail; show stock and available quantity. | “The browser is only the interface. The backend validates access and calculates stock availability.” |
| 1:20–2:05 | Open **Inventory**, demonstrate a small justified stock adjustment and confirmation. | “Stock changes go through a service that records a movement. Supported adjustment operations use an idempotency key so retries can return the saved result.” |
| 2:05–3:05 | Open **Purchase Orders**, show an approved order and receive a partial quantity. | “Receiving goods updates the order and inventory together. The multi-document write is designed for a MongoDB replica-set transaction.” |
| 3:05–4:05 | Open **Sales Orders**, show a draft/confirmed order; confirm, then show fulfillment if the demo dataset allows. | “Confirmation reserves stock with a conditional update, which prevents two competing orders from taking the last unit. Fulfillment deducts stock and writes movement/invoice records.” |
| 4:05–4:40 | Open **Stock Movements**, filter to the product or order. | “The movement history makes the stock change traceable.” |
| 4:40–5:00 | Show **Reports** or **Users** (depending on role), then close with the architecture diagram. | “The current suite verifies 384 backend tests and 116 frontend tests. Live replica-set integration and production email still need environment-level verification.” |

If a workflow is unavailable to the demo role, use a separately authorized
demo account prepared in advance. Do not bypass a permission check during the
presentation.

## Interview questions and concise model answers

1. **What does SmartERP do?**  
   It manages core ERP workflows for employees, departments, stock, purchasing,
   suppliers, customers, sales, payments, invoices, and reports.

2. **How is the application structured?**  
   React/Vite is the UI; Django REST Framework routes and validates API calls;
   services hold business logic; app repositories access MongoDB using PyMongo.

3. **Why use Django if the project does not use its ORM?**  
   Django/DRF still provide mature HTTP, middleware, URL routing, serializers,
   and request/response tooling. The ORM is deliberately excluded from the data
   layer.

4. **Why PyMongo instead of Django ORM?**  
   The application uses MongoDB documents and explicit Mongo transactions,
   indexes, and validators. PyMongo keeps those operations direct and visible;
   the trade-off is that schema/index evolution and relationship consistency
   are handled explicitly by the project.

5. **Why separate services and repositories?**  
   Services express workflow rules without embedding query construction;
   repositories centralize PyMongo operations. This makes authorization,
   transaction boundaries, and data queries easier to review and test.

6. **How are API inputs validated?**  
   Plain DRF serializers validate and normalize request fields. Unsafe keys and
   unknown fields are rejected, and URL/body ObjectIds are validated before
   service calls.

7. **Where are MongoDB transactions used?**  
   Multi-document operations such as purchase receipt, stock adjustment, and
   sales fulfillment use service-level transaction handling. The MongoDB
   deployment must support replica-set transactions.

8. **How do you avoid overselling?**  
   Sales confirmation uses conditional stock updates that require enough
   available quantity. It reserves stock; fulfillment later deducts on-hand
   and reserved quantities. A read-then-write check alone would be race-prone.

9. **What does idempotency do here?**  
   Supported operations accept a UUID key, scope it to an operation, bind it to
   the request content, and transactionally save/replay the result. Reusing a
   key with different content is rejected.

10. **Are all write endpoints idempotent?**  
    No. The security review found sales returns do not yet enforce an
    idempotency key. That is a known duplicate-credit/restock risk and a future
    fix.

11. **How does JWT authentication work?**  
    The API issues short-lived access JWTs. The browser keeps access tokens in
    memory and sends the bearer token on protected API calls.

12. **How are refresh tokens protected?**  
    The refresh token is delivered in an HttpOnly cookie, stored hashed in
    MongoDB, rotated on refresh, and checked for reuse. Reuse can revoke the
    token family and require sign-in again.

13. **How is access revoked when a user is deactivated?**  
    The backend rejects inactive users during authentication; token-version and
    refresh-token revocation mechanisms also invalidate prior sessions.

14. **What is the role of frontend route guards?**  
    They improve navigation and user experience. The backend permission matrix
    is the security boundary and checks every protected API operation.

15. **How do you reduce NoSQL injection risk?**  
    Serializers validate allow-listed fields, unsafe `$` and dotted keys are
    rejected, and repositories build queries from validated values rather than
    passing request dictionaries to MongoDB.

16. **How do you handle money safely?**  
    Calculations use Python `Decimal`, stored values use BSON `Decimal128`, and
    API values are serialized as decimal strings. Binary floats are avoided.

17. **How are stock movements kept consistent?**  
    Stock changes go through service functions that also create movement
    records, within the applicable transaction boundary.

18. **How do you handle concurrent updates?**  
    Conditional updates encode the expected quantity/state in the database
    operation; transactions group related writes. Tests cover competing sales
    confirmations using a fake transaction implementation.

19. **What do you return on API errors?**  
    A consistent JSON envelope with a stable error code, safe message, and
    details. Internal database errors and stack traces are not returned.

20. **What does the test suite prove?**  
    It covers API behavior, validation, permissions, workflows, and frontend
    interactions. The latest recorded run has 384 backend tests, 116 frontend
    tests, and 92% backend coverage. It does not prove live MongoDB transaction
    isolation.

21. **How were database indexes selected?**  
    Repository query shapes were measured with `explain("executionStats")` on
    synthetic data, including 10,000 products, sales orders, and purchase
    orders. The benchmark is representative, not production traffic.

22. **What are the current performance limits?**  
    Unanchored substring searches, exact counts, distinct category/designation
    results, broad monthly reports, and full-summary aggregations can still
    scale with data volume.

23. **How are secrets configured?**  
    Backend secrets are read from environment configuration and example files
    contain placeholders. Frontend `VITE_*` values are public build-time values
    and must never hold secrets.

24. **What must production deployment provide?**  
    Strong secrets, explicit hosts and CORS origins, HTTPS, secure cookies,
    protected logs, and a private MongoDB replica set. Production email delivery
    needs provider configuration and has not been verified here.

25. **What would you improve next?**  
    Add idempotency to sales returns, run live replica-set integration tests,
    configure and verify production reset email, and set operational policy for
    audit retention and report/search limits.

## Known limitations and future improvements

### Known limitations — current repository facts

- Sales-return requests do not use the shared idempotency mechanism.
- Standard backend tests use in-memory PyMongo-shaped fakes; live replica-set
  transaction isolation has not been verified by those tests.
- Production password-reset email delivery is not enabled/configured.
- There is no database-backed readiness endpoint; `/api/health/` is a liveness
  check.
- Audit-log retention is an operator policy; the application does not
  automatically purge audit events.
- Synthetic benchmarks do not represent all optional filters, production
  traffic, or every query plan.
- No production screenshots or browser-profile traces are included.

### Future improvements

- Add and test idempotency for sales returns, including same-key/different-body
  rejection and replay behavior.
- Run integration and concurrency tests against an isolated real replica set.
- Configure a production reset-email provider and add bounded throttling for
  public authentication/reset endpoints.
- Agree and implement audit retention, backup/recovery targets, and monitoring
  alerts for deployments.
- Define limits or pagination for distinct filter values and very broad report
  ranges; benchmark realistic workloads before changing indexes.
- Resolve current dependency advisories through a reviewed update and rerun
  dependency audits.

## GitHub profile README snippet

```markdown
### SmartERP

Full-stack ERP built with React/Vite, Django REST Framework, and MongoDB via
PyMongo. The project includes role-based API permissions, service-layer
workflows, stock movement tracking, and JWT access with rotated HttpOnly refresh
cookies.

- 59 resolved API URL patterns
- 384 backend tests and 116 frontend tests in the latest recorded full run
- 92% backend test coverage
- Synthetic query benchmark: 10,000 products, 10,000 sales orders, and 10,000
  purchase orders

**Stack:** React, JavaScript, Vite, Django, DRF, PyMongo, MongoDB, pytest,
Vitest. Live replica-set transaction verification and production email setup
remain deployment tasks.
```
