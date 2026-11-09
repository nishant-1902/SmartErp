import { useMemo, useState } from 'react'
import Button from 'react-bootstrap/Button'
import { Link } from 'react-router-dom'
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

const chartColors = ['#4776e6', '#20a58a', '#9271db', '#e6a34b', '#d96c78', '#48a6bd']

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

function InventoryStat({ label, value, detail }) {
  return (
    <div className="inventory-stat">
      <span className="inventory-stat__label">{label}</span>
      <strong className="inventory-stat__value">{value ?? '—'}</strong>
      {detail && <span className="inventory-stat__detail">{detail}</span>}
    </div>
  )
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
  const [selectedCategory, setSelectedCategory] = useState(null)
  const [hiddenCategories, setHiddenCategories] = useState([])
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

  const inventoryData = useMemo(
    () => (dashboard.inventory_by_category ?? []).map((item, index) => ({
      ...item,
      available_quantity: Number(item.available_quantity) || 0,
      color: chartColors[index % chartColors.length],
    })),
    [dashboard.inventory_by_category],
  )
  const visibleInventoryData = inventoryData.filter(
    (item) => !hiddenCategories.includes(item.category),
  )
  const hasVisibleQuantity = visibleInventoryData.some((item) => item.available_quantity > 0)
  const inventoryBarHeight = Math.max(160, visibleInventoryData.length * 36 + 24)
  const inventoryStats = dashboard.inventory_statistics ?? {}

  function toggleCategory(category) {
    setHiddenCategories((current) => current.includes(category)
      ? current.filter((value) => value !== category)
      : [...current, category])
  }

  function selectCategory(payload) {
    const category = payload?.category ?? payload?.payload?.category
    if (category) setSelectedCategory(category)
  }

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
          <div className="col-12">
            <DashboardWidget
              available={dashboard.inventory_by_category !== undefined}
              error={widgetError('inventory_by_category')}
              loading={loading}
              onRetry={onRetry}
              title="Inventory by category"
            >
              <div className="surface-card dashboard-chart inventory-dashboard p-3 p-md-4">
                <div className="d-flex flex-wrap align-items-start justify-content-between gap-2 mb-3">
                  <div>
                    <h2 className="h6 mb-1">Available inventory by category</h2>
                    <p className="small text-muted mb-0">Available units across active products</p>
                  </div>
                  {selectedCategory && (
                    <Button onClick={() => setSelectedCategory(null)} size="sm" variant="outline-secondary">
                      Reset selection
                    </Button>
                  )}
                </div>
                {inventoryData.length === 0 ? (
                  <div className="inventory-empty-state" role="status">
                    <span aria-hidden="true" className="inventory-empty-state__mark">◌</span>
                    <strong>No inventory categories yet</strong>
                    <span className="text-muted">Category distribution will appear when active products have stock data.</span>
                  </div>
                ) : (
                  <>
                    <div className="row g-4 align-items-center">
                      <div className="col-12 col-lg-5 col-xl-4">
                        <div aria-label="Available stock distribution by category" className="inventory-donut-frame" role="img">
                          {hasVisibleQuantity ? (
                            <ResponsiveContainer height="100%" width="100%">
                              <PieChart>
                                <Pie
                                  data={visibleInventoryData}
                                  dataKey="available_quantity"
                                  innerRadius="58%"
                                  nameKey="category"
                                  outerRadius="82%"
                                  paddingAngle={2}
                                  onClick={selectCategory}
                                >
                                  {visibleInventoryData.map((entry) => (
                                    <Cell
                                      fill={entry.color}
                                      key={entry.category}
                                      opacity={selectedCategory && selectedCategory !== entry.category ? 0.35 : 1}
                                      stroke="var(--erp-surface)"
                                      strokeWidth={2}
                                    />
                                  ))}
                                </Pie>
                                <Tooltip formatter={(value, name) => [`${value} units`, name]} />
                              </PieChart>
                            </ResponsiveContainer>
                          ) : (
                            <div className="inventory-chart-empty" role="status">{visibleInventoryData.length ? 'No available units in the visible categories.' : 'All categories are hidden.'}</div>
                          )}
                        </div>
                        <div aria-label="Inventory categories" className="inventory-legend">
                          {inventoryData.map((entry) => {
                            const visible = !hiddenCategories.includes(entry.category)
                            return (
                              <button
                                aria-pressed={visible}
                                className={`inventory-legend__item${visible ? '' : ' is-hidden'}`}
                                key={entry.category}
                                onClick={() => toggleCategory(entry.category)}
                                type="button"
                              >
                                <span aria-hidden="true" className="inventory-legend__swatch" style={{ '--legend-color': entry.color }} />
                                <span>{entry.category}</span>
                              </button>
                            )
                          })}
                        </div>
                      </div>
                      <div className="col-12 col-lg-7 col-xl-8">
                        <div className="inventory-summary-grid">
                          <InventoryStat label="Active products" value={inventoryStats.active_products ?? dashboard.total_products} />
                          <InventoryStat label="Available stock" value={inventoryStats.available_quantity} />
                          <InventoryStat label="Reserved stock" value={inventoryStats.reserved_quantity} />
                          <InventoryStat label="Low stock" value={inventoryStats.low_stock_count ?? dashboard.low_stock_count} />
                          <InventoryStat label="Out of stock" value={null} detail="Not reported by API" />
                        </div>
                        <div aria-live="polite" className="inventory-selection mt-3">
                          {selectedCategory ? (() => {
                            const item = inventoryData.find((value) => value.category === selectedCategory)
                            return item ? <><strong>{item.category}</strong><span>{item.product_count} products · {item.available_quantity} available units</span><Link className="small ms-auto" to={`/products?category=${encodeURIComponent(item.category)}`}>View products</Link></> : <span>Select a visible category to inspect its stock.</span>
                          })() : <span>Select a chart segment or category bar to inspect that category.</span>}
                        </div>
                      </div>
                    </div>
                    <div className="inventory-category-chart mt-4">
                      <div className="d-flex flex-wrap align-items-baseline justify-content-between gap-2 mb-2">
                        <h3 className="small fw-semibold mb-0">Stock by category</h3>
                        <span className="small text-muted">Available units</span>
                      </div>
                      <div className="inventory-bar-frame" style={{ height: inventoryBarHeight }}>
                        <ResponsiveContainer height="100%" width="100%">
                          <BarChart data={visibleInventoryData} layout="vertical" margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
                            <CartesianGrid horizontal={false} stroke="var(--erp-border)" />
                            <XAxis allowDecimals={false} axisLine={false} tickLine={false} type="number" />
                            <YAxis axisLine={false} dataKey="category" tickLine={false} type="category" width={110} />
                            <Tooltip formatter={(value) => [`${value} units`, 'Available']} />
                            <Bar dataKey="available_quantity" radius={[0, 5, 5, 0]} onClick={selectCategory}>
                              {visibleInventoryData.map((entry) => <Cell fill={entry.color} key={entry.category} cursor="pointer" opacity={selectedCategory && selectedCategory !== entry.category ? 0.35 : 1} />)}
                            </Bar>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    </div>
                  </>
                )}
              </div>
            </DashboardWidget>
          </div>
        </div>
      )}
    </>
  )
}
