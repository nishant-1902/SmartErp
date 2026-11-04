import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import SalesOrderDetail from './SalesOrderDetail.jsx'

const {
  fulfilSalesOrderMock,
  getSalesOrderMock,
  recordSalesOrderPaymentMock,
  returnSalesOrderItemsMock,
  showToastMock,
  transitionSalesOrderMock,
} = vi.hoisted(() => ({
  fulfilSalesOrderMock: vi.fn(),
  getSalesOrderMock: vi.fn(),
  recordSalesOrderPaymentMock: vi.fn(),
  returnSalesOrderItemsMock: vi.fn(),
  showToastMock: vi.fn(),
  transitionSalesOrderMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => [
      'sales:confirm',
      'sales:fulfil',
      'sales:cancel',
      'payments:record',
      'returns:process',
      'invoices:read',
    ].includes(permission),
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/invoiceService.js', () => ({
  listInvoices: vi.fn().mockResolvedValue({ items: [] }),
}))

vi.mock('../services/salesOrderService.js', () => ({
  fulfilSalesOrder: fulfilSalesOrderMock,
  getSalesOrder: getSalesOrderMock,
  recordSalesOrderPayment: recordSalesOrderPaymentMock,
  returnSalesOrderItems: returnSalesOrderItemsMock,
  transitionSalesOrder: transitionSalesOrderMock,
}))

function makeOrder(status) {
  return {
    id: 'order-1',
    order_number: 'SO-2026-000001',
    status,
    payment_status: 'unpaid',
    return_status: 'none',
    customer_snapshot: { name: 'Acme Stores' },
    created_at: '2026-01-02T00:00:00Z',
    items: [{
      product_id: 'product-1',
      sku: 'DESK-1',
      name: 'Desk',
      quantity: 2,
      returned_quantity: 0,
      unit_price: '12.00',
      discount_percent: '0.00',
      line_tax: '0.00',
      line_total: '24.00',
    }],
    subtotal: '24.00',
    discount_total: '0.00',
    tax_total: '0.00',
    grand_total: '24.00',
    paid_total: '0.00',
    status_history: [{
      status,
      at: '2026-01-02T00:00:00Z',
      by: 'user-1',
    }],
  }
}

function renderOrder() {
  return render(
    <MemoryRouter initialEntries={['/sales-orders/order-1']}>
      <Routes>
        <Route path="/sales-orders/:salesOrderId" element={<SalesOrderDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  vi.stubGlobal('crypto', { randomUUID: () => 'workflow-key' })
  getSalesOrderMock.mockResolvedValue(makeOrder('confirmed'))
  fulfilSalesOrderMock.mockResolvedValue({
    sales_order: makeOrder('fulfilled'),
    invoice: { id: 'invoice-1' },
  })
  recordSalesOrderPaymentMock.mockResolvedValue({
    sales_order: { ...makeOrder('fulfilled'), paid_total: '10.00' },
  })
  returnSalesOrderItemsMock.mockResolvedValue({
    sales_order: { ...makeOrder('fulfilled'), return_status: 'partial' },
    sales_return: { credit_note_number: 'CN-2026-000001' },
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('SalesOrderDetail page', () => {
  it('fulfils confirmed orders with an idempotency key and links to the invoice', async () => {
    renderOrder()
    fireEvent.click(await screen.findByRole('button', { name: 'Fulfil' }))

    await waitFor(() => {
      expect(fulfilSalesOrderMock).toHaveBeenCalledWith('order-1', 'workflow-key')
    })
    expect(await screen.findByRole('link', { name: 'View invoice' })).toHaveAttribute(
      'href',
      '/invoices/invoice-1',
    )
    expect(screen.getByText('fulfilled', { selector: 'span.badge' })).toBeInTheDocument()
  })

  it('records a payment using the retry-stable idempotency key', async () => {
    getSalesOrderMock.mockResolvedValue({
      ...makeOrder('fulfilled'),
      payment_status: 'partial',
      paid_total: '10.00',
    })
    renderOrder()
    fireEvent.click(await screen.findByRole('button', { name: 'Record payment' }))
    fireEvent.change(await screen.findByLabelText('Amount'), {
      target: { value: '5.00' },
    })
    const paymentButtons = screen.getAllByRole('button', { name: 'Record payment' })
    fireEvent.click(paymentButtons[paymentButtons.length - 1])

    await waitFor(() => {
      expect(recordSalesOrderPaymentMock).toHaveBeenCalledWith(
        'order-1',
        { amount: '5.00', method: 'cash' },
        'workflow-key',
      )
    })
  })

  it('submits a return quantity and reason from the return modal', async () => {
    getSalesOrderMock.mockResolvedValue(makeOrder('fulfilled'))
    renderOrder()
    fireEvent.click(await screen.findByRole('button', { name: 'Process return' }))
    fireEvent.change(await screen.findByLabelText('Desk (DESK-1) — 2 returnable'), {
      target: { value: '1' },
    })
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Customer changed their mind' },
    })
    const returnButtons = screen.getAllByRole('button', { name: 'Process return' })
    fireEvent.click(returnButtons[returnButtons.length - 1])

    await waitFor(() => {
      expect(returnSalesOrderItemsMock).toHaveBeenCalledWith(
        'order-1',
        {
          items: [{ product_id: 'product-1', quantity: 1 }],
          reason: 'Customer changed their mind',
        },
      )
    })
  })
})
