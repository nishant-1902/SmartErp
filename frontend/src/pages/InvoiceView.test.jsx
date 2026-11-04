import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import InvoiceView from './InvoiceView.jsx'

const { getInvoiceMock } = vi.hoisted(() => ({
  getInvoiceMock: vi.fn(),
}))

vi.mock('../services/invoiceService.js', () => ({
  getInvoice: getInvoiceMock,
}))

beforeEach(() => {
  getInvoiceMock.mockResolvedValue({
    id: 'invoice-1',
    invoice_number: 'INV-2026-000001',
    sales_order_id: 'order-1',
    issued_at: '2026-01-02T00:00:00Z',
    due_date: '2026-02-01T00:00:00Z',
    customer_snapshot: {
      name: 'Acme Stores',
      email: 'accounts@example.com',
      billing_address: { line1: '12 Market Street', city: 'Springfield', country: 'US' },
    },
    items: [{
      product_id: 'product-1',
      sku: 'DESK-1',
      name: 'Desk',
      quantity: 2,
      unit_price: '12.00',
      discount_percent: '0.00',
      line_tax: '0.00',
      line_total: '24.00',
    }],
    subtotal: '24.00',
    discount_total: '0.00',
    tax_total: '0.00',
    grand_total: '24.00',
  })
})

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

describe('InvoiceView page', () => {
  it('renders the saved invoice snapshot and invokes the browser print dialog', async () => {
    const print = vi.spyOn(window, 'print').mockImplementation(() => {})
    render(
      <MemoryRouter initialEntries={['/invoices/invoice-1']}>
        <Routes>
          <Route path="/invoices/:invoiceId" element={<InvoiceView />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Invoice' })).toBeInTheDocument()
    expect(screen.getByText('INV-2026-000001')).toBeInTheDocument()
    expect(screen.getByText('Acme Stores')).toBeInTheDocument()
    expect(screen.getByText('12 Market Street')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Print invoice' }))

    expect(print).toHaveBeenCalledOnce()
  })
})
