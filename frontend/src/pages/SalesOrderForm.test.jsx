import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import SalesOrderForm from './SalesOrderForm.jsx'

const { createSalesOrderMock, listCustomersMock, listProductsMock, navigateMock, showToastMock } =
  vi.hoisted(() => ({
    createSalesOrderMock: vi.fn(),
    listCustomersMock: vi.fn(),
    listProductsMock: vi.fn(),
    navigateMock: vi.fn(),
    showToastMock: vi.fn(),
  }))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('../services/customerService.js', () => ({
  listCustomers: listCustomersMock,
}))

vi.mock('../services/productService.js', () => ({
  listProducts: listProductsMock,
}))

vi.mock('../services/salesOrderService.js', () => ({
  createSalesOrder: createSalesOrderMock,
}))

beforeEach(() => {
  listCustomersMock.mockResolvedValue({
    items: [{ id: 'customer-1', code: 'CUS-1', name: 'Acme' }],
  })
  listProductsMock.mockResolvedValue({
    items: [{
      id: 'product-1',
      name: 'Desk',
      sku: 'DESK-1',
      selling_price: '12.34',
      quantity_on_hand: 8,
      reserved_quantity: 3,
    }],
  })
  createSalesOrderMock.mockResolvedValue({ id: 'order-1' })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SalesOrderForm', () => {
  it('shows available stock, previews totals, and submits no client prices or totals', async () => {
    render(
      <MemoryRouter>
        <SalesOrderForm />
      </MemoryRouter>,
    )

    fireEvent.change(await screen.findByLabelText('Customer'), {
      target: { value: 'customer-1' },
    })
    fireEvent.change(screen.getByLabelText('Product'), {
      target: { value: 'desk' },
    })
    expect(
      await screen.findByRole('option', {
        name: 'Desk (DESK-1) — 5 available',
      }),
    ).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', {
      name: 'Select product for line 1',
    }), {
      target: { value: 'product-1' },
    })
    fireEvent.change(screen.getByLabelText('Quantity'), {
      target: { value: '2' },
    })
    expect(screen.getAllByText('₹24.68')).toHaveLength(2)
    expect(screen.getByText(/Estimate only/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))

    await waitFor(() => expect(createSalesOrderMock).toHaveBeenCalledOnce())
    expect(createSalesOrderMock).toHaveBeenCalledWith({
      customer_id: 'customer-1',
      items: [{
        product_id: 'product-1',
        quantity: 2,
        discount_percent: '0.00',
        tax_percent: '0.00',
      }],
    })
    expect(createSalesOrderMock.mock.calls[0][0]).not.toHaveProperty('grand_total')
    expect(createSalesOrderMock.mock.calls[0][0].items[0]).not.toHaveProperty('unit_price')
    expect(navigateMock).toHaveBeenCalledWith('/sales-orders/order-1')
  })
})
