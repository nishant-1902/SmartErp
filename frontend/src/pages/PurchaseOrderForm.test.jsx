import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import PurchaseOrderForm from './PurchaseOrderForm.jsx'

const {
  createPurchaseOrderMock,
  getPurchaseOrderMock,
  listProductsMock,
  listSuppliersMock,
  navigateMock,
  showToastMock,
  updatePurchaseOrderMock,
} = vi.hoisted(() => ({
  createPurchaseOrderMock: vi.fn(),
  getPurchaseOrderMock: vi.fn(),
  listProductsMock: vi.fn(),
  listSuppliersMock: vi.fn(),
  navigateMock: vi.fn(),
  showToastMock: vi.fn(),
  updatePurchaseOrderMock: vi.fn(),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

vi.mock('../services/purchaseOrderService.js', () => ({
  createPurchaseOrder: createPurchaseOrderMock,
  getPurchaseOrder: getPurchaseOrderMock,
  updatePurchaseOrder: updatePurchaseOrderMock,
}))

vi.mock('../services/supplierService.js', () => ({
  listSuppliers: listSuppliersMock,
}))

vi.mock('../services/productService.js', () => ({
  listProducts: listProductsMock,
}))

beforeEach(() => {
  listSuppliersMock.mockResolvedValue({
    items: [{ id: 'supplier-1', code: 'SUP-1', name: 'Northwind' }],
  })
  listProductsMock.mockResolvedValue({
    items: [
      {
        id: '0123456789abcdef01234567',
        name: 'Desk',
        sku: 'DESK-1',
        cost_price: '12.34',
      },
    ],
  })
  createPurchaseOrderMock.mockResolvedValue({ id: 'new-po' })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('PurchaseOrderForm', () => {
  it('uses searchable dynamic items and submits only server-calculated source values', async () => {
    render(
      <MemoryRouter>
        <PurchaseOrderForm />
      </MemoryRouter>,
    )

    await screen.findByRole('option', { name: 'Northwind (SUP-1)' })
    fireEvent.change(screen.getByLabelText('Supplier'), {
      target: { value: 'supplier-1' },
    })
    fireEvent.change(screen.getByLabelText('Product'), {
      target: { value: 'desk' },
    })
    await screen.findByRole('option', { name: 'Desk (DESK-1)' })
    fireEvent.change(screen.getByRole('combobox', {
      name: 'Select product for line 1',
    }), {
      target: { value: '0123456789abcdef01234567' },
    })
    expect(listProductsMock).toHaveBeenCalledWith(
      expect.objectContaining({
        page: 1,
        page_size: 20,
        search: 'desk',
        is_active: true,
      }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    fireEvent.change(screen.getByLabelText('Quantity'), {
      target: { value: '2' },
    })
    fireEvent.change(screen.getByLabelText('Tax rate (%)'), {
      target: { value: '7.50' },
    })

    expect(
      screen.getByText('Preview only. The server calculates and stores the final totals.'),
    ).toBeInTheDocument()
    expect(screen.getByText('₹24.68')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add item' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Add item' }))
    expect(screen.getByRole('button', { name: 'Remove item 2' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Remove item 2' }))
    fireEvent.click(screen.getByRole('button', { name: 'Create draft' }))

    await waitFor(() => expect(createPurchaseOrderMock).toHaveBeenCalledOnce())
    expect(createPurchaseOrderMock).toHaveBeenCalledWith({
      supplier_id: 'supplier-1',
      tax_rate: '7.50',
      items: [
        {
          product_id: '0123456789abcdef01234567',
          quantity_ordered: 2,
          unit_cost: '12.34',
        },
      ],
    })
    expect(navigateMock).toHaveBeenCalledWith('/purchase-orders/new-po')
  })
})
