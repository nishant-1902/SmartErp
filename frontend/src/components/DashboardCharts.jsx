import { useMemo } from 'react'
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
import DashboardWidget from './DashboardWidget.jsx'
import { formatMoney } from '../utils/formatMoney.js'

const chartColors = ['#3157d5', '#16a085', '#e67e22', '#8e44ad', '#d64550']

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
 * Renders report charts in a separate chunk loaded after dashboard data arrives.
 *
 * @param {{canReadSales: boolean, canReadPurchases: boolean, canReadInventory: boolean, dashboard: object, loading: boolean, onRetry: () => void, widgetError: (key: string) => string}} props
 */
export default function DashboardCharts({
  canReadInventory,
  canReadPurchases,
  canReadSales,
  dashboard,
  loading,
  onRetry,
  widgetError,
}) {
  const salesChartData = useMemo(
    () =>
      (dashboard.sales_chart ?? []).map((month) => ({
        ...month,
        gross_sales_chart: Number(month.gross_sales),
        net_sales_chart: Number(month.net_sales),
      })),
    [dashboard.sales_chart],
  )

  const comparisonData = useMemo(
    () =>
      (dashboard.purchases_vs_sales ?? []).map((month) => ({
        ...month,
        purchase_total_chart: Number(month.purchase_total),
        net_sales_chart: Number(month.net_sales),
      })),
    [dashboard.purchases_vs_sales],
  )

  return (
    <>
      {canReadSales && (
        <div className="row g-3 mb-3">
          <div className="col-12 col-xl-6">
            <DashboardWidget
              available={dashboard.sales_chart !== undefined}
              error={widgetError('sales_chart')}
              loading={loading}
              onRetry={onRetry}
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
                      <Tooltip
                        formatter={(value, name, item) =>
                          tooltipMoney(value, name, item.payload, item.dataKey)
                        }
                      />
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
          {canReadPurchases && (
            <div className="col-12 col-xl-6">
              <DashboardWidget
                available={dashboard.purchases_vs_sales !== undefined}
                error={widgetError('purchases_vs_sales')}
                loading={loading}
                onRetry={onRetry}
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
                        <Tooltip
                          formatter={(value, name, item) =>
                            tooltipMoney(value, name, item.payload, item.dataKey)
                          }
                        />
                        <Legend />
                        <Bar
                          dataKey="purchase_total_chart"
                          fill={chartColors[2]}
                          name="Purchases"
                        />
                        <Bar
                          dataKey="net_sales_chart"
                          fill={chartColors[0]}
                          name="Net sales"
                        />
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

      {canReadInventory && (
        <div className="row g-3 mb-3">
          <div className="col-12 col-xl-6">
            <DashboardWidget
              available={dashboard.inventory_by_category !== undefined}
              error={widgetError('inventory_by_category')}
              loading={loading}
              onRetry={onRetry}
              title="Inventory by category"
            >
              <div className="surface-card dashboard-chart p-3">
                <h2 className="h6 mb-3">Available inventory by category</h2>
                {dashboard.inventory_by_category?.length === 0 ? (
                  <p className="text-muted mb-0">No active inventory was returned.</p>
                ) : (
                  <ResponsiveContainer height={280} width="100%">
                    <PieChart>
                      <Pie
                        data={dashboard.inventory_by_category ?? []}
                        dataKey="available_quantity"
                        nameKey="category"
                        outerRadius={95}
                        label={({ name, value }) => `${name}: ${value}`}
                      >
                        {(dashboard.inventory_by_category ?? []).map(
                          (entry, index) => (
                            <Cell
                              fill={chartColors[index % chartColors.length]}
                              key={entry.category}
                            />
                          ),
                        )}
                      </Pie>
                      <Tooltip />
                      <Legend />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </div>
            </DashboardWidget>
          </div>
        </div>
      )}
    </>
  )
}
