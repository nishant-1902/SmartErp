import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import SalesOrders from './SalesOrders.jsx'

const { authState, listCustomersMock, listSalesOrdersMock } = vi.hoisted(() => ({
  authState: { permissions: ['sales:read', 'sales:create', 'customers:read'] },
  listCustomersMock: vi.fn(),
  listSalesOrdersMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../services/customerService.js', () => ({
  listCustomers: listCustomersMock,
}))

vi.mock('../services/salesOrderService.js', () => ({
  listSalesOrders: listSalesOrdersMock,
}))

beforeEach(() => {
  authState.permissions = ['sales:read', 'sales:create', 'customers:read']
  listCustomersMock.mockResolvedValue({
    items: [{ id: 'customer-1', code: 'CUS-1', name: 'Acme' }],
  })
  listSalesOrdersMock.mockResolvedValue({
    items: [{
      id: 'order-1',
      order_number: 'SO-2026-000001',
      customer_snapshot: { name: 'Acme' },
      created_at: '2026-01-02T00:00:00Z',
      status: 'fulfilled',
      payment_status: 'partial',
      grand_total: '24.00',
    }],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SalesOrders page', () => {
  it('shows order and payment badges and requests the selected filters', async () => {
    render(
      <MemoryRouter>
        <SalesOrders />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'SO-2026-000001' })).toHaveAttribute(
      'href',
      '/sales-orders/order-1',
    )
    expect(screen.getByText('fulfilled', { selector: 'span.badge' })).toBeInTheDocument()
    expect(screen.getByText('partial', { selector: 'span.badge' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Payment status'), {
      target: { value: 'partial' },
    })

    await waitFor(() => {
      expect(listSalesOrdersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ payment_status: 'partial' }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })
  })

  it('lets fulfil-only sales readers browse orders without requiring customer access', async () => {
    authState.permissions = ['sales:read', 'sales:fulfil']
    render(
      <MemoryRouter>
        <SalesOrders />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'SO-2026-000001' })).toBeInTheDocument()
    expect(listCustomersMock).not.toHaveBeenCalled()
    expect(screen.queryByLabelText('Customer')).toBeNull()
  })
})
