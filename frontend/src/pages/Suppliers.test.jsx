import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Suppliers from './Suppliers.jsx'

const { authState, createSupplierMock, listSuppliersMock, showToastMock, updateSupplierMock } =
  vi.hoisted(() => ({
    authState: { permissions: ['suppliers:read', 'suppliers:write'] },
    createSupplierMock: vi.fn(),
    listSuppliersMock: vi.fn(),
    showToastMock: vi.fn(),
    updateSupplierMock: vi.fn(),
  }))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/supplierService.js', () => ({
  createSupplier: createSupplierMock,
  listSuppliers: listSuppliersMock,
  updateSupplier: updateSupplierMock,
}))

const supplier = {
  id: 'supplier-1',
  code: 'SUP-1',
  name: 'Northwind',
  contact_person: 'Ada',
  email: 'orders@example.com',
  status: 'active',
}

beforeEach(() => {
  authState.permissions = ['suppliers:read', 'suppliers:write']
  listSuppliersMock.mockResolvedValue({
    items: [supplier],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  createSupplierMock.mockResolvedValue(supplier)
  updateSupplierMock.mockResolvedValue({ ...supplier, status: 'inactive' })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <Suppliers />
    </MemoryRouter>,
  )
}

describe('Suppliers page', () => {
  it('creates suppliers and exposes status in the edit form', async () => {
    renderPage()

    expect(await screen.findByRole('link', { name: 'Northwind' })).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Add supplier' }))
    fireEvent.change(screen.getByLabelText('Supplier name'), {
      target: { value: 'Acme Parts' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create supplier' }))

    await waitFor(() => expect(createSupplierMock).toHaveBeenCalledOnce())
    expect(createSupplierMock).toHaveBeenCalledWith(
      expect.objectContaining({ name: 'Acme Parts', status: 'active' }),
    )
    expect(createSupplierMock.mock.calls[0][0]).not.toHaveProperty('code')
    expect(listSuppliersMock).toHaveBeenCalledTimes(2)
    expect(showToastMock).toHaveBeenCalledWith('Supplier created successfully.')
  })

  it('updates supplier status through the edit modal', async () => {
    renderPage()

    await screen.findByRole('link', { name: 'Northwind' })
    fireEvent.click(screen.getByRole('button', { name: 'Edit Northwind' }))
    fireEvent.change(screen.getByLabelText('Status'), {
      target: { value: 'inactive' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))

    await waitFor(() =>
      expect(updateSupplierMock).toHaveBeenCalledWith(
        'supplier-1',
        expect.objectContaining({ status: 'inactive' }),
      ),
    )
  })

  it('hides supplier write actions without the write permission', async () => {
    authState.permissions = ['suppliers:read']
    renderPage()

    expect(await screen.findByRole('link', { name: 'Northwind' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add supplier' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit Northwind' })).toBeNull()
  })
})
