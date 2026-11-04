# API Documentation

Base URL: `http://localhost:8000/api`

All department endpoints require a bearer access token and use the standard JSON
success/error envelopes. Department list endpoints use `page` (default `1`) and
`page_size` (default `20`, maximum `100`). Search is a literal, case-insensitive
substring search. Sort fields are explicitly allowlisted.

## Customers

Customer endpoints require a bearer access token. Customer list and detail reads
require `customers:read`; create and update require `customers:write` (Sales
Manager or Super Admin). Customer sales-order history requires both
`customers:read` and `sales:read` (Sales Manager or Super Admin); Inventory
Managers can read sales orders for fulfilment but not customer history.

### List customers

- **Method and URL:** `GET /api/customers/`.
- **Purpose:** Return a paginated, searchable customer list.
- **Query parameters:** `page` (default `1`), `page_size` (default `20`,
  maximum `100`), `search`, `status` (`active` or `inactive`), `sort_by`
  (`code`, `name`, `email`, `phone`, `status`, `created_at`, or `updated_at`),
  and `sort_order` (`asc` or `desc`).
- **Search:** Literal, case-insensitive match against code, name, email, phone,
  or tax ID. Search text is escaped before it is used in MongoDB.
- **Success response (`200`):** Standard envelope with `data.customers` and
  pagination metadata.
- **Validation:** Unknown/unsafe query keys, invalid status values, and
  unsupported sort fields return `400`.

### Create customer

- **Method and URL:** `POST /api/customers/`.
- **Role:** Sales Manager or Super Admin (`customers:write`).
- **Request body:**

  ```json
  {
    "code": "CUS-001",
    "name": "Acme Stores",
    "email": "ap@acme.example",
    "phone": "+1 (555) 123-1111",
    "billing_address": {
      "line1": "10 Main Street",
      "city": "Austin",
      "postal_code": "78701",
      "country": "US"
    },
    "shipping_address": null,
    "tax_id": "TAX-12345",
    "status": "active",
    "credit_limit": "5000.00"
  }
  ```

- **Fields:** `code` and `name` are required. Email, phone, billing/shipping
  addresses, tax ID, and credit limit may be omitted or null; status defaults to
  `active`. Addresses require `line1`, `city`, and `country`; other address
  fields are optional.
- **Validation:** Code is trimmed, uppercased, and unique. Tax IDs are trimmed,
  uppercased, and unique when present. Email is normalized to lowercase. Phone
  accepts 7–15 digits with an optional leading `+` and common separators.
  Credit limits are non-negative decimal amounts with at most two fractional
  digits and must be sent as decimal strings, not JSON floating-point numbers.
  Unknown/unsafe fields are rejected.
- **Success response (`201`):** Standard envelope with `data.customer`.
- **Status codes:** `201`, `400`, `401`, `403`, `409`.

### Get and update customer

- **Methods and URL:** `GET` or `PATCH /api/customers/{id}/`.
- **Roles:** Reads require `customers:read`; PATCH requires `customers:write`
  (Sales Manager or Super Admin).
- **PATCH body:** Any non-empty subset of the create fields. A supplied address
  replaces that full address object; send `null` to clear it. Server-owned
  timestamps and search fields cannot be written.
- **Validation:** `{id}` must be a MongoDB ObjectId. Missing customers return
  `404`; duplicate code or tax ID returns `409`.
