# Maintenance and performance

## Index management

SmartERP accesses MongoDB through PyMongo repositories. Indexes are declared in
`backend/database/indexes.py` and created additively by `init_db`; the
initializer does not remove existing indexes. Index choices should be based on
the production query shapes and verified with `explain("executionStats")`, not
added speculatively. Indexes consume storage and increase write cost.

### Reproducing the demo benchmark

`backend/scripts/seed_demo.py` uses Faker to create synthetic records and
measure representative list, history, dashboard, and report queries. It refuses
to run outside `SMARTERP_ENV=development`, requires a local MongoDB replica-set
primary, and accepts only a database name matching `smarterp_perf_*`; it will
not seed the application database. The measured workload used the isolated
`smarterp_perf_demo` database, with 10,000 products, 10,000 sales orders,
10,000 purchase orders, and supporting records. Do not point the script at a
production or shared database.

From the repository root in PowerShell:

```powershell
$env:MONGO_DB_NAME = "smarterp_perf_demo"
.\backend\venv\Scripts\python.exe .\backend\manage.py init_db
.\backend\venv\Scripts\python.exe .\backend\scripts\seed_demo.py --database smarterp_perf_demo --records 10000
.\backend\venv\Scripts\python.exe .\backend\scripts\seed_demo.py --database smarterp_perf_demo --explain-only
```

The seed command initializes the demo database and inserts Faker-generated
documents. `--explain-only` can be rerun after code or index changes without
seeding again. The benchmark is a representative synthetic workload, not a
substitute for measuring realistic production data and traffic.

### Findings and before/after measurements

The baseline plans were captured before the query and index changes. The final
plans below were captured after seeding the same 10,000-record workload and
running `explain("executionStats")`. The benchmark uses a page size of 20.

| Query shape | Before | After |
|---|---|---|
| Default user, department, employee, customer, supplier, product, sales-order, purchase-order, payment, invoice, and stock-movement pages | Many default sort paths used `COLLSCAN` followed by an in-memory `SORT`; large collections were scanned to return one page. | All measured default pages used indexes, returned at most 20 rows, and had no blocking `SORT` stage. |
| Customer and supplier history pages | Existing parent-key indexes did not cover the complete deterministic page ordering. | History pages used compound parent-key/created-time/`_id` indexes; only the 10 requested rows were examined for 10-row history pages. |
| Low-stock product page/report | The derived low-stock predicate required examining about 9,000 active products to return a page. | `is_low_stock` plus the dedicated low-stock/created-time/`_id` index returned 20 rows; the measured page examined 20 documents. The report uses a separate active/low-stock/availability index. |
| Sales report page | About 2,500 documents examined for a 20-row page. | 20 documents examined for 20 returned rows, using the report page index. |
| Department report page with employee totals | About 1,020 documents examined. | 40 documents examined for the 20 departments and their joined employee counts; the join occurs after pagination. |
| Inventory summary | Examined product records while aggregating. | The covering inventory index examined about 9,000 index keys and fetched zero product documents. |
| Purchase summary | Aggregation examined purchase-order documents. | The covering purchase-statistics index examined 10,000 keys and fetched zero purchase-order documents. |
| Exact unfiltered counts | Could scan documents for exact totals. | Empty-filter totals use the `_id_` index; measured count plans fetched zero documents, though they still examine index keys to return an exact count. |

Across the measured endpoint list pages and reports, final explain plans had no
`COLLSCAN` or blocking `SORT` stage. Representative final output included:

```text
products low-stock page: nReturned=20, totalDocsExamined=20
sales report page: nReturned=20, totalDocsExamined=20
department report page: nReturned=20, totalDocsExamined=40
inventory summary: totalKeysExamined=9000, totalDocsExamined=0
purchase statistics: totalKeysExamined=10000, totalDocsExamined=0
```

The dashboard/report aggregations that summarize whole collections still
inspect matching index keys. For example, inventory summary examines about
9,000 keys, and purchase statistics examines 10,000 keys; the covering indexes
avoid fetching every document but do not make a whole-collection aggregate
constant-time. Exact counts similarly require examining matching index keys.
Monthly sales groups all orders in the requested date range, so its work grows
with that range.

The indexes added for the measured workload include deterministic page sort
indexes, report match/sort indexes, an inventory summary covering index, a
purchase summary covering index, and low-stock indexes for the stored derived
fields. The low-stock fields are `available_quantity` and `is_low_stock`.
Stock-changing services keep them in sync with quantity movements, and product
updates recalculate them when relevant stock thresholds change.

The benchmark led to these new index definitions:

- Users: `ix_users_created_page`.
- Employees: `ix_employees_created_page`, `ix_employees_joining_page`,
  `ix_employees_department_created_page`, and `ix_employees_designation`.
- Departments: `ix_departments_created_page`.
- Products: `ix_products_created_page`, `ix_products_low_stock_created`,
  `ix_products_active_low_stock_available`, and
  `ix_products_inventory_summary`.
- Stock movements: `ix_stock_created_page` and
  `ix_stock_product_created_page`.
- Suppliers: `ix_suppliers_created_page`.
- Purchase orders: `ix_purchase_orders_status_created_page`,
  `ix_purchase_orders_created_page`, `ix_purchase_orders_updated_page`,
  `ix_purchase_orders_status_total`, and
  `ix_purchase_orders_supplier_created_page`.
