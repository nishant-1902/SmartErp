import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import PurchaseOrderDetail from './PurchaseOrderDetail.jsx'

const {
  authState,
  getPurchaseOrderMock,
  receivePurchaseOrderMock,
  showToastMock,
  transitionPurchaseOrderMock,
} = vi.hoisted(() => ({
  authState: {
    user: { id: 'user-1' },
    role: 'purchase_manager',
    permissions: ['purchase:read', 'purchase:approve', 'purchase:receive'],
  },
  getPurchaseOrderMock: vi.fn(),
  receivePurchaseOrderMock: vi.fn(),
  showToastMock: vi.fn(),
  transitionPurchaseOrderMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    user: authState.user,
    role: authState.role,
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/purchaseOrderService.js', () => ({
  getPurchaseOrder: getPurchaseOrderMock,
  receivePurchaseOrder: receivePurchaseOrderMock,
  transitionPurchaseOrder: transitionPurchaseOrderMock,
}))

const order = {
  id: 'po-1',
  po_number: 'PO-2026-000001',
  supplier_snapshot: { name: 'Northwind' },
  created_by: 'user-1',
  status: 'approved',
  created_at: '2026-01-01T00:00:00Z',
  items: [
    {
      product_id: 'product-1',
      sku: 'DESK-1',
      name: 'Desk',
      quantity_ordered: 4,
      quantity_received: 0,
      unit_cost: '25.00',
      line_total: '100.00',
    },
  ],
  subtotal: '100.00',
  tax_rate: '0.00',
  tax_total: '0.00',
  grand_total: '100.00',
  status_history: [
    { status: 'draft', by: 'user-1', at: '2026-01-01T00:00:00Z' },
    { status: 'approved', by: 'manager-2', at: '2026-01-02T00:00:00Z' },
  ],
}

beforeEach(() => {
  authState.user = { id: 'user-1' }
  authState.role = 'purchase_manager'
  authState.permissions = ['purchase:read', 'purchase:approve', 'purchase:receive']
  getPurchaseOrderMock
    .mockResolvedValueOnce(order)
    .mockResolvedValue({ ...order, status: 'received' })
  receivePurchaseOrderMock.mockResolvedValue({
    receipt_reference: 'RCPT-2026-000001',
  })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe('PurchaseOrderDetail', () => {
  it('hides self-approval but allows receiving with a generated idempotency key', async () => {
    vi.stubGlobal('crypto', {
      randomUUID: vi.fn().mockReturnValue('receive-uuid'),
    })
    render(
      <MemoryRouter initialEntries={['/purchase-orders/po-1']}>
        <Routes>
          <Route path="/purchase-orders/:purchaseOrderId" element={<PurchaseOrderDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'PO-2026-000001' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Approve' })).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: 'Receive' }))
    fireEvent.change(screen.getByLabelText('Receive quantity for Desk'), {
      target: { value: '4' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Record receipt' }))

    await waitFor(() =>
      expect(receivePurchaseOrderMock).toHaveBeenCalledWith(
        'po-1',
        { items: [{ product_id: 'product-1', quantity_received: 4 }] },
        'receive-uuid',
      ),
    )
    await waitFor(() =>
      expect(showToastMock).toHaveBeenCalledWith(
        'Receipt RCPT-2026-000001 recorded.',
      ),
    )
  })

  it('requires and submits a rejection reason', async () => {
    const pendingOrder = {
      ...order,
      status: 'pending_approval',
      created_by: 'creator-2',
    }
    authState.user = { id: 'user-1' }
    authState.permissions = ['purchase:read', 'purchase:reject']
    getPurchaseOrderMock.mockReset().mockResolvedValue(pendingOrder)
    transitionPurchaseOrderMock.mockResolvedValue({
      ...pendingOrder,
      status: 'rejected',
    })

    render(
      <MemoryRouter initialEntries={['/purchase-orders/po-1']}>
        <Routes>
          <Route path="/purchase-orders/:purchaseOrderId" element={<PurchaseOrderDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('button', { name: 'Reject' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Reject' }))
    fireEvent.click(screen.getByRole('button', { name: 'Reject order' }))
    expect(await screen.findByText('A rejection reason is required.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Supplier quote was not accepted.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Reject order' }))

    await waitFor(() =>
      expect(transitionPurchaseOrderMock).toHaveBeenCalledWith(
        'po-1',
        'reject',
        { reason: 'Supplier quote was not accepted.' },
      ),
    )
  })
})