- **Success response (`200`):** Standard envelope with `data.customer`.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`.

### Customer sales-order history

- **Method and URL:** `GET /api/customers/{id}/sales-orders/`.
- **Roles:** Requires both `customers:read` and `sales:read` (Sales Manager or
  Super Admin). Inventory Managers can read sales orders to fulfil them but do
  not receive customer-master/history access.
- **Query parameters:** `page` (default `1`), `page_size` (default `20`,
  maximum `100`), and optional `status` (`draft`, `confirmed`, `fulfilled`, or
  `cancelled`).
- **Success response (`200`):** Standard envelope with `data.sales_orders` and
  pagination metadata. Orders are sorted newest-first.
- **Validation:** `{id}` must be a valid ObjectId; a missing customer returns
  `404`. The route is declared before the customer detail route.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

## Sales orders — part 1

Sales-order list/detail reads require `sales:read`. Creating or editing a Draft
order requires `sales:create`; Confirm requires `sales:confirm`; Cancel requires
`sales:cancel`. The permission matrix grants management actions to Sales
Managers and Super Admins; `sales:read` is granted to Sales Managers,
Inventory Managers (for fulfilment), and Super Admins.

### List and create sales orders

- **Methods and URL:** `GET` and `POST /api/sales-orders/`.
- **List filters:** `page` (default `1`), `page_size` (default `20`, maximum
  `100`), `status` (`draft`, `confirmed`, `fulfilled`, or `cancelled`), and
  `customer_id`.
- **Create body:** `customer_id` and a non-empty `items` array. Each item takes
  `product_id`, positive integer `quantity`, and optional decimal-string
  `discount_percent` and `tax_percent` (each defaults to `"0"` and ranges from
  `0` to `100`).
- **Server-owned values:** The server requires an active customer and active
  products, snapshots customer and product details, reads each product's
  `selling_price`, allocates `SO-YYYY-000001` from the yearly MongoDB counter,
  and calculates all prices/totals. Submitted `unit_price`, `sku`, `name`,
  order number, and total fields are ignored.
- **Calculation and money:** For each line, `line_subtotal = quantity ×
  server unit price`; the discounted line amount is rounded to two decimal
  places with `ROUND_HALF_UP`; tax is calculated on that discounted amount and
  rounded to two places; `line_total = discounted amount + line_tax`. Order
  subtotal, discount, tax, and grand total sum the rounded line values. Values
  are calculated with the shared Decimal helpers and stored as Decimal128.
- **Success response (`201`):** Standard envelope with `data.sales_order`.
- **Status codes:** `201`, `400`, `401`, `403`.

### Read and edit sales orders

- **Methods and URL:** `GET` or `PATCH /api/sales-orders/{id}/`.
- **Role:** Reads require `sales:read`; PATCH requires `sales:create`.
- **PATCH:** Draft only; accepts `customer_id` and/or replacement `items`.
  Recalculates server-owned prices and totals. Client price and total values
  are ignored. Empty patches and edits after Draft return `400` and `409`
  respectively.
- **Success response (`200`):** Standard envelope with `data.sales_order`.
- **Validation:** `{id}` must be an ObjectId. Missing orders return `404`.

### Confirm and cancel

- **URLs:** `POST /api/sales-orders/{id}/confirm/` and
  `POST /api/sales-orders/{id}/cancel/`; both accept an empty JSON object.
- **Permissions:** Confirm requires `sales:confirm`; Cancel requires
  `sales:cancel`.
- **Confirm:** Draft → Confirmed in one snapshot/majority MongoDB transaction.
  For each line, a conditional product update requires an active product and
  `quantity_on_hand - reserved_quantity >= quantity`, then increases
  `reserved_quantity` and records a `reservation` stock movement. On-hand
  quantity is unchanged. Insufficient stock returns `409 insufficient_stock`
  with the product ID, SKU, name, requested quantity, and available quantity;
  all order/stock/movement writes roll back.
- **Cancel:** Draft → Cancelled has no stock effect. Confirmed → Cancelled
  decrements each line's `reserved_quantity`, does not change on-hand, and
  writes a `reservation_release` movement in the same transaction as the
  conditional status transition.
- **State rules:** Confirm only accepts Draft. Cancel accepts Draft or
  Confirmed. Repeated or otherwise invalid transitions return `409` without
  changing stock or history.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`.
