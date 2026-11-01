import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Purchases from './Purchases.jsx'

const { authState, listPurchaseOrdersMock, listSuppliersMock } = vi.hoisted(() => ({
  authState: { permissions: ['purchase:read', 'purchase:create'] },
  listPurchaseOrdersMock: vi.fn(),
  listSuppliersMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../services/purchaseOrderService.js', () => ({
  listPurchaseOrders: listPurchaseOrdersMock,
}))

vi.mock('../services/supplierService.js', () => ({
  listSuppliers: listSuppliersMock,
}))

beforeEach(() => {
  listPurchaseOrdersMock.mockResolvedValue({
    items: [],
    meta: { page: 1, page_size: 20, total: 0, total_pages: 0 },
  })
  listSuppliersMock.mockResolvedValue({
    items: [{ id: 'supplier-1', name: 'Northwind' }],
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Purchases page', () => {
  it('sends status, supplier, and creation-date filters to the API list service', async () => {
    render(
      <MemoryRouter>
        <Purchases />
      </MemoryRouter>,
    )

    await screen.findByRole('option', { name: 'Northwind' })
    fireEvent.change(screen.getByLabelText('Filter purchase orders by status'), {
      target: { value: 'draft' },
    })
    fireEvent.change(screen.getByLabelText('Filter purchase orders by supplier'), {
      target: { value: 'supplier-1' },
    })
    fireEvent.change(screen.getByLabelText('Created from'), {
      target: { value: '2026-03-01' },
    })
    fireEvent.change(screen.getByLabelText('Created to'), {
      target: { value: '2026-03-31' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply dates' }))

    await waitFor(() =>
      expect(listPurchaseOrdersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({
          status: 'draft',
          supplier_id: 'supplier-1',
          start_date: '2026-03-01T00:00:00Z',
          end_date: '2026-03-31T23:59:59.999Z',
        }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
    expect(screen.getByRole('button', { name: 'Create purchase order' })).toBeInTheDocument()
  })

  it('rejects reversed date ranges before updating filters', async () => {
    render(
      <MemoryRouter>
        <Purchases />
      </MemoryRouter>,
    )
    await screen.findByRole('button', { name: 'Apply dates' })
    fireEvent.change(screen.getByLabelText('Created from'), {
      target: { value: '2026-03-31' },
    })
    fireEvent.change(screen.getByLabelText('Created to'), {
      target: { value: '2026-03-01' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Apply dates' }))

    expect(
      await screen.findByText('End date must be on or after the start date.'),
    ).toBeInTheDocument()
  })
})
