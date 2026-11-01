import { cleanup, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import SupplierDetail from './SupplierDetail.jsx'

const { getSupplierMock, listSupplierPurchaseOrdersMock } = vi.hoisted(() => ({
  getSupplierMock: vi.fn(),
  listSupplierPurchaseOrdersMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ hasPermission: () => true }),
}))

vi.mock('../services/supplierService.js', () => ({
  getSupplier: getSupplierMock,
  listSupplierPurchaseOrders: listSupplierPurchaseOrdersMock,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('SupplierDetail', () => {
  it('shows supplier contact details, outstanding POs, and purchase history', async () => {
    getSupplierMock.mockResolvedValue({
      id: 'supplier-1',
      code: 'SUP-1',
      name: 'Northwind',
      contact_person: 'Ada',
      email: 'orders@example.com',
      phone: '+1234567890',
      status: 'active',
      address: {
        line1: '1 Market Street',
        city: 'London',
        country: 'UK',
      },
    })
    listSupplierPurchaseOrdersMock.mockResolvedValue({
      items: [
        {
          id: 'po-1',
          po_number: 'PO-2026-000001',
          created_at: '2026-01-01T00:00:00Z',
          status: 'received',
          grand_total: '125.00',
        },
      ],
      outstanding: [
        {
          id: 'po-2',
          po_number: 'PO-2026-000002',
          created_at: '2026-02-01T00:00:00Z',
          status: 'approved',
          grand_total: '250.00',
        },
      ],
      meta: {
        purchase_orders: { page: 1, page_size: 20, total: 1, total_pages: 1 },
        outstanding_purchase_orders: {
          page: 1,
          page_size: 20,
          total: 1,
          total_pages: 1,
        },
      },
    })

    render(
      <MemoryRouter initialEntries={['/suppliers/supplier-1']}>
        <Routes>
          <Route path="/suppliers/:supplierId" element={<SupplierDetail />} />
        </Routes>
      </MemoryRouter>,
    )

    expect(await screen.findByRole('heading', { name: 'Northwind' })).toBeInTheDocument()
    expect(screen.getByText(/1 Market Street/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'PO-2026-000001' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'PO-2026-000002' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Outstanding orders' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Purchase history' })).toBeInTheDocument()
  })
})