- Fulfilment, payments, invoices, and returns are documented under [Sales orders — part 2](#sales-orders--part-2).

## Sales orders — part 2

Fulfilment requires `sales:fulfil` (Sales Manager, Inventory Manager, or Super
Admin according to the permission matrix). Payment recording requires
`payments:record`; payment and invoice reads require `payments:read` and
`invoices:read`; return processing requires `returns:process`.

### Fulfil and issue an invoice

- **Method and URL:** `POST /api/sales-orders/{id}/fulfill/`.
- **Headers:** `Idempotency-Key` is required and must be a UUID. Send an empty
  JSON object as the body.
- **Behavior:** Confirmed only. In one snapshot/majority transaction, each
  product's on-hand and reserved quantities are conditionally reduced by the
  order quantity and a `sale_fulfilment` movement is recorded. The order
  conditionally transitions to Fulfilled, its `fulfilled_at` timestamp and
  status history are updated, and one invoice snapshot plus an audit event are
  created. Invoice numbers use `INV-YYYY-000001`; due date defaults to 30 days
  after issue.
- **Idempotency:** Repeating the same request with the same key replays the
  original response. A distinct key cannot fulfil the order twice.
- **Success response (`200`):** `data.sales_order` and `data.invoice`.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`, `422`.

### Record and list payments

- **Record method and URL:** `POST /api/sales-orders/{id}/payments/`.
- **Request body:** `amount` as an exact decimal string, `method` (`cash`,
  `bank_transfer`, `card`, or `other`), and optional `reference`.
- **Headers:** `Idempotency-Key` is required and must be a UUID. A retry with
  the same key and body replays the original payment; reuse with a different
  body is rejected.
- **Behavior:** Only fulfilled orders accept payments. Overpayment is rejected
  with `409`; payment inserts, paid-total compare-and-set, server-derived
  `payment_status` (`partial` or `paid`), and an audit event share a MongoDB
  transaction. New orders start `unpaid`.
- **List method and URL:** `GET /api/payments/`; requires `payments:read`.
- **Filters:** `page`, `page_size` (maximum `100`), `customer_id`,
  `sales_order_id`, `method`, and `status`.
- **Success response:** Record returns `201` with `data.payment` and
  `data.sales_order`; list returns `200` with `data.payments` and pagination
  metadata.
- **Status codes:** `201`, `200`, `400`, `401`, `403`, `404`, `409`.

### List and read invoices

- **Methods and URLs:** `GET /api/invoices/` and `GET /api/invoices/{id}/`;
  both require `invoices:read`.
- **List filters:** `page`, `page_size` (maximum `100`), `customer_id`, and
  `sales_order_id`.
- **Behavior:** Invoices are immutable customer/item/totals snapshots, emitted
  once during fulfillment. Invoice listing and detail return historical data
  without reading mutable customer or product records.
- **Success response:** List returns `200` with `data.invoices` and pagination
  metadata; detail returns `200` with `data.invoice`.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.
- **Not implemented:** Printable HTML or PDF invoice generation.

### Process returns

- **Method and URL:** `POST /api/sales-orders/{id}/returns/`; requires
  `returns:process`.
- **Request body:** A non-empty `items` array of unique `product_id` and
  positive integer `quantity` lines, plus a 3–500 character `reason`.
- **Behavior:** Fulfilled orders only. Each line is conditionally limited to
  fulfilled quantity minus prior returns. A transaction increments returned
  quantities, restocks through `apply_stock_change` as `sale_return`, writes
  the stock movement, creates an auditable credit note (`CN-YYYY-000001`), and
  updates `return_status` to `partial` or `full`. The sales order remains
  Fulfilled. The credit note records the returned amount; no refund is issued.
- **Success response (`201`):** `data.sales_return` and `data.sales_order`.
- **Status codes:** `201`, `400`, `401`, `403`, `404`, `409`.

## Suppliers

Supplier endpoints require a bearer access token. Supplier list and detail reads
require `suppliers:read`; writes require `suppliers:write` (Purchase Manager or
Super Admin). Supplier purchase history requires `purchase:read` (Purchase
Manager, Inventory Manager, or Super Admin).

### List suppliers

- **Method:** `GET`
- **URL:** `/api/suppliers/`
- **Purpose:** Return a paginated, searchable supplier list.
- **Query parameters:** `page` (default `1`), `page_size` (default `20`,
  maximum `100`), `search`, `status` (`active` or `inactive`), `sort_by`
  (`code`, `name`, `contact_person`, `email`, `status`, `created_at`, or
  `updated_at`), and `sort_order` (`asc` or `desc`).
- **Success response (`200`):** Standard success envelope with
  `data.suppliers` and pagination metadata.
- **Validation:** Search is a literal, case-insensitive match against code,
  name, contact person, email, or phone. Unknown/unsafe query keys, invalid
  statuses, and unsupported sort fields are rejected.
- **Status codes:** `200`, `400`, `401`, `403`.

### Create supplier

- **Method:** `POST`
- **URL:** `/api/suppliers/`
- **Purpose:** Create a supplier record.
- **Role:** Purchase Manager or Super Admin (`suppliers:write`).
- **Request body:**

  ```json
  {
    "name": "Northwind Supply",
    "contact_person": "Ada Lovelace",
    "email": "buying@example.com",
    "phone": "+1 (415) 555-0123",
    "address": {
      "line1": "1 Main Street",
      "line2": null,
      "city": "London",
      "region": null,
      "postal_code": "SW1A 1AA",
      "country": "United Kingdom"
    },
    "status": "active",
    "payment_terms": "Net 30"
  }
  ```

- **Optional field:** `code`. When omitted, the API atomically allocates a
  `SUP-000001` style code using the MongoDB `counters` collection.
- **Success response (`201`):** Standard success envelope with `data.supplier`.
- **Validation:** Code is uppercased and unique. Email is validated and stored
  lowercase; phone accepts 7–15 digits with an optional leading `+` and common
  separators, and is stored without separators. Address is either `null` or an
  object with `line1`, `city`, and `country`; other address fields are optional.
  Status is `active` or `inactive`. Unknown/unsafe keys are rejected.
- **Status codes:** `201`, `400`, `401`, `403`, `409`.

### Get supplier

- **Method:** `GET`
- **URL:** `/api/suppliers/{id}/`
- **Purpose:** Return one supplier.
- **Role:** `suppliers:read`.
- **Success response (`200`):** Standard success envelope with `data.supplier`.
- **Validation:** `{id}` must be a valid MongoDB ObjectId.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

### Update supplier

- **Method:** `PATCH`
- **URL:** `/api/suppliers/{id}/`
- **Purpose:** Update a non-empty subset of supplier fields.
- **Role:** Purchase Manager or Super Admin (`suppliers:write`).
- **Request body:** Any non-empty subset of `code`, `name`, `contact_person`,
  `email`, `phone`, `address`, `status`, and `payment_terms`. Replacing a
  non-null address requires the full address shape.
- **Success response (`200`):** Standard success envelope with `data.supplier`.
- **Validation:** Field rules match create; duplicate codes return `409`.
  Supplier records are retained when their status changes to inactive.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`.

### Supplier purchase history

- **Method:** `GET`
- **URL:** `/api/suppliers/{id}/purchase-orders/`
- **Purpose:** Return paginated purchase history and outstanding purchase
  orders, each with its own pagination metadata.
- **Role:** `purchase:read`.
- **Query parameters:** `page` (default `1`) and `page_size` (default `20`,
  maximum `100`), applied separately to both lists.
- **Success response (`200`):** Standard success envelope with
  `data.purchase_orders`, `data.outstanding_purchase_orders`, and corresponding
  pagination metadata under `meta.purchase_orders` and
  `meta.outstanding_purchase_orders`. Each item includes
  `quantity_outstanding` (`quantity_ordered - quantity_received`).
- **Outstanding definition:** Includes `pending_approval`, `approved`, and
  `partially_received` orders. Draft, received, rejected, and cancelled orders
  remain in the full purchase history but are not outstanding.
- **Validation:** `{id}` must be a valid ObjectId; a missing supplier returns
  `404`. The route is declared before the supplier detail route.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

## Purchase orders

Every endpoint requires a bearer token. Reads require `purchase:read`;
creation and Draft edits require `purchase:create`; workflow actions require
their matching `purchase:submit`, `purchase:approve`, `purchase:reject`, or
`purchase:cancel` permission.

### List and create purchase orders

- **Methods and URLs:** `GET` and `POST` `/api/purchase-orders/`.
- **List filters:** `page`, `page_size`, `status`, `supplier_id`, `start_date`,
  and `end_date`. The date filters are timezone-aware ISO-8601 datetimes and
  match the PO creation timestamp; when both are supplied, start must not be
  after end.
- **Create body:** `supplier_id`, `items` (each with `product_id`,
  `quantity_ordered`, and `unit_cost`), and `tax_rate` as a decimal percentage
  from `0` to `100`.
- **Calculated fields:** `po_number`, snapshots, `quantity_received`,
  `line_total`, `subtotal`, `tax_total`, `grand_total`, status, and timestamps
  are generated by the backend. Any submitted totals are ignored. Monetary
  inputs must be decimal strings; for example, `"unit_cost": "12.34"`.
- **Calculation:** Line totals and tax are calculated with Decimal and rounded
  to two decimal places using `ROUND_HALF_UP`. `tax_total` is
  `subtotal * tax_rate / 100`; `grand_total` is `subtotal + tax_total`.
- **Rules:** Supplier and products must exist and be active; duplicate product
  IDs are rejected; quantities must be positive integers. PO numbers use an
  atomic yearly counter and the `PO-YYYY-000001` format.
- **Initial state:** New orders are Draft and include a Draft status-history
  entry. Success responses contain `data.purchase_orders` for lists or
  `data.purchase_order` for a single created order.

### Read and edit purchase orders

- **Methods and URL:** `GET` or `PATCH` `/api/purchase-orders/{id}/`.
- **Rule:** `{id}` must be an ObjectId. PATCH only changes a Draft order and
  recalculates its totals; supplier, items, and tax rate are optional, but the
  patch body must contain at least one editable field.

### Submit, approve, reject, and cancel

- **URLs:** `POST /api/purchase-orders/{id}/submit/`,
  `/approve/`, `/reject/`, or `/cancel/`.
- **Allowed transitions:** Draft → Pending Approval or Cancelled; Pending
  Approval → Approved, Rejected, or Cancelled. Other transitions return
  `409 invalid_state_transition`.
- **Reject body:** `{"reason": "..."}`; reason is required and becomes the
  status-history note.
- **Separation of duties:** The creator cannot approve their PO unless they
  are a Super Admin. Approval uses a conditional Mongo update so concurrent
  approvals cannot both succeed.

All order responses use the standard JSON envelope. Invalid IDs and request
fields return 400, unauthenticated callers return 401, missing permissions
return 403, missing orders return 404, and invalid state transitions return
409.

### Receive purchase order

- **Method and URL:** `POST /api/purchase-orders/{id}/receive/`.
- **Role:** Requires `purchase:receive` (Purchase Manager, Inventory Manager,
  or Super Admin).
- **Header:** Required UUID `Idempotency-Key`.
- **Body:** `{"items":[{"product_id":"...","quantity_received":2}],"notes":"..."}`.
  `notes` is optional; product IDs must be unique in the request, and each
  quantity must be a positive integer no greater than the PO line's remaining
  ordered quantity.
- **Success (`201`):** Standard envelope containing `data.purchase_receipt`,
  including its `RCPT-YYYY-000001` reference.
- **Replay behavior:** Repeating the same key and body returns the original
  receipt without increasing stock again. Reusing the key with a different
  body returns `422 idempotency_key_reused`.
- **Atomic effects:** Receipt record, stock updates and movements, PO received
  quantities/status history, audit log, receipt counter, and stored
  idempotency response are written in one MongoDB transaction. A failure rolls
  all of them back.
- **Deployment requirement:** MongoDB transactions require a replica set or
  sharded cluster; standalone MongoDB cannot run this operation. Transactions
  add coordination and resource overhead, so receipt transactions must stay
  short and perform database work only.
- **Status:** Only Approved or Partially Received POs may be received. The
  order becomes Partially Received until every ordered line is complete, then
  Received. Concurrent line updates use a conditional quantity cap; stale or
  excessive receipts fail without over-receiving.
- **Status codes:** `201`, `400`, `401`, `403`, `404`, `409`, `422`.

## Employees

### List employees

- **Method:** `GET`
- **URL:** `/api/employees/`
- **Purpose:** Return a paginated employee directory with search and filters.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`employees:read`). Employee-role accounts cannot read the directory.
- **Request body:** None. Query parameters: `page`, `page_size`, `search`,
  `department_id`, `status` (`active`, `inactive`, `on_leave`), `sort_by`
  (`employee_code`, `first_name`, `last_name`, `email`, `department_id`,
  `designation`, `joining_date`, `status`, `created_at`, `updated_at`), and
  `sort_order` (`asc`, `desc`). Default order is newest first.
