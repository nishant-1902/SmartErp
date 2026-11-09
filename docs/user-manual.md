# SmartERP User Manual

## Scope and access

This guide describes the screens currently present in `frontend/src/pages`
and the route/permission guards in `frontend/src/App.jsx`. Your administrator
creates your account and assigns one of these roles: Super Admin, HR Manager,
Inventory Manager, Purchase Manager, or Sales Manager. Screens and actions
depend on the server-side permission matrix. A hidden menu item does not mean
you can call its API directly.

Open the application URL supplied by your administrator (local development is
`http://127.0.0.1:5173/`). Sign in at **Login** with your assigned email and
password. Use **Forgot password?** if that flow is enabled for your account.
After login, **Overview** shows dashboard data allowed for your role. Use the
sidebar to open available modules. Lists support search, filters, and
pagination where provided; use detail links to inspect one record. Forms show
validation errors beside fields; save only after reviewing the values.

## Screens shared across roles

- **Overview (`/`)** — summary cards and lazy-loaded charts from the dashboard
  API. The content is permission-filtered; a chart error is separate from login.
- **Profile (`/profile`)** — your account and linked employee details when
  available.
- **Settings (`/settings`)** — change your password. Sign in again if your
  session expires.
- **403 (`/403`)** — the account lacks permission for the requested screen.
- **Not found** — the requested frontend URL is not a defined screen.

## Super Admin

1. Open **Users**. Create a user, choose the role, and set the initial account
   details. The user must change their password if the configured flow requires
   it.
2. Use the user row actions to activate, deactivate, or reset a user's
   password. Deactivation blocks authentication while preserving business
   history.
3. Open **Employees** and **Departments** to maintain staff records and
   department assignments. Use employee detail pages for profile information.
4. Maintain **Products**, **Suppliers**, and **Customers** through their list
   and detail screens. Use the dedicated forms and respect unique code errors.
5. Use **Purchase Orders** and **Sales Orders** to review workflows; use
   **Inventory** and **Stock Movements** to inspect stock changes.
6. Open **Reports** for permitted operational summaries and **Audit Logs** to
   review recorded security and business events.

## HR Manager

1. Open **Employees** to search and page through the directory; select a row
   for **Employee Profile**. Use the employee form to add or update permitted
   employee fields.
2. Open **Departments** to maintain department records and inspect the linked
   employee list.
3. Use **Reports** for employee and department summaries when the role's
   report permission permits them.
4. Use **Profile** and **Settings** for your own details and password.

The current frontend permits the employee directory route for HR, inventory,
purchase, sales, and super-admin roles; the backend permission matrix remains
the authority for each operation.

## Inventory Manager

1. Open **Products** to search the catalogue. Select a product to view its
   details and current stock information.
2. Open **Inventory** to review stock levels and low-stock items.
3. Use the stock adjustment action only for a justified correction. Enter the
   adjustment quantity and reason, review the confirmation, and submit once.
   A successful adjustment records a stock movement.
4. Open **Stock Movements** to trace receipts, fulfilments, returns, and manual
   adjustments. Use the movement details to explain a quantity change.
5. Open **Purchase Orders** to review orders and receive approved goods. For a
   receipt, select the received quantities, verify them against the delivery,
   and submit; partial receipts may be followed by later receipts.
6. Open **Sales Orders** to view work requiring fulfilment. Confirm the order
   status and available stock before fulfilling it.

## Purchase Manager

1. Open **Suppliers** to search the supplier directory and select a supplier
   for its details and purchase-order history.
2. Open **Purchase Orders**, then choose **New** to select a supplier and
   products. Review quantities, unit costs, and calculated totals before
   saving.
3. Submit a draft order for approval. Use the order detail screen to review
   lines and status. Approve, reject with a reason, or cancel when those actions
   are available for the current status.
4. Track delivery on the order detail screen. Receiving goods is an inventory
   operation and may be permission-restricted to the Inventory Manager.
5. Use **Reports** to inspect purchase and supplier summaries if authorized.

## Sales Manager

1. Open **Customers** to search the customer list. Select a customer to view
   details and sales-order history. Create or update customer information when
   permitted.
2. Open **Sales Orders**, choose **New**, select a customer and products, and
   review quantities, prices, and totals before saving the draft.
3. Open a sales order's detail screen to confirm or cancel it according to its
   current status. Inventory availability is checked by the backend.
4. Follow fulfilment status in the order detail view. An authorized inventory
   user completes fulfilment, which updates stock and creates movement history.
5. Use the order detail/payment controls to record a payment. Review the amount
   and method carefully; payment records affect the balance and audit trail.
6. Use the return action for an eligible fulfilled order. Select returned
   lines/quantities and submit once after checking the confirmation.
7. Open **Invoices** from the order workflow to review or print the invoice.
   Open **Reports** for sales summaries and CSV export when available.

## Employee

1. Sign in with the account created by an administrator. The Employee role
   cannot open manager directories or business modules unless permissions are
   explicitly granted by the backend matrix.
2. Open **Profile** to review your own account details and linked employee
   information when present.
3. Open **Settings** to change your own password. Use the password reset flow
   if you cannot sign in.

The current frontend does not provide a separate Employee directory screen for
this role; employee directory access is limited to the manager roles listed
above.

## Common problems

- **Login rejected:** check email/password and ask an administrator to confirm
  the account is active or issue a reset.
- **403 Forbidden:** ask the administrator to confirm the assigned role. Do not
  retry by changing the URL; backend authorization still applies.
- **Validation or duplicate error:** correct the highlighted field. Product,
  supplier, customer, and employee codes may need to be unique.
- **Stale stock or order status:** reload the detail page. Another user may
  have changed the record; the backend rechecks stock and allowed transitions.
- **Refresh/API/network error:** contact support with the screen, approximate
  time, and action. Never send a password, cookie, or access token in a report.

## Screenshots

No screenshots are included yet. The UI changes over time, so use current
screenshots only after capturing them with synthetic or redacted data. Planned
screenshots: Login, Overview, Employees, Products/Inventory, Purchase Order
detail, Sales Order detail, Reports, and Audit Logs. The route files defining
these screens are in `frontend/src/pages` and `frontend/src/App.jsx`.

## Feature boundary

This is a guide to implemented page routes and actions visible in the current
frontend. Exact control visibility depends on role and record status. Live
production deployment, administrator provisioning, and MongoDB transaction
behavior must be configured and verified by the operator.
