# MongoDB Database Design

SmartERP accesses MongoDB only through PyMongo repositories. This document
describes the initial collection contract in
[`backend/database/indexes.py`](../backend/database/indexes.py). Run the
idempotent Django command `python manage.py init_db` from `backend\` to create
missing collections and validators and ensure the declared indexes.

The schemas are a database-level safety net, not a replacement for request
serializers or business rules. Services must still validate permissions,
workflow state, relationships, money calculations, and conditional stock
updates. Persist UTC dates as BSON dates and money as BSON Decimal128.

## Conventions and search strategy

- Every collection has MongoDB's automatically created `_id: ObjectId`.
- Required fields are listed in each collection's `required` array. Optional
  fields may be absent; examples show `null` where the validator permits it.
- References are BSON `ObjectId` values. MongoDB does not enforce foreign keys;
  services validate referenced documents.
- User email is trimmed and lowercased before storage. SKU is uppercased.
  `name_search` is the lowercased, normalized name used only for search.
- The selected name-search strategy is an **escaped, anchored prefix regex**
  over a normal ascending index on `name_search`, for example
  `{"name_search": {"$regex": "^" + re.escape(query.lower())}}`. This supports
  fast case-sensitive prefix search when values are normalized and regex is
  anchored. It does not provide arbitrary substring or typo-tolerant search.
  Escaping prevents user text from becoming regex syntax. A MongoDB text index
  was not selected because it tokenizes words and does not provide the desired
  prefix behavior; Atlas Search is a separate option if richer search becomes
  a requirement. Keep queries restricted to serializer-validated fields.
- TTL indexes are asynchronous cleanup, not exact-time schedulers. Expiration
  timestamps must be set by the application. Do not use TTL for business
  history.
- Indexes cost storage and add write work. The initial indexes below correspond
  to the current API list, authentication, and workflow requirements; review
  `$indexStats` with real traffic before adding speculative indexes.

## Collection contracts

Examples use Mongo shell notation: `ObjectId("...")`, `ISODate("...")`, and
`Decimal128("...")` represent BSON types, not JSON strings. Optional example
fields are shown explicitly when the validator permits `null`.

### `users`

**Purpose:** Login identity, role, active status, and optional employee link.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000001"),
  email: "alex@example.com",
  password_hash: "argon2$...",
  full_name: "Alex Morgan",
  role: "super_admin",
  is_active: true,
  employee_id: null,
  token_version: 0,
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z"),
  last_login_at: null
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `email` | string | Yes | 3–254 chars, lowercase normalized login email |
| `password_hash` | string | Yes | Non-empty Django hasher output; never return it in API data |
| `full_name` | string | Yes | 1–200 chars |
| `role` | string | Yes | `super_admin`, `hr_manager`, `inventory_manager`, `purchase_manager`, `sales_manager`, or `employee` |
| `is_active` | boolean | Yes | Login enabled/disabled |
| `employee_id` | ObjectId or null | No | Optional employee profile link |
| `token_version` | integer | Yes | Non-negative; supports immediate access-token revocation |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |
| `last_login_at` | date or null | Yes | UTC date of last successful login; null before first login |

**Unique constraints:** `email`; `employee_id` is unique only when it is an
ObjectId, using a partial unique index. Normalize email before insert/update.

**Indexes:** unique `email`; partial unique `employee_id`; `(is_active,
created_at DESC)` for active-user lists; `(role, is_active)` for role
administration.

**Relationships / embed vs reference:** `employee_id` references `employees`.
Keep credentials separate from employee profile data because authentication
and HR records have different access controls and lifecycles.

**Sample query:** `db.users.find({email: "alex@example.com", is_active: true})`.

### `employees`

**Purpose:** HR profile, department/status lists, and normalized name search.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000002"),
  employee_code: "EMP-0001",
  first_name: "Alex",
  last_name: "Morgan",
  name_search: "alex morgan",
  email: "alex@example.com",
  phone: "+15551234567",
  department_id: ObjectId("650000000000000000000003"),
  designation: "HR Manager",
  joining_date: ISODate("2025-03-01T00:00:00Z"),
  status: "active",
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z"),
  deactivated_at: null
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `employee_code` | string | Yes | Immutable, non-empty business identifier |
| `first_name`, `last_name` | string | Yes | 1–100 chars each |
| `name_search` | string | Yes | Lowercase normalized combined name |
| `email` | string | Yes | Lowercase normalized email |
| `phone` | string or null | No | Validated phone text |
| `department_id` | ObjectId | Yes | Existing department |
| `designation` | string | Yes | 1–100 chars |
| `joining_date` | date | Yes | UTC BSON date |
| `status` | string | Yes | `active`, `inactive`, or `on_leave` |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |
| `deactivated_at` | date or null | No | Optional UTC deactivation date |

**Unique constraints:** `employee_code` and normalized `email`.

**Indexes:** unique code and email; `(department_id, status)` for department
lists; `(status, name_search)` for status-filtered name prefixes.

**Relationships / embed vs reference:** `department_id` references
`departments`; a user may reference this employee. Employees are independently
searched and updated, so they are not embedded into departments.

**Sample query:** `db.employees.find({department_id: deptId, status: "active"})`.

### `departments`

**Purpose:** Organization units and active-employee department filtering.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000003"),
  code: "HR",
  name: "Human Resources",
  name_search: "human resources",
  description: "People operations",
  manager_employee_id: ObjectId("650000000000000000000002"),
  is_active: true,
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `code` | string | Yes | Non-empty, unique department code |
| `name` | string | Yes | 1–120 chars |
| `name_search` | string | Yes | Lowercase normalized department name |
| `description` | string or null | No | Optional explanation |
| `manager_employee_id` | ObjectId or null | No | Existing active employee, checked by service |
| `is_active` | boolean | Yes | Whether department accepts active assignments |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |

**Unique constraints:** `code` and normalized `name_search`.

**Indexes:** unique code/name; `(is_active, name_search)` for active and prefix
queries. Employee list queries use the employee-side department index.

**Relationships / embed vs reference:** manager and employee links reference
separate employee records. Departments are independently managed and may have
many employees, so employees are not embedded.

**Sample query:** `db.departments.find({is_active: true, name_search: /^human/})`.

### `products`

**Purpose:** Product catalogue and current stock summary.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000004"),
  sku: "CHAIR-001",
  name: "Office Chair",
  name_search: "office chair",
  description: "Adjustable office chair",
  category: "Furniture",
  unit: "each",
  cost_price: Decimal128("75.00"),
  selling_price: Decimal128("120.00"),
  quantity_on_hand: NumberLong(20),
  reserved_quantity: NumberLong(2),
  min_stock_level: NumberLong(5),
  is_active: true,
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `sku` | string | Yes | Non-empty, uppercase unique stock identifier |
| `name`, `name_search` | string | Yes | Display name and lowercase search form |
| `description` | string or null | No | Optional description |
| `category`, `unit` | string | Yes | Non-empty category and unit |
| `cost_price`, `selling_price` | Decimal128 | Yes | Non-negative money; never float |
| `quantity_on_hand`, `reserved_quantity` | integer | Yes | Non-negative; only stock service may change |
| `min_stock_level` | integer | Yes | Non-negative low-stock threshold |
| `is_active` | boolean | Yes | Whether product can be used in new transactions |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |

**Unique constraints:** `sku`.

**Indexes:** unique SKU; `(category, is_active)` for catalogue filters;
`(is_active, name_search)` for active product prefix search.

**Relationships / embed vs reference:** Orders and movements reference the
product, while their line items embed SKU/name/price snapshots. Stock totals
are kept here for atomic conditional updates; the append-only movement
collection remains the audit history.

**Sample queries:**

```javascript
db.products.find({is_active: true, category: "Furniture"});
db.products.find({$expr: {$lte: [{$subtract: ["$quantity_on_hand", "$reserved_quantity"]}, "$min_stock_level"]}});
```

### `stock_movements`

**Purpose:** Append-only evidence for every stock quantity change.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000005"),
  product_id: ObjectId("650000000000000000000004"),
  movement_type: "purchase_receipt",
  quantity_change: NumberLong(5),
  reserved_change: NumberLong(0),
  quantity_before: NumberLong(20),
  quantity_after: NumberLong(25),
  reason: "Receipt PO-2026-000001",
  reference_type: "purchase_receipt",
  reference_id: ObjectId("650000000000000000000008"),
  performed_by: ObjectId("650000000000000000000001"),
  created_at: ISODate("2026-01-02T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `product_id` | ObjectId | Yes | Product affected |
| `movement_type` | string | Yes | `purchase_receipt`, `sale_fulfilment`, `sale_return`, `adjustment`, `reservation`, or `reservation_release` |
| `quantity_change`, `reserved_change` | integer | Yes | Deltas to on-hand and reserved quantities |
| `quantity_before`, `quantity_after` | integer | Yes | On-hand values before and after the atomic change |
| `reason` | string | Yes | Non-empty explanation |
| `reference_type`, `reference_id` | string, ObjectId | Yes | Originating business document |
| `performed_by` | ObjectId | Yes | Actor who initiated the operation |
| `created_at` | date | Yes | UTC BSON date |

**Unique constraints:** none; movements are immutable events.

**Indexes:** `(product_id, created_at DESC)` for item history; `(reference_type,
reference_id)` to find movements for a receipt/order; `(created_at DESC)` for
recent movement reports.

**Relationships / embed vs reference:** References products and the originating
receipt/order instead of embedding an unbounded movement list into products.

**Sample query:** `db.stock_movements.find({product_id: productId}).sort({created_at: -1})`.

### `suppliers`

**Purpose:** Supplier master data used by purchasing.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000006"),
  code: "SUP-001",
  name: "Northwind Supply",
  name_search: "northwind supply",
  email: "orders@northwind.example",
  phone: "+15551230000",
  contact_person: "Jamie Lee",
  address: {line1: "1 Market Street", city: "Seattle", postal_code: "98101", country: "US"},
  payment_terms: "Net 30",
  status: "active",
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `code` | string | Yes | Non-empty unique supplier code |
| `name`, `name_search` | string | Yes | Display name and lowercase search form |
| `email`, `phone`, `contact_person` | string or null | No | Optional contact details |
| `address` | object or null | No | Bounded postal address snapshot |
| `payment_terms` | string or null | No | Commercial terms |
| `status` | string | Yes | `active` or `inactive` |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |

**Unique constraints:** `code`.

**Indexes:** unique code; `(status, name_search)` for active supplier prefixes.

**Relationships / embed vs reference:** Purchase orders reference supplier ID
and embed a supplier snapshot so historical documents stay readable if contact
details change. The supplier itself remains independently editable.

**Sample query:** `db.suppliers.find({status: "active", name_search: /^north/})`.

### `purchase_orders`

**Purpose:** Purchase workflow, supplier snapshot, ordered line snapshots, and totals.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000007"),
  po_number: "PO-2026-000001",
  supplier_id: ObjectId("650000000000000000000006"),
  supplier_snapshot: {code: "SUP-001", name: "Northwind Supply"},
  items: [{
    product_id: ObjectId("650000000000000000000004"),
    sku: "CHAIR-001",
    name: "Office Chair",
    quantity_ordered: NumberLong(5),
    quantity_received: NumberLong(0),
    unit_cost: Decimal128("75.00"),
    line_total: Decimal128("375.00")
  }],
  status: "pending_approval",
  tax_rate: Decimal128("10.00"),
  subtotal: Decimal128("375.00"),
  tax_total: Decimal128("37.50"),
  grand_total: Decimal128("412.50"),
  created_by: ObjectId("650000000000000000000001"),
  approved_by: null,
  status_history: [{
    status: "pending_approval",
    by: ObjectId("650000000000000000000001"),
    at: ISODate("2026-01-02T00:00:00Z"),
    note: null
  }],
  created_at: ISODate("2026-01-02T00:00:00Z"),
  updated_at: ISODate("2026-01-02T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `po_number` | string | Yes | Unique human-readable number |
| `supplier_id`, `created_by` | ObjectId | Yes | Supplier and creating user |
| `supplier_snapshot` | object | Yes | Embedded historical supplier identity |
| `items` | array | Yes | At least one item with product ID, SKU/name snapshot, positive `quantity_ordered`, non-negative `quantity_received`, Decimal128 unit cost and line total |
| `status` | string | Yes | `draft`, `pending_approval`, `approved`, `rejected`, `partially_received`, `received`, or `cancelled` |
| `tax_rate` | Decimal128 | Yes | Per-order percentage from 0 to 100 |
| `subtotal`, `tax_total`, `grand_total` | Decimal128 | Yes | Server-calculated, non-negative money |
| `approved_by` | ObjectId or null | No | Approver when approved |
| `status_history` | array | Yes | Status, actor, UTC time, optional note for each transition |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |

**Unique constraints:** `po_number`.

**Indexes:** unique PO number; `(status, created_at DESC)`; `(supplier_id,
created_at DESC)`.

**Relationships / embed vs reference:** References supplier and products;
embeds bounded line and supplier snapshots for purchase detail reads and
historical pricing. Receipts stay separate because one PO can have many.

Duplicate product IDs in one PO are rejected with a validation error. The API
accepts a per-order tax percentage; it calculates line totals, subtotal, tax,
and grand total on the server using `Decimal`, rounds monetary amounts to two
places with `ROUND_HALF_UP`, and stores amounts and the tax rate as Decimal128.

**Sample queries:** `db.purchase_orders.find({status: "pending_approval"}).sort({created_at: -1})`; `db.purchase_orders.find({supplier_id: supplierId}).sort({created_at: -1})`.

### `purchase_receipts`

**Purpose:** Partial or complete quantities received against a purchase order.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000008"),
  receipt_reference: "RCPT-2026-000001",
  purchase_order_id: ObjectId("650000000000000000000007"),
  supplier_id: ObjectId("650000000000000000000006"),
  items: [{
    product_id: ObjectId("650000000000000000000004"),
    quantity_received: NumberLong(5)
  }],
  received_by: ObjectId("650000000000000000000001"),
  created_at: ISODate("2026-01-03T00:00:00Z"),
  idempotency_key: "e4fb7e89-5e1e-49bd-a13c-b98a6e028415",
  notes: "Checked against delivery note."
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `receipt_reference` | string | Yes | Unique `RCPT-YYYY-000001` reference |
| `purchase_order_id`, `supplier_id` | ObjectId | Yes | Related order and supplier |
| `items` | array | Yes | At least one product ID and positive `quantity_received` pair |
| `received_by` | ObjectId | Yes | Receiving actor |
| `created_at` | date | Yes | UTC BSON date |
| `idempotency_key` | string | Yes | Required UUID operation key; canonical request record is in `idempotency_keys` |
| `notes` | string or null | Yes | Optional receipt notes |

**Unique constraints:** `receipt_reference`; `(purchase_order_id,
idempotency_key)` for receipt records that contain a string idempotency key.

**Indexes:** unique receipt reference; `(purchase_order_id, created_at DESC)`;
`(supplier_id, created_at DESC)`; partial unique `(purchase_order_id,
idempotency_key)`.

**Relationships / embed vs reference:** References the PO, supplier, and
products. A receipt is separate because a PO can be received in multiple
transactions; bounded received lines are embedded in each receipt.
Receipt insertion, stock movements, PO received quantities/status, audit
record, and the idempotency response are committed in one MongoDB transaction.
Conditional PO-line updates enforce the remaining ordered quantity even when
receipts race.

**Sample query:** `db.purchase_receipts.find({purchase_order_id: poId}).sort({created_at: -1})`.

### `customers`

**Purpose:** Customer master data, addresses, tax ID, and credit settings.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000009"),
  code: "CUS-001",
  name: "Acme Stores",
  name_search: "acme stores",
  email: "ap@acme.example",
  phone: "+15551231111",
  tax_id: "TAX-12345",
  billing_address: {line1: "10 Main Street", city: "Austin", postal_code: "78701", country: "US"},
  shipping_address: {line1: "20 Warehouse Road", city: "Austin", postal_code: "78702", country: "US"},
  credit_limit: Decimal128("5000.00"),
  status: "active",
  created_at: ISODate("2026-01-01T00:00:00Z"),
  updated_at: ISODate("2026-01-01T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `code` | string | Yes | Unique customer code |
| `name`, `name_search` | string | Yes | Display name and lowercase search form |
| `email`, `phone` | string or null | No | Optional contact details |
| `tax_id` | string or null | No | Unique when present; empty string is invalid |
| `billing_address`, `shipping_address` | object or null | No | Address snapshots |
| `credit_limit` | Decimal128 or null | No | Non-negative monetary limit |
| `status` | string | Yes | `active` or `inactive` |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |

**Unique constraints:** `code`; optional `tax_id` is unique only when it is a
string, using `partialFilterExpression` (not a sparse index).

**Indexes:** unique code; partial unique tax ID; `(status, name_search)` for
active customer prefix search.

**Relationships / embed vs reference:** Sales orders reference the customer
and embed a customer/address snapshot. Orders and invoices retain the historical
customer data even after the master record changes.

**Sample query:** `db.customers.find({status: "active", name_search: /^acme/})`.

### `sales_orders`

**Purpose:** Sales order state, customer snapshot, pricing, discounts, and taxes.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000010"),
  order_number: "SO-2026-000001",
  customer_id: ObjectId("650000000000000000000009"),
  customer_snapshot: {code: "CUS-001", name: "Acme Stores", billing_address: {city: "Austin"}},
  items: [{
    product_id: ObjectId("650000000000000000000004"),
    sku: "CHAIR-001",
    name: "Office Chair",
    quantity: NumberLong(2),
    unit_price: Decimal128("120.00"),
    discount_percent: Decimal128("10.00"),
    tax_percent: Decimal128("10.00"),
    line_subtotal: Decimal128("240.00"),
    line_tax: Decimal128("21.60"),
    line_total: Decimal128("237.60"),
    returned_quantity: NumberLong(0)
  }],
  status: "confirmed",
  return_status: "none",
  payment_status: "unpaid",
  paid_total: Decimal128("0.00"),
  subtotal: Decimal128("240.00"),
  discount_total: Decimal128("24.00"),
  tax_total: Decimal128("21.60"),
  grand_total: Decimal128("237.60"),
  created_by: ObjectId("650000000000000000000001"),
  status_history: [{
    status: "confirmed",
    by: ObjectId("650000000000000000000001"),
    at: ISODate("2026-01-04T00:00:00Z"),
    note: null
  }],
  created_at: ISODate("2026-01-04T00:00:00Z"),
  updated_at: ISODate("2026-01-04T00:00:00Z"),
  fulfilled_at: null
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `order_number` | string | Yes | Unique human-readable order number |
| `customer_id` | ObjectId | Yes | Existing active customer for new orders |
| `customer_snapshot` | object | Yes | Historical customer identity/address |
| `items` | array | Yes | Product ID and SKU/name snapshots, positive quantity, server-derived Decimal128 unit price, discount/tax percentages, Decimal128 line subtotal/tax/total, and returned quantity |
| `status` | string | Yes | `draft`, `confirmed`, `fulfilled`, or `cancelled` |
| `return_status` | string | Yes | `none`, `partial`, or `full`; separate from order status |
| `payment_status` | string | Yes | Server-computed `unpaid`, `partial`, or `paid` |
| `paid_total` | Decimal128 | Yes for new orders | Server-maintained payment sum used to enforce the outstanding balance |
| `subtotal`, `discount_total`, `tax_total`, `grand_total` | Decimal128 | Yes | Server-calculated non-negative totals; tax applies after discount |
| `created_by` | ObjectId | Yes | Creator |
| `status_history` | array | Yes | Status, actor, UTC time, optional note for each transition |
| `created_at`, `updated_at` | date | Yes | UTC BSON dates |
| `fulfilled_at` | date or null | No | Fulfilment timestamp |

**Unique constraints:** `order_number`.

**Indexes:** unique number; `(customer_id, created_at DESC)`; `(status,
created_at DESC)`.

**Calculation:** For each line, multiply quantity by the server-read product
selling price for `line_subtotal`; apply the discount and round the discounted
line amount to two places using `ROUND_HALF_UP`; apply tax to that discounted
amount and round tax to two places; add discounted amount and tax for
`line_total`. The order totals are sums of the per-line rounded amounts. Never
use a client-supplied price or total.

**Stock timing:** Confirm conditionally reserves quantity by incrementing
`reserved_quantity` only when `is_active` is true and
`quantity_on_hand - reserved_quantity >= quantity`; it does not change
`quantity_on_hand`. Fulfilment deducts by reducing both on-hand and reserved
quantities. Cancelling a confirmed order reduces only the reservation. Each
operation and its stock movement are transactionally committed.

**Payments and returns:** Fulfillment initializes any legacy line return
counters and sets `fulfilled_at`. Payment writes compare-and-set `paid_total`
inside a transaction, and derive `payment_status` from the exact Decimal128
balance. Return writes conditionally increment each item's
`returned_quantity`; the order status remains `fulfilled`, while
`return_status` becomes `partial` or `full`.

**Relationships / embed vs reference:** References customer and product master
records, embeds bounded line and customer snapshots for order detail and
invoice workflows. Unbounded payments and stock movements stay separate.

**Sample queries:** `db.sales_orders.find({customer_id: customerId}).sort({created_at: -1})`; `db.sales_orders.find({status: "confirmed"}).sort({created_at: -1})`.

### `payments`

**Purpose:** Payment events associated with a customer sales order.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000011"),
  sales_order_id: ObjectId("650000000000000000000010"),
  customer_id: ObjectId("650000000000000000000009"),
  payment_reference: "BANK-REF-1001",
  amount: Decimal128("100.00"),
  method: "bank_transfer",
  status: "completed",
  received_at: ISODate("2026-01-05T00:00:00Z"),
  created_by: ObjectId("650000000000000000000001"),
  created_at: ISODate("2026-01-05T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `sales_order_id`, `customer_id` | ObjectId | Yes | Related order and customer |
| `payment_reference` | string or null | No | Unique external reference when present |
| `amount` | Decimal128 | Yes | Greater than zero |
| `method` | string | Yes | `cash`, `bank_transfer`, `card`, or `other` |
| `status` | string | Yes | `pending`, `completed`, `refunded`, or `failed` |
| `received_at` | date | Yes | UTC effective payment time |
| `created_by` | ObjectId | Yes | Recording actor |
| `created_at` | date | No | UTC audit timestamp |

**Unique constraints:** optional `payment_reference` is unique when present via
a partial index.

**Indexes:** partial unique reference; `(sales_order_id, created_at DESC)` for
order payment history; `(customer_id, status)` for customer payment status.

**Relationships / embed vs reference:** Payments reference order and customer.
They are separate append-only events because an order can have many payments,
refunds, and reconciliation queries.

**Sample query:** `db.payments.find({sales_order_id: orderId}).sort({created_at: -1})`.

### `invoices`

**Purpose:** Immutable invoice snapshot emitted for a fulfilled order.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000012"),
  invoice_number: "INV-2026-000001",
  sales_order_id: ObjectId("650000000000000000000010"),
  customer_id: ObjectId("650000000000000000000009"),
  customer_snapshot: {code: "CUS-001", name: "Acme Stores", billing_address: {city: "Austin"}},
  items: [{
    product_id: ObjectId("650000000000000000000004"),
    sku: "CHAIR-001",
    name: "Office Chair",
    quantity: NumberLong(2),
    unit_price: Decimal128("120.00"),
    discount_percent: Decimal128("10.00"),
    tax_percent: Decimal128("10.00"),
    line_subtotal: Decimal128("240.00"),
    line_tax: Decimal128("21.60"),
    line_total: Decimal128("237.60")
  }],
  subtotal: Decimal128("240.00"),
  discount_total: Decimal128("24.00"),
  tax_total: Decimal128("21.60"),
  grand_total: Decimal128("237.60"),
  issued_at: ISODate("2026-01-06T00:00:00Z"),
  due_date: ISODate("2026-02-05T00:00:00Z"),
  created_at: ISODate("2026-01-06T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `invoice_number` | string | Yes | Unique invoice identifier |
| `sales_order_id`, `customer_id` | ObjectId | Yes | Source order and customer |
| `customer_snapshot` | object | Yes | Immutable billing identity/address snapshot |
| `items` | array | Yes | Non-empty invoice line snapshots |
| `subtotal`, `discount_total`, `tax_total`, `grand_total` | Decimal128 | Yes | Non-negative totals copied from trusted server calculation |
| `issued_at`, `created_at`, `due_date` | date | Yes | UTC dates |

**Unique constraints:** `invoice_number`; `sales_order_id` is unique to enforce
at most one invoice per order in the current workflow.

**Indexes:** unique invoice number and order; `(customer_id, issued_at DESC)`.

**Relationships / embed vs reference:** References source order/customer and
embeds immutable invoice lines and customer data so a historical invoice is
rendered without joining mutable master records.

**Sample query:** `db.invoices.find({customer_id: customerId}).sort({issued_at: -1})`.

### `sales_returns`

**Purpose:** Append-only return records and credit-note snapshots, linked to a
fulfilled sales order.

Each return stores a unique `CN-YYYY-000001` credit-note number, customer and
order references/snapshots, returned product lines, exact Decimal128 subtotal,
discount, tax and total, the required reason, actor, and UTC creation time.
Per-order item `returned_quantity` counters prevent subsequent returns from
exceeding fulfilled quantity. The stock movement and return document are
created in the same transaction. Credit notes record a credit amount; they do
not automatically issue cash refunds.

**Indexes:** unique credit-note number; `(sales_order_id, created_at DESC)` and
`(customer_id, created_at DESC)`.

### `audit_logs`

**Purpose:** Append-only history for sensitive security and business changes.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000013"),
  actor_id: ObjectId("650000000000000000000001"),
  action: "purchase_order.approved",
  entity_type: "purchase_order",
  entity_id: ObjectId("650000000000000000000007"),
  before: {status: "pending_approval"},
  after: {status: "approved"},
  request_id: "req-6e0b",
  created_at: ISODate("2026-01-07T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `actor_id` | ObjectId or null | Yes | Authenticated actor; null for system activity |
| `action` | string | Yes | Non-empty action identifier |
| `entity_type` | string | Yes | Entity category |
| `entity_id` | ObjectId or string | Yes | Changed record identifier |
| `before`, `after` | object or null | No | Redacted change snapshots; never store secrets |
| `request_id` | string or null | No | Request correlation |
| `created_at` | date | Yes | UTC date |

**Unique constraints:** none; every event is distinct.

**Indexes:** `(entity_type, entity_id, created_at DESC)` for entity history;
`(actor_id, created_at DESC)` for user audit; `(action, created_at DESC)` for
action/date filters; and `(created_at DESC)` for date-range queries.

**Relationships / embed vs reference:** Entity ID is a polymorphic reference;
small, redacted before/after values are embedded to preserve history. Keep
snapshots bounded and never embed whole unbounded documents.

**Sample query:** `db.audit_logs.find({entity_type: "purchase_order", entity_id: poId}).sort({created_at: -1})`.

### `refresh_tokens`

**Purpose:** Hashed refresh sessions with rotation, family revocation, and reuse detection.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000014"),
  user_id: ObjectId("650000000000000000000001"),
  token_hash: "4d967...",
  family_id: "family-7f28",
  status: "active",
  created_at: ISODate("2026-01-01T00:00:00Z"),
  expires_at: ISODate("2026-01-08T00:00:00Z"),
  revoked_at: null,
  replaced_by: null,
  user_agent: "SmartERP browser",
  ip: "127.0.0.1"
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `user_id` | ObjectId | Yes | Token owner |
| `token_hash` | string | Yes | Hash only; never raw refresh token |
| `family_id` | string | Yes | Session family used for rotation/reuse detection |
| `status` | string | Yes | `active`, `rotated`, or `revoked` |
| `created_at`, `expires_at` | date | Yes | UTC dates; TTL is based on expiry |
| `revoked_at` | date or null | Yes | UTC rotation/revocation time; null while active |
| `replaced_by` | ObjectId or null | Yes | Rotated token record reference; null while active |
| `user_agent`, `ip` | string or null | Yes | Optional session context, stored as null when unavailable |

**Unique constraints:** `token_hash`.

**Indexes:** unique hash; `(user_id, status, expires_at)` for token-family
operations; TTL on `expires_at` with `expireAfterSeconds: 0`.

**Relationships / embed vs reference:** References user; separate records allow
many sessions per user, atomic rotation, and revocation without an unbounded
token array on the user.

The raw refresh token is returned only to the client; MongoDB stores its
SHA-256 hash. A rotated token retry within 10 seconds returns `REFRESH_RACE`
without revoking the session family. Reuse outside that window revokes every
record in the family.

**Sample query:** `db.refresh_tokens.find({user_id: userId, status: "active", expires_at: {$gt: new Date()}})`.

### `login_attempts`

**Purpose:** Temporary rate-limit counters per normalized email and client IP.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000015"),
  email: "alex@example.com",
  client_ip: "127.0.0.1",
  failed_count: NumberLong(3),
  window_started_at: ISODate("2026-01-01T00:00:00Z"),
  expires_at: ISODate("2026-01-01T00:15:00Z"),
  locked_until: null
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `email` | string | Yes | Normalized lowercase account key |
| `client_ip` | string | Yes | Validated client address |
| `failed_count` | integer | Yes | Non-negative failures in current window |
| `window_started_at`, `expires_at` | date | Yes | UTC rate-limit window and cleanup time |
| `locked_until` | date or null | No | UTC lock deadline if threshold reached |

**Unique constraints:** `(email, client_ip)` for one active counter per pair.

**Indexes:** unique email/IP pair; TTL on `expires_at`.

**Relationships / embed vs reference:** No user ID is required, avoiding
account-existence disclosure. A compact counter record is simpler than
embedding attacker-controlled IP arrays on user documents.

**Sample query:** `db.login_attempts.findOne({email: "alex@example.com", client_ip: "127.0.0.1"})`.

### `idempotency_keys`

**Purpose:** Store operation identity, request hash, and result linkage for safe retries.

**Full example**

```javascript
{
  _id: ObjectId("650000000000000000000016"),
  key: "54e2b9a2-c6fe-4fd8-86f4-4c26fe44cae7",
  scope: "650000000000000000000001:/api/stock-adjustments/",
  request_hash: "3c42...",
  status: "completed",
  result_id: ObjectId("650000000000000000000016"),
  response: {stock_movement: {id: "650000000000000000000005"}},
  created_at: ISODate("2026-01-01T00:00:00Z"),
  expires_at: ISODate("2026-01-02T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `key` | string | Yes | Client-supplied retry key |
| `scope` | string | Yes | Authenticated user ID plus endpoint; key uniqueness is scoped |
| `request_hash` | string | Yes | Hash of canonical validated request body |
| `status` | string | Yes | `processing`, `completed`, or `failed` |
| `result_id` | ObjectId or null | No | Result document reference |
| `response` | object or null | No | Stored bounded response for same-key/same-body replay |
| `created_at`, `expires_at` | date | Yes | UTC creation and retention dates |

**Unique constraints:** compound `(key, scope)`.

**Indexes:** unique `(key, scope)`; TTL on `expires_at`. Both key fields are
queried together for operation replay, and the declared order matches the
existing application index. Stock adjustment
records are retained for 24 hours for request replay.

**Relationships / embed vs reference:** The bounded response is stored with its
request hash in the same transaction as the business operation. Same-key/same-
body requests replay that response; changing the body with the same key returns
HTTP 422.

**Sample query:** `db.idempotency_keys.findOne({key: suppliedKey, scope: operationScope})`.

### `counters`

**Purpose:** Atomic sequence values for human-readable identifiers such as
`PO-2026-000001`, `SO-2026-000001`, and `INV-2026-000001`.

**Full example**

```javascript
{
  _id: "purchase_order:2026",
  value: NumberLong(1),
  updated_at: ISODate("2026-01-02T00:00:00Z")
}
```

| Field | Type | Required | Validation / meaning |
|---|---|---:|---|
| `_id` | string | Yes | Counter key, typically entity and year |
| `value` | integer | Yes | Non-negative sequence number |
| `updated_at` | date | Yes | UTC counter update date |

**Unique constraints:** `_id`, using MongoDB's built-in unique `_id` index.
The declared explicit unique index documents this contract but is redundant
with MongoDB's mandatory `_id_` index; `init_db` ensures the declared name for
consistency. Applications may use the built-in index directly.

**Indexes:** `_id` unique; update and allocate with one atomic
`find_one_and_update({"_id": key}, {"$inc": {"value": 1}, "$set": ...},
upsert=True, return_document=AFTER)`. Do not read then increment separately.

**Relationships / embed vs reference:** Independent counters are separate from
orders to keep number allocation atomic and avoid coupling counter updates to
order document shape.

**Sample query:** `db.counters.findOne({_id: "purchase_order:2026"})`.

## Duplicate-key errors and safe index rollout

MongoDB unique indexes reject duplicate values with `DuplicateKeyError`.
Repositories/services should catch that specific exception at the operation
boundary and translate it to a stable HTTP 409 conflict response. Do not return
the raw MongoDB message or index name; log diagnostic details server-side
without exposing them to the client. Never treat a duplicate as success unless
an idempotency record proves it is the same operation and request body.

Before creating a unique index on an existing collection:

1. Back up the database and confirm the intended normalization/collation rules.
2. Find duplicates using the exact key shape. Example for normalized email:

   ```javascript
   db.users.aggregate([
     {$group: {_id: "$email", ids: {$push: "$_id"}, count: {$sum: 1}}},
     {$match: {count: {$gt: 1}}}
   ])
   ```

3. For a compound key, group on the same fields, for example
   `{key: "$key", scope: "$scope"}` for idempotency records. For optional
   unique values, include only records matching the intended partial filter:
   `{tax_id: {$type: "string"}}`.
4. Review and resolve each duplicate according to business ownership: merge
   only when safe, otherwise correct a value or archive/remove a redundant
   record with an auditable decision. Do not blindly delete duplicate users,
   orders, or financial history.
5. Rerun the aggregation until it returns no groups. Check missing and
   malformed values separately; a unique index does not enforce all schema
   semantics on legacy documents.
6. Run `python manage.py init_db` again. It reports collection/validator/index
   work and surfaces an index build failure instead of silently skipping it.
7. Verify with `db.collection.getIndexes()` and representative `explain()`
   queries. MongoDB TTL deletion is asynchronous.

`init_db` applies `validationLevel: "strict"` and `validationAction: "error"`
to both new and existing collections. Existing documents are not rewritten by
`collMod`, but subsequent writes to non-conforming existing documents may be
rejected. Inspect and repair legacy data before production rollout; the command
does not delete data, remove indexes, or automatically resolve duplicates.

## Data flow and local setup

```text
React frontend
    -> Django REST Framework serializer validates input
    -> service enforces permissions, business rules, and transactions
    -> repository uses PyMongo and MONGO_URI
    -> MongoDB validates documents and applies indexes
    -> backend serializes response and returns it to the frontend
```

Run the initializer only after local MongoDB is available and the `MONGO_URI`
in `backend/.env` points to the intended database:

```powershell
Set-Location backend
.\venv\Scripts\python.exe manage.py init_db
```

Do not run it against production without a backup and a reviewed duplicate
cleanup plan. It creates/updates schema metadata but does not insert seed data.