- **Success response (`200`):** Standard success envelope with
  `data.employees` and pagination metadata (`page`, `page_size`, `total`,
  `total_pages`). Employee values are projected to public directory fields.
- **Error response:** Standard error envelope.
- **Validation:** Search is regex-escaped and matches name, email, or employee
  code. `department_id` must be a valid ObjectId. Query keys, status, sort,
  page, and page size are validated; maximum page size is 100.
- **Status codes:** `200`, `400`, `401`, `403`.

### Create employee

- **Method:** `POST`
- **URL:** `/api/employees/`
- **Purpose:** Create an employee and audit the change.
- **Role:** HR or Super Admin (`employees:write`).
- **Request body:**

  ```json
  {
    "employee_code": "EMP-001",
    "first_name": "Ada",
    "last_name": "Lovelace",
    "email": "ada@example.com",
    "phone": "+1 (415) 555-0123",
    "department_id": "65a000000000000000000001",
    "designation": "Engineer",
    "joining_date": "2024-01-15",
    "status": "active"
  }
  ```

- **Success response (`201`):** Standard success envelope with
  `data.employee`.
- **Error response:** Standard error envelope; duplicate employee code/email
  returns HTTP `409`.
- **Validation:** Code is trimmed and uppercased; email is validated and stored
  lowercase; code and email are unique. Names and designation cannot be blank.
  Phone is optional and accepts 7–15 digits with an optional leading `+` and
  common separators; it is stored without separators. `department_id` must
  identify an existing active department. `joining_date` uses `YYYY-MM-DD`,
  is stored as a UTC BSON date, and cannot be after today. Status must be
  `active`, `inactive`, or `on_leave`. Unknown/unsafe fields are rejected.
