import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Customers from './Customers.jsx'

const {
  authState,
  createCustomerMock,
  listCustomersMock,
  showToastMock,
  updateCustomerMock,
} = vi.hoisted(() => ({
  authState: { permissions: ['customers:read', 'customers:write'] },
  createCustomerMock: vi.fn(),
  listCustomersMock: vi.fn(),
  showToastMock: vi.fn(),
  updateCustomerMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/customerService.js', () => ({
  createCustomer: createCustomerMock,
  listCustomers: listCustomersMock,
  updateCustomer: updateCustomerMock,
}))

const customer = {
  id: 'customer-1',
  code: 'CUS-001',
  name: 'Acme Stores',
  email: 'accounts@example.com',
  phone: '+1234567890',
  status: 'active',
}

beforeEach(() => {
  authState.permissions = ['customers:read', 'customers:write']
  listCustomersMock.mockResolvedValue({
    items: [customer],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  createCustomerMock.mockResolvedValue(customer)
  updateCustomerMock.mockResolvedValue({ ...customer, status: 'inactive' })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('Customers page', () => {
  it('creates customers and displays their sales-history link', async () => {
    render(
      <MemoryRouter>
        <Customers />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'Acme Stores' })).toHaveAttribute(
      'href',
      '/customers/customer-1',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Add customer' }))
    fireEvent.change(screen.getByLabelText('Customer code'), {
      target: { value: 'cus-002' },
    })
    fireEvent.change(screen.getByLabelText('Customer name'), {
      target: { value: 'New Customer' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create customer' }))

    await waitFor(() => expect(createCustomerMock).toHaveBeenCalledOnce())
    expect(createCustomerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        code: 'CUS-002',
        name: 'New Customer',
        status: 'active',
      }),
    )
  })

  it('hides write actions without the customer write permission', async () => {
    authState.permissions = ['customers:read']
    render(
      <MemoryRouter>
        <Customers />
      </MemoryRouter>,
    )

    expect(await screen.findByRole('link', { name: 'Acme Stores' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add customer' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit Acme Stores' })).toBeNull()
  })
})
