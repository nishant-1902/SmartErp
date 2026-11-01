# API Documentation

Base URL: `http://localhost:8000/api`

All department endpoints require a bearer access token and use the standard JSON
success/error envelopes. Department list endpoints use `page` (default `1`) and
`page_size` (default `20`, maximum `100`). Search is a literal, case-insensitive
substring search. Sort fields are explicitly allowlisted.

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

Inactive supplier check: purchase-order creation must call the reusable
`require_active_supplier` service before creating a new order. The purchase-order
creation/workflow endpoints are not implemented yet, so there is currently no
PO creation API on which to enforce this check.

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