- **Status codes:** `201`, `400`, `401`, `403`, `409`.

### Get current employee profile

- **Method:** `GET`
- **URL:** `/api/employees/me/`
- **Purpose:** Return the employee profile linked to the signed-in user.
- **Role:** Employee (`employees:read`); only the Employee role can use this
  route.
- **Request body:** None.
- **Success response (`200`):** Standard success envelope with
  `data.employee`.
- **Error response:** Standard error envelope. An Employee account without a
  linked/existing employee record receives `404`.
- **Validation:** Resolves the employee ObjectId from `users.employee_id`; the
  client cannot choose another employee ID.
- **Status codes:** `200`, `401`, `403`, `404`.

### List designations

- **Method:** `GET`
- **URL:** `/api/employees/designations/`
- **Purpose:** Return distinct employee designations for dropdowns.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`employees:read`). Employee-role accounts cannot enumerate designations.
- **Request body:** None.
- **Success response (`200`):** Standard success envelope with
  `data.designations`, a sorted array of distinct non-empty strings.
- **Error response:** Standard error envelope.
- **Validation:** Requires a bearer token and directory-read permission.
- **Status codes:** `200`, `401`, `403`.

### Get employee

- **Method:** `GET`
- **URL:** `/api/employees/{id}/`
- **Purpose:** Return one employee profile.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`employees:read`); an Employee can read only their own linked profile.
- **Request body:** None.
- **Success response (`200`):** Standard success envelope with
  `data.employee`.
- **Error response:** Standard error envelope. Invalid ObjectId is `400`;
  missing employee is `404`; an Employee requesting another profile gets `403`.
- **Validation:** `{id}` must be a valid MongoDB ObjectId. Employee-role
  requests are matched against the authenticated user's `employee_id`.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

### Update employee

- **Method:** `PATCH`
- **URL:** `/api/employees/{id}/`
- **Purpose:** Partially update an employee and audit the change.
- **Role:** HR or Super Admin (`employees:write`).
- **Request body:** Any non-empty subset of `first_name`, `last_name`, `email`,
  `phone`, `department_id`, `designation`, `joining_date`, and `status`.
  `employee_code` is immutable. Field rules match create.
- **Success response (`200`):** Standard success envelope with updated
  `data.employee`.
- **Error response:** Standard error envelope. Duplicate email returns `409`;
  a missing/inactive department or invalid fields return `400`.
