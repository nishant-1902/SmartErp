import { cleanup, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Home from './Home.jsx'
import { getDashboard } from '../services/reportsService.js'

const { permissionSet } = vi.hoisted(() => ({
  permissionSet: new Set(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => permissionSet.has(permission),
  }),
}))

vi.mock('../services/reportsService.js', () => ({
  getDashboard: vi.fn(),
}))

vi.mock('recharts', () => {
  const Chart = ({ children }) => <div>{children}</div>
  return {
    Bar: Chart,
    BarChart: Chart,
    CartesianGrid: Chart,
    Cell: Chart,
    Legend: Chart,
    Line: Chart,
    LineChart: Chart,
    Pie: Chart,
    PieChart: Chart,
    ResponsiveContainer: Chart,
    Tooltip: Chart,
    XAxis: Chart,
    YAxis: Chart,
  }
})

const dashboard = {
  total_employees: 12,
  total_products: 4,
  low_stock_count: 1,
  monthly_sales: {
    month: '2026-11',
    order_count: 3,
    net_sales: '120.00',
  },
  sales_chart: [
    { month: '2026-10', gross_sales: '130.00', net_sales: '120.00' },
  ],
  purchases_vs_sales: [
    {
      month: '2026-10',
      net_sales: '120.00',
      purchase_total: '80.00',
      purchase_count: 2,
    },
  ],
  inventory_by_category: [
    { category: 'Tools', product_count: 2, available_quantity: 9 },
  ],
  low_stock_products: [
    {
      sku: 'TOOL-1',
      name: 'Wrench',
      category: 'Tools',
      available_quantity: 1,
      min_stock_level: 2,
    },
  ],
  recent_transactions: [
    {
      id: 'transaction-1',
      number: 'SO-1',
      type: 'sale',
      party: 'Acme',
      status: 'fulfilled',
      occurred_at: '2026-11-02T10:00:00Z',
      amount: '120.00',
    },
  ],
}

beforeEach(() => {
  permissionSet.clear()
  ;[
    'reports:read',
    'employees:read',
    'products:read',
    'stock:read',
    'sales:read',
    'purchase:read',
  ].forEach((permission) => permissionSet.add(permission))
  getDashboard.mockResolvedValue(dashboard)
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Home', () => {
  it('renders metrics, charts, low-stock rows, and recent transactions from the API', async () => {
    render(<Home />)

    expect(await screen.findByText('Active employees')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('Sales this month')).toBeInTheDocument()
    expect(screen.getByText('Monthly sales')).toBeInTheDocument()
    expect(screen.getByText('Purchase commitments vs net sales')).toBeInTheDocument()
    expect(screen.getByText('Available inventory by category')).toBeInTheDocument()
    expect(screen.getByText('Wrench')).toBeInTheDocument()
    expect(screen.getByText('SO-1')).toBeInTheDocument()
    expect(getDashboard).toHaveBeenCalledWith(
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })

  it('shows only widgets allowed by the returned dashboard permissions', async () => {
    permissionSet.delete('sales:read')
    permissionSet.delete('purchase:read')
    permissionSet.delete('employees:read')
    getDashboard.mockResolvedValue({
      total_products: 4,
      low_stock_count: 1,
      inventory_by_category: [],
      low_stock_products: [],
    })

    render(<Home />)

    expect(await screen.findByText('Active products')).toBeInTheDocument()
    expect(screen.queryByText('Monthly sales')).not.toBeInTheDocument()
    expect(screen.queryByText('Recent transactions')).not.toBeInTheDocument()
    await waitFor(() => expect(getDashboard).toHaveBeenCalledTimes(1))
  })

  it('renders a retryable error in each dashboard widget after request failure', async () => {
    getDashboard.mockRejectedValue({
      response: {
        status: 503,
        data: { error: { message: 'Dashboard unavailable.' } },
      },
    })
    render(<Home />)

    expect(await screen.findAllByText('Dashboard unavailable.')).not.toHaveLength(0)
    expect(screen.getAllByRole('button', { name: 'Retry' }).length).toBeGreaterThan(1)
  })

  it('shows a widget-specific backend error without hiding other dashboard data', async () => {
    getDashboard.mockResolvedValue({
      total_products: 4,
      inventory_statistics: {
        active_products: 4,
        quantity_on_hand: 10,
        reserved_quantity: 1,
        available_quantity: 9,
        low_stock_count: 1,
        stock_cost_value: '20.00',
      },
      low_stock_count: 1,
      low_stock_products: [],
      widget_errors: {
        inventory_by_category: {
          code: 'widget_unavailable',
          message: 'This dashboard widget could not be loaded.',
        },
      },
    })

    render(<Home />)

    expect(await screen.findByText('Active products')).toBeInTheDocument()
    expect(screen.queryByText('Wrench')).not.toBeInTheDocument()
    expect(
      screen.getByRole('region', { name: 'Inventory by category' }),
    ).toHaveTextContent('This dashboard widget could not be loaded.')
    expect(screen.getAllByText('Low-stock products')).not.toHaveLength(0)
  })
})
