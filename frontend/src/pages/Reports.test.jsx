import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import Reports from './Reports.jsx'
import { getInventorySummary, listReport } from '../services/reportsService.js'

const { permissionSet, downloadCsvMock } = vi.hoisted(() => ({
  permissionSet: new Set(),
  downloadCsvMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => permissionSet.has(permission),
  }),
}))

vi.mock('../services/reportsService.js', () => ({
  getInventorySummary: vi.fn(),
  listReport: vi.fn(),
}))

vi.mock('../utils/csvExport.js', () => ({
  downloadCsv: downloadCsvMock,
}))

beforeEach(() => {
  permissionSet.clear()
  ;[
    'reports:read',
    'sales:read',
    'products:read',
    'stock:read',
    'purchase:read',
    'employees:read',
  ].forEach((permission) => permissionSet.add(permission))
  listReport.mockResolvedValue({
    items: [
      {
        id: 'sale-1',
        order_number: 'SO-1',
        customer_snapshot: { name: 'Acme' },
        fulfilled_at: '2026-03-10T00:00:00Z',
        grand_total: '100.00',
        returns_total: '10.00',
        net_total: '90.00',
      },
    ],
    meta: { page: 1, page_size: 20, total: 21, total_pages: 2 },
  })
  getInventorySummary.mockResolvedValue({
    active_products: 4,
    available_quantity: 17,
    reserved_quantity: 3,
    stock_cost_value: '250.00',
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Reports page', () => {
  it('filters report dates, paginates results, and exports returned rows', async () => {
    render(<Reports />)

    expect(await screen.findByText('SO-1')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Date from'), {
      target: { value: '2026-03-01' },
    })
    fireEvent.change(screen.getByLabelText('Date to'), {
      target: { value: '2026-03-31' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply dates' }))

    await waitFor(() => {
      expect(listReport).toHaveBeenLastCalledWith(
        'sales',
        expect.objectContaining({
          date_from: '2026-03-01',
          date_to: '2026-03-31',
          page: 1,
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    await waitFor(() => {
      expect(listReport).toHaveBeenLastCalledWith(
        'sales',
        expect.objectContaining({ page: 2 }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })

    fireEvent.click(screen.getByRole('button', { name: 'Export current page CSV' }))
    expect(downloadCsvMock).toHaveBeenCalledWith(
      expect.arrayContaining([
        expect.objectContaining({ key: 'order_number', label: 'Order' }),
      ]),
      expect.arrayContaining([expect.objectContaining({ order_number: 'SO-1' })]),
      'sales',
    )
  })

  it('loads inventory summary and paginated low-stock rows independently', async () => {
    render(<Reports />)
    fireEvent.click(screen.getByRole('tab', { name: 'Inventory' }))

    expect(await screen.findByText('Stock cost value')).toBeInTheDocument()
    expect(screen.getByText(/250\.00/)).toBeInTheDocument()
    await waitFor(() => {
      expect(getInventorySummary).toHaveBeenCalledWith(
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
      expect(listReport).toHaveBeenLastCalledWith(
        'lowStock',
        expect.objectContaining({ page: 1, page_size: 20 }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })
  })

  it('keeps the inventory summary visible when the low-stock list fails', async () => {
    listReport.mockRejectedValue({
      response: {
        status: 503,
        data: { error: { message: 'Low-stock report unavailable.' } },
      },
    })
    render(<Reports />)
    fireEvent.click(screen.getByRole('tab', { name: 'Inventory' }))

    expect(await screen.findByText('Stock cost value')).toBeInTheDocument()
    expect(await screen.findByText('Low-stock report unavailable.')).toBeInTheDocument()
    expect(screen.getByText(/250\.00/)).toBeInTheDocument()
  })

  it('limits visible tabs to the user’s data permissions', () => {
    permissionSet.delete('sales:read')
    permissionSet.delete('products:read')
    permissionSet.delete('stock:read')
    permissionSet.delete('purchase:read')

    render(<Reports />)

    expect(screen.queryByRole('tab', { name: 'Sales' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Inventory' })).not.toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Purchases' })).not.toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Employees' })).toBeInTheDocument()
  })

  it('rejects reversed date ranges before calling the report service', async () => {
    render(<Reports />)
    await screen.findByText('SO-1')
    const callsBefore = listReport.mock.calls.length
    fireEvent.change(screen.getByLabelText('Date from'), {
      target: { value: '2026-04-02' },
    })
    fireEvent.change(screen.getByLabelText('Date to'), {
      target: { value: '2026-04-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply dates' }))

    expect(await screen.findByText('End date must be on or after the start date.')).toBeInTheDocument()
    expect(listReport).toHaveBeenCalledTimes(callsBefore)
  })
})