- **Validation:** Unknown/unsafe fields and `employee_code` are rejected.
  Active employee status updates require an existing active department.
  Successful changes create an audit-log entry.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`.

### Deactivate employee

- **Method:** `DELETE`
- **URL:** `/api/employees/{id}/`
- **Purpose:** Deactivate the employee without deleting the MongoDB document.
- **Role:** HR or Super Admin (`employees:write`).
- **Request body:** None.
- **Success response (`200`):** Standard success envelope with
  `data.employee`; its status is `inactive`.
- **Error response:** Standard error envelope. Invalid ObjectId is `400`;
  missing employee is `404`.
- **Validation:** `{id}` must be a valid ObjectId. The operation retains the
  record, sets its status to `inactive`, and writes an audit-log entry when the
  status changes.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

## Departments

### List departments

- **Method:** `GET`
- **URL:** `/api/departments/`
- **Purpose:** Return a paginated, searchable list of departments.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`departments:read`).
- **Request body:** None. Query parameters: `page`, `page_size`, `search`,
  `is_active`, `sort_by` (`code`, `name`, `created_at`, `updated_at`,
  `is_active`), and `sort_order` (`asc`, `desc`). Default ordering is newest
  first.
- **Success response (`200`):**

  ```json
  {
    "success": true,
    "data": {
      "departments": [
        {
          "id": "65a000000000000000000001",
          "code": "OPS",
          "name": "Operations",
          "description": null,
          "manager_employee_id": null,
          "is_active": true,
          "created_at": "2026-10-30T05:00:00+00:00",
          "updated_at": "2026-10-30T05:00:00+00:00"
        }
      ]
    },
    "meta": {"page": 1, "page_size": 20, "total": 1, "total_pages": 1}
  }
  ```

- **Error response:** Standard error envelope, for example
  `{"success": false, "error": {"code": "validation_error", "message": "Request validation failed.", "details": {}}}`.
- **Validation:** Rejects unknown or unsafe query keys, blank search, invalid
  boolean values, unsupported sort fields/orders, invalid pages, and page sizes
  above 100. Search text is regex-escaped before querying MongoDB.
- **Status codes:** `200`, `400`, `401`, `403`.

### Create department

- **Method:** `POST`
- **URL:** `/api/departments/`
- **Purpose:** Create a department.
- **Role:** HR or Super Admin (`departments:write`).
- **Request body:**

  ```json
  {
    "code": "OPS",
    "name": "Operations",
    "description": "Operations team",
    "manager_employee_id": null,
    "is_active": true
  }
  ```

  `description`, `manager_employee_id`, and `is_active` are optional; defaults
  are `null`, `null`, and `true`.
- **Success response (`201`):** Standard success envelope with
  `data.department` containing `id`, `code`, `name`, `description`,
  `manager_employee_id`, `is_active`, `created_at`, and `updated_at`.
- **Error response:** Standard error envelope; duplicate code/name uses HTTP
  `409` and code `conflict`.
- **Validation:** Code is trimmed and uppercased (1–40 characters); name is
  trimmed (1–120 characters) and unique without regard to case. Description is
  at most 2,000 characters. Manager must be `null` or a valid ObjectId for an
  existing employee whose status is `active`. Unknown/unsafe keys are rejected.
- **Status codes:** `201`, `400`, `401`, `403`, `409`.

### Get department

- **Method:** `GET`
- **URL:** `/api/departments/{id}/`
- **Purpose:** Return one department by ObjectId.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`departments:read`).
- **Request body:** None.
- **Success response (`200`):** Standard success envelope with
  `data.department` and the department fields described above.
- **Error response:** Standard error envelope. Invalid ObjectId is `400`;
  missing department is `404`.
- **Validation:** `{id}` must be a valid MongoDB ObjectId.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

### Update or deactivate department

- **Method:** `PATCH`
- **URL:** `/api/departments/{id}/`
- **Purpose:** Partially update department fields or deactivate it. There is no
  hard-delete endpoint.
- **Role:** HR or Super Admin (`departments:write`).
- **Request body:** Any non-empty subset of `code`, `name`, `description`,
  `manager_employee_id`, and `is_active`. Example:

  ```json
  {"description": "Updated description"}
  ```

- **Success response (`200`):** Standard success envelope with the updated
  `data.department`.
- **Error response:** Standard error envelope. Duplicate code/name returns
  `409`; deactivation with active employees returns `409` with
  `details.active_employee_count`.
- **Validation:** Same field rules as create. `manager_employee_id: null`
  clears the manager. Deactivation is blocked while any employee with
  `status: "active"` references the department. No hard delete is supported.
- **Status codes:** `200`, `400`, `401`, `403`, `404`, `409`.

### List department employees

- **Method:** `GET`
- **URL:** `/api/departments/{id}/employees/`
- **Purpose:** Return employees assigned to a department, including inactive
  employees, with pagination and optional search.
- **Role:** Super Admin, HR, Inventory Manager, Purchase Manager, Sales Manager
  (`departments:read`).
- **Request body:** None. Query parameters: `page`, `page_size`, `search`,
  `sort_by` (`employee_code`, `first_name`, `last_name`, `email`, `designation`,
  `joining_date`, `status`, `created_at`), and `sort_order` (`asc`, `desc`).
- **Success response (`200`):** Standard success envelope with
  `data.employees` and pagination metadata. Employee results contain only
  public directory fields (for example employee code, name, email, department,
  designation, status, and timestamps).
- **Error response:** Standard error envelope. Invalid ObjectId is `400`;
  missing department is `404`.
- **Validation:** `{id}` must be a valid ObjectId. Search is literal and
  case-insensitive; pagination and sort values are validated and bounded.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

## Products

All product routes require a bearer access token. Product reads require
`products:read`; create and update require `products:write` (Inventory Manager
or Super Admin). Lists use `page` (default `1`) and `page_size` (default `20`,
maximum `100`) and return standard pagination metadata.

### List products

- **Method:** `GET`
- **URL:** `/api/products/`
- **Purpose:** Return a paginated product list with search and filters.
- **Role:** Roles with `products:read` in the permission matrix.
- **Request body:** None. Query parameters: `page`, `page_size`, `search`
  (case-insensitive substring in name or SKU), `category`, `is_active`,
  `low_stock`, `sort_by` (`sku`, `name`, `category`, `unit`, `cost_price`,
  `selling_price`, `quantity_on_hand`, `reserved_quantity`, `min_stock_level`,
  `is_active`, `created_at`, `updated_at`), and `sort_order` (`asc`, `desc`).
- **Success response (`200`):** Standard envelope containing
  `data.products` and `meta` with `page`, `page_size`, `total`, and
  `total_pages`. Prices are JSON decimal strings.
- **Validation:** Unknown/unsafe query keys, invalid booleans, unsupported
  sorting, blank search/category filters, and invalid pagination are rejected.
  Search text is escaped before it is used in MongoDB.
- **Status codes:** `200`, `400`, `401`, `403`.

### Create product

- **Method:** `POST`
- **URL:** `/api/products/`
- **Purpose:** Create a product catalogue entry with zero initial stock.
- **Role:** Inventory Manager or Super Admin (`products:write`).
- **Request body:**

  ```json
  {
    "sku": "PART-001",
    "name": "Widget",
    "description": "Replacement component",
    "category": "Hardware",
    "unit": "each",
    "cost_price": "12.50",
    "selling_price": "19.99",
    "min_stock_level": 5,
    "is_active": true
  }
  ```

- **Success response (`201`):** Standard envelope containing
  `data.product`; `quantity_on_hand` and `reserved_quantity` are both `0`.
- **Error response:** Standard error envelope; duplicate SKU is `409`.
- **Validation:** SKU is trimmed, uppercased, and unique. Name, category, and
  unit cannot be blank. Prices must be positive decimals with at most two
  decimal places and are stored as BSON Decimal128. Unknown/unsafe fields are
  rejected. Client-supplied stock quantities are never accepted.
- **Status codes:** `201`, `400`, `401`, `403`, `409`.

### Get or update a product

- **Method:** `GET` or `PATCH`
- **URL:** `/api/products/{id}/`
- **Purpose:** Read or partially update product details.
- **Role:** Read requires `products:read`; update requires `products:write`.
- **Request body:** PATCH accepts a non-empty subset of `name`, `description`,
  `category`, `unit`, `cost_price`, `selling_price`, `min_stock_level`, and
  `is_active`.
- **Success response (`200`):** Standard envelope containing `data.product`.
- **Error response:** Invalid ObjectId is `400`; missing product is `404`;
  product quantities and SKU updates return `400` with a clear explanation.
- **Validation:** SKU is immutable. Attempts to set `quantity_on_hand` or
  `reserved_quantity` are rejected; stock changes belong to stock services
  that also write stock movements. Prices must remain positive.
- **Status codes:** `200`, `400`, `401`, `403`, `404`.

### List low-stock products

- **Method:** `GET`
- **URL:** `/api/products/low-stock/`
- **Purpose:** Return a paginated list of products at or below their minimum
  available stock.
- **Role:** Roles with `products:read` in the permission matrix.
- **Request body:** None. Supports `page`, `page_size`, `search`, `category`,
  `is_active`, `sort_by`, and `sort_order`, with the same rules as product
  listing.
- **Success response (`200`):** Standard envelope containing `data.products`
  and pagination metadata.
- **Validation:** A product is low-stock when
  `quantity_on_hand - reserved_quantity <= min_stock_level`.
- **Status codes:** `200`, `400`, `401`, `403`.

### List product categories

- **Method:** `GET`
- **URL:** `/api/products/categories/`
- **Purpose:** Return sorted, distinct non-empty product categories.
- **Role:** Roles with `products:read` in the permission matrix.
- **Request body:** None.
- **Success response (`200`):** Standard envelope containing
  `data.categories`, an array of category strings.
- **Status codes:** `200`, `400`, `401`, `403`.

**Order integration:** New-order services must reject inactive product
references. The product service exposes a tested active-product guard, but
sales and purchase order endpoints are not implemented yet in this checkout.

## Stock

Stock quantities change only through the inventory stock service, which
conditionally updates the product and appends its movement in one MongoDB
transaction. The transaction uses snapshot read concern and majority write
concern. A conditional update makes concurrent stock reductions safe: when one
request uses stock first, the other request's availability condition no longer
matches and it is rejected instead of overselling.

### Adjust stock

- **Method:** `POST`
- **URL:** `/api/stock-adjustments/`
- **Purpose:** Increase or decrease on-hand stock and record an immutable
  movement.
- **Role:** Inventory Manager or Super Admin (`stock:adjust`).
- **Headers:** `Authorization: Bearer <access-token>` and
  `Idempotency-Key: <UUID>` (required).
- **Request body:**

  ```json
  {
    "product_id": "65a000000000000000000001",
    "quantity_change": -2,
    "reason": "Damaged during inspection"
  }
  ```

- **Success response (`201`):** Standard envelope containing
  `data.stock_movement` with movement ID, product, movement type, quantity and
  reservation deltas, before/after on-hand quantity, reason, reference, actor,
  and creation time.
- **Error response:** Standard error envelope. Insufficient available stock
  returns `409`; reusing a key with a different validated request body returns
  `422`.
- **Validation:** Product ID must be a valid ObjectId; `quantity_change` must be
  a non-zero integer; reason must contain at least three characters. The UUID
  key is scoped to the authenticated user and endpoint. Repeating the same key
  and body returns the original response without applying another adjustment.
  A reduction is allowed only when
  `quantity_on_hand - reserved_quantity >= abs(quantity_change)`.
- **Status codes:** `201`, `400`, `401`, `403`, `409`, `422`.

### List stock movements

- **Method:** `GET`
- **URL:** `/api/stock-movements/`
- **Purpose:** Read append-only inventory movement history, newest first.
- **Role:** Roles with `stock:read` in the permission matrix.
- **Request body:** None. Query parameters: `product` (ObjectId), `type`
  (`purchase_receipt`, `sale_fulfilment`, `sale_return`, `adjustment`,
  `reservation`, `reservation_release`), `start_date` and `end_date`
  (timezone-aware ISO-8601 datetimes), `user` (actor ObjectId), `page`, and
  `page_size` (maximum `100`).
- **Success response (`200`):** Standard envelope containing
  `data.stock_movements` and pagination metadata.
- **Validation:** IDs, movement type, dates, range order, and pagination are
  validated. Movement records cannot be updated or deleted through the API.
- **Status codes:** `200`, `400`, `401`, `403`.

## Accounts and audit logs

### List users

- **Method:** `GET`
- **URL:** `/api/users/`
- **Purpose:** Return a paginated user list.
- **Role:** Super Admin (`users:manage`).
- **Query parameters:** `page`, `page_size` (maximum 100), `search` (name/email),
  `role`, and `is_active` (`true` or `false`).
- **Success response (`200`):** Standard envelope with `data.users` and
  pagination metadata. Password hashes and reset-token data are never returned.
- **Status codes:** `200`, `400`, `401`, `403`.

### Create, edit, activate, deactivate, and reset a user

- **Role:** Super Admin (`users:manage`) for all routes.
- **Create:** `POST /api/users/` with `email`, `password`, `full_name`, `role`,
  and optional `employee_id`; returns `data.user` with status `201`.
- **Edit:** `PATCH /api/users/{id}/` with one or more of `email`, `full_name`,
  `role`, or `employee_id`; returns `data.user`.
- **Activate/deactivate:** `POST /api/users/{id}/activate/` or
  `/api/users/{id}/deactivate/` with an empty JSON object. Deactivation revokes
  that account's sessions. The last active Super Admin and the current user
  cannot be deactivated.
- **Admin password reset:** `POST /api/users/{id}/reset-password/` with an
  empty JSON object. In development, the single-use reset link is printed to
  the backend console. Email delivery is not configured in this environment.
- **Validation:** Passwords require at least 10 characters, must not match the
  email, and must not be commonly used. Role and ObjectId fields are validated;
  unknown/unsafe fields are rejected.
- **Status codes:** `200`, `201`, `400`, `401`, `403`, `404`, `409`.

### Read audit logs

- **Method:** `GET`
- **URL:** `/api/audit-logs/`
- **Purpose:** Return a filtered, newest-first audit page.
- **Role:** Super Admin (`audit:read`).
- **Query parameters:** `page`, `page_size` (maximum 100), `user` (MongoDB
  ObjectId; matches actor or target), `action`, `start_date`, and `end_date`
  (ISO-8601 datetimes).
- **Success response (`200`):** Standard envelope with `data.audit_logs` and
  pagination metadata.
- **Status codes:** `200`, `400`, `401`, `403`.

### Change password

- **Method:** `POST`
- **URL:** `/api/auth/change-password/`
- **Purpose:** Change the authenticated user's password and revoke every
  refresh session.
- **Role:** Authenticated users with `own-password:change`.
- **Request body:** `old_password`, `new_password`, and `confirm_password`.
- **Validation:** New passwords require at least 10 characters, must not match
  the account email, and must not be commonly used.
- **Status codes:** `200`, `400`, `401`, `403`.

### Request or confirm a password reset

- **Request:** `POST /api/auth/password-reset/request/` with `{ "email": "..." }`.
  This route is public and returns the same generic response whether or not an
  account exists.
- **Confirm:** `POST /api/auth/password-reset/confirm/` with `email`, `token`,
  `password`, and `confirm_password`. The one-time token is read from the reset
  link's query string by the frontend.
- **Development limitation:** With `DEBUG=True`, reset links are printed to the
  backend console. Production email delivery is not configured.
- **Status codes:** Request `200` or `400`; confirmation `200`, `400`, or `401`.

## Postman

Import [`postman/departments.postman_collection.json`](./postman/departments.postman_collection.json),
[`postman/employees.postman_collection.json`](./postman/employees.postman_collection.json),
[`postman/products.postman_collection.json`](./postman/products.postman_collection.json),
and [`postman/stock.postman_collection.json`](./postman/stock.postman_collection.json).
Set collection variables `base_url` (for example `http://localhost:8000/api`)
and role-appropriate `access_token`; the employee collection also uses
`employee_access_token` for the self-profile request. The product collection
uses `product_id` and a generated SKU for its create/read/update requests.
The stock collection uses a `product_id` and includes an adjustment key.
Requests include successful flows and negative validation, permission,
duplicate, and deactivation examples.
