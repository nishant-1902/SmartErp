import { lazy, Suspense, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import DataTable from '../components/DataTable.jsx'
import DashboardCard from '../components/DashboardCard.jsx'
import DashboardWidget from '../components/DashboardWidget.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { getDashboard } from '../services/reportsService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

const DashboardCharts = lazy(() => import('../components/DashboardCharts.jsx'))

function formatDate(value) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed)
}

/**
 * Renders live, permission-filtered dashboard widgets from the reports API.
 *
 * @returns {JSX.Element}
 */
export default function Home() {
  const { hasPermission } = useAuth()
  const canReadReports = hasPermission('reports:read')
  const canReadSales = hasPermission('sales:read')
  const canReadPurchases = hasPermission('purchase:read')
  const [dashboard, setDashboard] = useState(null)
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(true)
  const [retryKey, setRetryKey] = useState(0)

  useEffect(() => {
    if (!canReadReports) return undefined
    const controller = new AbortController()
    getDashboard({ signal: controller.signal })
      .then((result) => {
        if (!controller.signal.aborted) setDashboard(result)
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) {
          setError(getApiError(requestError).message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [canReadReports, retryKey])

  const retry = () => {
    setError('')
    setLoading(true)
    setRetryKey((current) => current + 1)
  }
  const widgetError = (key) =>
    error || dashboard?.widget_errors?.[key]?.message || ''

  if (!canReadReports) {
    return (
      <section>
        <div className="page-heading">
          <p className="text-primary text-uppercase fw-bold small mb-2">Overview</p>
          <h1>Dashboard</h1>
          <p className="mb-0">Your account does not have access to report widgets.</p>
        </div>
      </section>
    )
  }

  const metrics = [
    { key: 'total_employees', title: 'Active employees', permission: 'employees:read' },
    { key: 'total_departments', title: 'Departments', permission: 'departments:read' },
    { key: 'total_products', title: 'Active products', permission: 'products:read' },
    { key: 'low_stock_count', title: 'Low-stock products', permission: 'stock:read' },
    { key: 'total_suppliers', title: 'Active suppliers', permission: 'suppliers:read' },
    { key: 'total_customers', title: 'Active customers', permission: 'customers:read' },
    { key: 'pending_purchase_orders', title: 'Pending purchase orders', permission: 'purchase:read' },
  ]

  const transactionColumns = [
    { key: 'number', label: 'Reference' },
    { key: 'type', label: 'Type', render: (row) => row.type.replaceAll('_', ' ') },
    { key: 'party', label: 'Customer / supplier' },
    { key: 'status', label: 'Status', render: (row) => row.status.replaceAll('_', ' ') },
    { key: 'occurred_at', label: 'Date', render: (row) => formatDate(row.occurred_at) },
    { key: 'amount', label: 'Net / total', render: (row) => formatMoney(row.amount) },
  ]

  const lowStockColumns = [
    {
      key: 'name',
      label: 'Product',
      className: 'low-stock-product-cell',
      render: (product) => <span className="low-stock-product-name" title={product.name}>{product.name}</span>,
    },
    {
      key: 'sku',
      label: 'SKU',
      className: 'low-stock-sku-cell',
      render: (product) => product.id
        ? <Link to={`/products/${product.id}`}>{product.sku}</Link>
        : product.sku,
    },
    {
      key: 'available_quantity',
      label: 'Available',
      className: 'text-end low-stock-quantity-cell',
    },
    {
      key: 'min_stock_level',
      label: 'Minimum stock',
      className: 'text-end low-stock-minimum-cell',
    },
    {
      key: 'stock_status',
      label: 'Status',
      className: 'low-stock-status-cell',
      render: (product) => {
        const outOfStock = Number(product.available_quantity) <= 0
        return (
          <span className={`badge ${outOfStock ? 'low-stock-badge low-stock-badge--empty' : 'low-stock-badge low-stock-badge--warning'}`}>
            {outOfStock ? 'Out of Stock' : 'Low Stock'}
          </span>
        )
      },
    },
  ]

  const availableMetrics = metrics.filter(
    (metric) =>
      hasPermission(metric.permission) &&
      (loading ||
        error ||
        dashboard?.[metric.key] !== undefined ||
        dashboard?.widget_errors?.[metric.key] !== undefined),
  )
  const canReadInventory =
    hasPermission('stock:read') && hasPermission('products:read')
  const hasDashboardCharts =
    hasPermission('sales:read') || canReadInventory

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Overview</p>
        <h1>Dashboard</h1>
        <p className="mb-0">Live business activity and inventory health.</p>
      </div>

      <div className="row g-3 mb-3">
        {availableMetrics.map((metric) => (
          <div className="col-12 col-sm-6 col-xl-3" key={metric.key}>
            <DashboardWidget
              available={dashboard?.[metric.key] !== undefined}
              error={widgetError(metric.key)}
              loading={loading}
              onRetry={retry}
              title={metric.title}
            >
              <DashboardCard
                label={metric.title}
                value={dashboard?.[metric.key]}
              />
            </DashboardWidget>
          </div>
        ))}
        {hasPermission('sales:read') &&
          (
            loading ||
            error ||
            dashboard?.monthly_sales ||
            dashboard?.widget_errors?.monthly_sales
          ) && (
            <div className="col-12 col-sm-6 col-xl-3">
              <DashboardWidget
                available={Boolean(dashboard?.monthly_sales)}
                error={widgetError('monthly_sales')}
                loading={loading}
                onRetry={retry}
                title="Sales this month"
              >
                <DashboardCard
                  detail={`${dashboard?.monthly_sales?.order_count} fulfilled orders`}
                  label="Sales this month"
                  value={dashboard?.monthly_sales?.net_sales
                    ? formatMoney(dashboard.monthly_sales.net_sales)
                    : '—'}
                />
              </DashboardWidget>
            </div>
          )}
      </div>

      {hasDashboardCharts && !dashboard && loading && (
        <div className="row g-3 mb-3">
          {canReadSales && (
            <div className="col-12 col-xl-6">
              <DashboardWidget loading title="Monthly sales" />
            </div>
          )}
          {canReadInventory && (
            <div className="col-12 col-xl-6">
              <DashboardWidget loading title="Inventory by category" />
            </div>
          )}
        </div>
      )}

      {hasDashboardCharts && (dashboard || error) && (
        <Suspense
          fallback={
            <div className="surface-card p-3">
              <LoadingSpinner label="Loading dashboard charts" />
            </div>
          }
        >
          <DashboardCharts
            canReadInventory={canReadInventory}
            canReadPurchases={canReadPurchases}
            canReadSales={canReadSales}
            dashboard={dashboard ?? {}}
            loading={loading}
            onRetry={retry}
            widgetError={widgetError}
          />
        </Suspense>
      )}

      {canReadInventory && (dashboard || error) && (
        <div className="row g-3 mb-3">
          <div className="col-12">
            <DashboardWidget
              available={dashboard?.low_stock_products !== undefined}
              error={widgetError('low_stock_products')}
              loading={loading}
              onRetry={retry}
              title="Low-stock products"
            >
              <div className="surface-card dashboard-chart low-stock-dashboard-card p-3">
                <div className="low-stock-dashboard-heading">
                  <h2 className="h6 mb-0">Low-stock products</h2>
                  <Link className="btn btn-outline-primary btn-sm" to="/inventory?low_stock=true">
                    View all
                  </Link>
                </div>
                <DataTable
                  className="dashboard-low-stock-table"
                  columns={lowStockColumns}
                  data={(dashboard?.low_stock_products ?? []).slice(0, 6)}
                  emptyMessage="No active products are below their stock minimum."
                />
              </div>
            </DashboardWidget>
          </div>
        </div>
      )}

      {(canReadSales || canReadPurchases) && (
        <DashboardWidget
          available={dashboard?.recent_transactions !== undefined}
          error={widgetError('recent_transactions')}
          loading={loading}
          onRetry={retry}
          title="Recent transactions"
        >
          <div className="surface-card dashboard-chart p-3">
            <h2 className="h6 mb-3">Recent transactions</h2>
            <DataTable
              columns={transactionColumns}
              data={dashboard?.recent_transactions ?? []}
              emptyMessage="No recent transactions were returned."
            />
          </div>
        </DashboardWidget>
      )}
    </section>
  )
}
