import { useEffect, useMemo, useState } from 'react'
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts'
import DataTable from '../components/DataTable.jsx'
import DashboardCard from '../components/DashboardCard.jsx'
import DashboardWidget from '../components/DashboardWidget.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { getDashboard } from '../services/reportsService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

const chartColors = ['#3157d5', '#16a085', '#e67e22', '#8e44ad', '#d64550']

function formatDate(value) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed)
}

function chartMoneyTick(value) {
  return Number(value).toLocaleString(undefined, {
    maximumFractionDigits: 0,
  })
}

function tooltipMoney(value, name, payload, dataKey) {
  const sourceKey = dataKey?.replace(/_chart$/, '')
  const exactValue = payload?.[sourceKey] ?? String(value ?? 0)
  return [formatMoney(exactValue), name]
}

/**
 * Renders live, permission-filtered dashboard widgets from the reports API.
 *
 * @returns {JSX.Element}
 */
export default function Home() {
  const { hasPermission } = useAuth()
  const canReadReports = hasPermission('reports:read')
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

  const salesChartData = useMemo(
    () =>
      (dashboard?.sales_chart ?? []).map((month) => ({
        ...month,
        gross_sales_chart: Number(month.gross_sales),
        net_sales_chart: Number(month.net_sales),
      })),
    [dashboard],
  )

  const comparisonData = useMemo(
    () =>
      (dashboard?.purchases_vs_sales ?? []).map((month) => ({
        ...month,
        purchase_total_chart: Number(month.purchase_total),
        net_sales_chart: Number(month.net_sales),
      })),
    [dashboard],
  )

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
    { key: 'sku', label: 'SKU' },
    { key: 'name', label: 'Product' },
    { key: 'category', label: 'Category' },
    { key: 'available_quantity', label: 'Available' },
    { key: 'min_stock_level', label: 'Minimum' },
  ]

  const availableMetrics = metrics.filter(
    (metric) =>
      hasPermission(metric.permission) &&
      (loading ||
        error ||
        dashboard?.[metric.key] !== undefined ||
        dashboard?.widget_errors?.[metric.key] !== undefined),
  )

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

      {hasPermission('sales:read') && (
        <div className="row g-3 mb-3">
          <div className="col-12 col-xl-6">
            <DashboardWidget
              available={dashboard?.sales_chart !== undefined}
              error={widgetError('sales_chart')}
              loading={loading}
              onRetry={retry}
              title="Monthly sales"
            >
              <div className="surface-card dashboard-chart p-3">
                <h2 className="h6 mb-3">Monthly sales</h2>
                {salesChartData.length === 0 ? (
                  <p className="text-muted mb-0">No monthly sales data returned.</p>
                ) : (
                  <ResponsiveContainer height={280} width="100%">
                    <LineChart data={salesChartData}>
                      <CartesianGrid stroke="#e8edf5" strokeDasharray="3 3" />
                      <XAxis dataKey="month" />
                      <YAxis tickFormatter={chartMoneyTick} />
                      <Tooltip formatter={(value, name, item) =>
                        tooltipMoney(value, name, item.payload, item.dataKey)
                      } />
                      <Legend />
                      <Line
                        dataKey="gross_sales_chart"
                        name="Gross sales"
                        stroke={chartColors[0]}
                        strokeWidth={2}
                        type="monotone"
                      />
                      <Line
                        dataKey="net_sales_chart"
                        name="Net sales"
                        stroke={chartColors[1]}
                        strokeWidth={2}
                        type="monotone"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </div>
            </DashboardWidget>
          </div>
          {hasPermission('purchase:read') && (
            <div className="col-12 col-xl-6">
              <DashboardWidget
                available={dashboard?.purchases_vs_sales !== undefined}
                error={widgetError('purchases_vs_sales')}
                loading={loading}
                onRetry={retry}
                title="Purchases versus sales"
              >
                <div className="surface-card dashboard-chart p-3">
                  <h2 className="h6 mb-3">Purchase commitments vs net sales</h2>
                  {comparisonData.length === 0 ? (
                    <p className="text-muted mb-0">No comparison data returned.</p>
                  ) : (
                    <ResponsiveContainer height={280} width="100%">
                      <BarChart data={comparisonData}>
                        <CartesianGrid stroke="#e8edf5" strokeDasharray="3 3" />
                        <XAxis dataKey="month" />
                        <YAxis tickFormatter={chartMoneyTick} />
                        <Tooltip formatter={(value, name, item) =>
                          tooltipMoney(value, name, item.payload, item.dataKey)
                        } />
                        <Legend />
                        <Bar dataKey="purchase_total_chart" fill={chartColors[2]} name="Purchases" />
                        <Bar dataKey="net_sales_chart" fill={chartColors[0]} name="Net sales" />
                      </BarChart>
                    </ResponsiveContainer>
                  )}
                  <p className="small text-muted mb-0">
                    Purchases use non-draft purchase-order totals by creation month.
                  </p>
                </div>
              </DashboardWidget>
            </div>
          )}
        </div>
      )}

      {hasPermission('stock:read') && hasPermission('products:read') && (
        <div className="row g-3 mb-3">
          <div className="col-12 col-xl-6">
            <DashboardWidget
              available={dashboard?.inventory_by_category !== undefined}
              error={widgetError('inventory_by_category')}
              loading={loading}
              onRetry={retry}
              title="Inventory by category"
            >
              <div className="surface-card dashboard-chart p-3">
                <h2 className="h6 mb-3">Available inventory by category</h2>
                {dashboard?.inventory_by_category?.length === 0 ? (
                  <p className="text-muted mb-0">No active inventory was returned.</p>
                ) : (
                  <ResponsiveContainer height={280} width="100%">
                    <PieChart>
                      <Pie
                        data={dashboard?.inventory_by_category ?? []}
                        dataKey="available_quantity"
                        nameKey="category"
                        outerRadius={95}
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {(dashboard?.inventory_by_category ?? []).map((entry, index) => (
                          <Cell fill={chartColors[index % chartColors.length]} key={entry.category} />
                        ))}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </DashboardWidget>
          </div>
          <div className="col-12 col-xl-6">
            <DashboardWidget
              available={dashboard?.low_stock_products !== undefined}
              error={widgetError('low_stock_products')}
              loading={loading}
              onRetry={retry}
              title="Low-stock products"
            >
              <div className="surface-card dashboard-chart p-3">
                <h2 className="h6 mb-3">Low-stock products</h2>
                <DataTable
                  columns={lowStockColumns}
                  data={dashboard?.low_stock_products ?? []}
                  emptyMessage="No active products are below their stock minimum."
                />
              </div>
            </DashboardWidget>
          </div>
        </div>
      )}

      {(hasPermission('sales:read') || hasPermission('purchase:read')) && (
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
