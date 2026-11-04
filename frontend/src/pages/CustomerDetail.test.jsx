import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import CustomerDetail from './CustomerDetail.jsx'

const { getCustomerMock, listCustomerSalesOrdersMock } = vi.hoisted(() => ({
  getCustomerMock: vi.fn(),
  listCustomerSalesOrdersMock: vi.fn(),
}))

vi.mock('../services/customerService.js', () => ({
  getCustomer: getCustomerMock,
  listCustomerSalesOrders: listCustomerSalesOrdersMock,
}))

beforeEach(() => {
  getCustomerMock.mockResolvedValue({
    id: 'customer-1',
    code: 'CUS-1',
    name: 'Acme Stores',
    email: 'accounts@example.com',
    phone: '555-0100',
    status: 'active',
    billing_address: {
      line1: '12 Market Street',
      city: 'Springfield',
      country: 'US',
    },
  })
  listCustomerSalesOrdersMock.mockResolvedValue({
    items: [{
      id: 'order-1',
      order_number: 'SO-2026-000001',
      created_at: '2026-01-02T00:00:00Z',
      status: 'fulfilled',
      payment_status: 'paid',
      grand_total: '24.00',
    }],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('CustomerDetail page', () => {
  it('loads customer details and links to the customer sales history', async () => {
    render(
      <MemoryRouter initialEntries={['/customers/customer-1']}>
        <Routes>
          <Route path="/customers/:customerId" element={<CustomerDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Acme Stores' })).toBeInTheDocument()
    expect(screen.getByText('12 Market Street', { exact: false })).toBeInTheDocument()
    expect(await screen.findByRole('link', { name: 'SO-2026-000001' })).toHaveAttribute(
      'href',
      '/sales-orders/order-1',
    )
    expect(listCustomerSalesOrdersMock).toHaveBeenCalledWith(
      'customer-1',
      expect.objectContaining({ page: 1, page_size: 20 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
  })
})
