import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Users from './Users.jsx'

const {
  authState,
  listUsersMock,
  listEmployeesMock,
  createUserMock,
  updateUserMock,
  activateUserMock,
  deactivateUserMock,
  resetUserPasswordMock,
  showToastMock,
} = vi.hoisted(() => ({
  authState: { id: 'admin-1', permissions: ['users:manage'] },
  listUsersMock: vi.fn(),
  listEmployeesMock: vi.fn(),
  createUserMock: vi.fn(),
  updateUserMock: vi.fn(),
  activateUserMock: vi.fn(),
  deactivateUserMock: vi.fn(),
  resetUserPasswordMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({ user: authState }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/userService.js', () => ({
  listUsers: listUsersMock,
  createUser: createUserMock,
  updateUser: updateUserMock,
  activateUser: activateUserMock,
  deactivateUser: deactivateUserMock,
  resetUserPassword: resetUserPasswordMock,
}))

vi.mock('../services/employeeService.js', () => ({
  listEmployees: listEmployeesMock,
}))

const account = {
  id: 'user-2',
  email: 'alex@example.com',
  full_name: 'Alex Example',
  role: 'employee',
  employee_id: null,
  is_active: true,
}

beforeEach(() => {
  listUsersMock.mockResolvedValue({
    items: [account],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  listEmployeesMock.mockResolvedValue({
    items: [{
      id: 'employee-1',
      first_name: 'Ada',
      last_name: 'Lovelace',
      employee_code: 'EMP-01',
    }],
    meta: { page: 1, page_size: 100, total: 1, total_pages: 1 },
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderPage() {
  return render(
    <MemoryRouter>
      <Users />
    </MemoryRouter>,
  )
}

describe('Users page', () => {
  it('loads accounts and applies role and active filters through the service', async () => {
    renderPage()

    expect(await screen.findByText('alex@example.com')).toBeInTheDocument()
    fireEvent.change(screen.getByRole('combobox', { name: 'Filter users by role' }), {
      target: { value: 'employee' },
    })
    fireEvent.change(
      screen.getByRole('combobox', { name: 'Filter users by active status' }),
      { target: { value: 'false' } },
    )

    await waitFor(() => {
      expect(listUsersMock).toHaveBeenLastCalledWith(
        expect.objectContaining({ role: 'employee', is_active: false }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      )
    })
  })

  it('confirms account deactivation and sends the API request', async () => {
    deactivateUserMock.mockResolvedValue({ ...account, is_active: false })
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Deactivate Alex Example' }))
    expect(screen.getByText(/They will lose access immediately/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Deactivate account' }))

    await waitFor(() => expect(deactivateUserMock).toHaveBeenCalledWith('user-2'))
  })

  it('confirms account activation and sends the API request', async () => {
    const inactiveAccount = { ...account, is_active: false }
    listUsersMock.mockResolvedValueOnce({
      items: [inactiveAccount],
      meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
    })
    activateUserMock.mockResolvedValue(account)
    renderPage()

    fireEvent.click(await screen.findByRole('button', { name: 'Activate Alex Example' }))
    expect(screen.getByText("Activate Alex Example's account?")).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Activate account' }))

    await waitFor(() => expect(activateUserMock).toHaveBeenCalledWith('user-2'))
  })

  it('confirms and requests an administrator password reset', async () => {
    resetUserPasswordMock.mockResolvedValue({ message: 'A reset link was generated.' })
    renderPage()

    fireEvent.click(await screen.findByRole('button', {
      name: 'Reset password for Alex Example',
    }))
    fireEvent.click(screen.getByRole('button', { name: 'Generate reset link' }))

    await waitFor(() => expect(resetUserPasswordMock).toHaveBeenCalledWith('user-2'))
  })

  it('shows the optional employee link in the create-user modal', async () => {
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Create user' }))

    expect(await screen.findByRole('option', {
      name: 'Ada Lovelace (EMP-01)',
    })).toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: 'Role' })).toBeInTheDocument()
  })

  it('creates a user with the selected role and optional employee link', async () => {
    createUserMock.mockResolvedValue({ id: 'user-3' })
    renderPage()
    fireEvent.click(screen.getByRole('button', { name: 'Create user' }))
    await screen.findByRole('option', { name: 'Ada Lovelace (EMP-01)' })

    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: '  new@example.com ' },
    })
    fireEvent.change(screen.getByLabelText('Full name'), {
      target: { value: ' New User ' },
    })
    fireEvent.change(screen.getByLabelText('Temporary password'), {
      target: { value: 'UniqueBluePassword771!' },
    })
    fireEvent.change(screen.getByRole('combobox', { name: 'Role' }), {
      target: { value: 'hr_manager' },
    })
    fireEvent.change(screen.getByLabelText('Employee link (optional)'), {
      target: { value: 'employee-1' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Create user' }).at(-1))

    await waitFor(() =>
      expect(createUserMock).toHaveBeenCalledWith({
        email: 'new@example.com',
        full_name: 'New User',
        role: 'hr_manager',
        employee_id: 'employee-1',
        password: 'UniqueBluePassword771!',
      }),
    )
  })
})