- Customers: `ix_customers_created_page`.
- Sales orders: `ix_sales_orders_customer_created_page`,
  `ix_sales_orders_created_page`, `ix_sales_orders_status_created_page`, and
  `ix_sales_orders_status_fulfilled_page`.
- Payments: `ix_payments_customer_status_received` and
  `ix_payments_received_page`.
- Invoices: `ix_invoices_customer_issued_page` and
  `ix_invoices_issued_page`.
- Audit logs: `ix_audit_created_page`.

The not-selected list below shows the definitions not chosen by the benchmark;
they were kept because they support other filters, sort choices, or production
workloads not represented by this synthetic data.

When deploying code that filters on `is_low_stock`, first run `init_db` to
create the indexes and then run the backfill command against the target
database, before routing traffic to the new code:

```powershell
.\backend\venv\Scripts\python.exe .\backend\manage.py init_db
.\backend\venv\Scripts\python.exe .\backend\manage.py backfill_stock_index_fields
```

The backfill is idempotent. Production requires
`--confirm-production`; review its output and take the normal database backup
before running it. Do not run the synthetic seed script against production.

### Indexes not selected by this workload

The final explain report listed 20 non-unique indexes not selected by the
synthetic query set:

- `audit_logs`: `ix_audit_entity_created`, `ix_audit_actor_created`,
  `ix_audit_action_created`, `ix_audit_created`
- `invoices`: `ix_invoices_customer_issued`,
  `ix_invoices_customer_issued_page`
- `payments`: `ix_payments_order_created`, `ix_payments_customer_status`,
  `ix_payments_customer_status_received`
- `products`: `ix_products_active_created`
- `purchase_orders`: `ix_purchase_orders_status_created_page`,
  `ix_purchase_orders_updated`
- `sales_orders`: `ix_sales_orders_status_created_page`
- `sales_returns`: `ix_sales_returns_customer_created`
- `stock_movements`: `ix_stock_product_created`,
  `ix_stock_product_created_page`, `ix_stock_reference`, `ix_stock_created`
- `users`: `ix_users_active_created`, `ix_users_role_active`

“Not selected” only means these indexes were not chosen by the benchmark's
specific query shapes and data distribution; it does not establish that they
are unused in production. Check query logs, index usage statistics over a
representative period, and all supported filters before considering an index
removal. Index removal is intentionally not automated by `init_db`.

### Query patterns and remaining limits

- The measured report `$lookup` operations are aggregation stages, not
  application-level N+1 queries. No per-result database-call loop was found in
  the measured list/report paths. Sales-return and employee joins are applied
  after sort and pagination where the join does not affect the ordering. The
  monthly sales report must consider all matching sales orders to calculate
  monthly totals; recent dashboard transactions limit each source before
  joining.
- Paged list routes cap page size at 100. Exact totals remain proportional to
  the number of matching index keys.
- Search uses escaped, unanchored substring expressions in some list filters.
  A normal B-tree index cannot efficiently satisfy arbitrary substring
  searches; those filtered query shapes may scan many candidates even though
  the default list plans are indexed. Evaluate Atlas Search or a supported
  prefix-search UX before changing search semantics.
- Category/designation distinct-value filters can grow with the number of
  distinct values. The benchmark observed 20 categories and 3 designations;
  those results are not currently capped or paginated.
- Monthly reports accept user-selected date ranges. Very large ranges can
  require substantial aggregation work and create many month rows. No arbitrary
  maximum range was introduced in this performance step.
- The explain script covers the default list pages, histories, reports, and
  dashboard query shapes in its seeded dataset. It does not cover every
  combination of optional filters and sort choices. Re-run it and inspect
  additional production query shapes before making index-removal decisions.

## Frontend bundle and loading

Page-level lazy loading was already in place. The dashboard chart library made
the Home page's previous chunk about 413 KB (about 116 KB gzip). Charts now live
in the lazy-loaded `frontend/src/components/DashboardCharts.jsx`, imported by
`frontend/src/pages/Home.jsx` only when the dashboard or an error is available
and the user has a relevant chart permission.

The production build after the split reported:

| Chunk | Size | Gzip |
|---|---:|---:|
| Home page | 6.35 KB | 2.14 KB |
| Dashboard charts | 408.28 KB | 115.12 KB |
| Shared entry chunk | 323.04 KB | 104.80 KB |

This moves chart code out of the initial Home page chunk; users who need the
charts still download the chart chunk when it is rendered. The build was
measured with Vite's production output. No new bundle-analysis dependency was
added. The dashboard request effect depends on permission and explicit retry,
not render state, so loading/error state updates do not repeat the API request.
Chart-data conversions are memoized by their source arrays. No browser Profiler
trace was captured, so this review does not claim measured render-time
improvements; the targeted Home tests verify that the lazy chart appears when
dashboard data is available.

## Ongoing maintenance

After changing repository queries or indexes:

1. Update index declarations and their tests in `backend/database/indexes.py`
   and `backend/tests/database/`.
2. Run `init_db` in a disposable local/test database.
3. Use fake-only seeded data and `seed_demo.py` to capture
   `explain("executionStats")` for the affected query shapes.
4. Compare `nReturned`, `totalKeysExamined`, `totalDocsExamined`, and the plan
   stages. Investigate `COLLSCAN`, blocking `SORT`, large examined-to-returned
   ratios, and unbounded result materialization.
5. Run the relevant backend tests and frontend checks; record representative
   before/after measurements here.
6. In production, review index storage/write costs and actual usage before
   adding or removing indexes. Keep a recoverable backup before a schema or
   data backfill.
