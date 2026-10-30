import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { MemoryRouter } from 'react-router-dom'
import Employees from './Employees.jsx'

const { authState, listEmployeesMock, listDepartmentsMock, showToastMock } =
  vi.hoisted(() => ({
    authState: { permissions: ['employees:read'] },
    listEmployeesMock: vi.fn(),
    listDepartmentsMock: vi.fn(),
    showToastMock: vi.fn(),
  }))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => ({
    hasPermission: (permission) => authState.permissions.includes(permission),
  }),
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

vi.mock('../services/employeeService.js', () => ({
  listEmployees: listEmployeesMock,
  createEmployee: vi.fn(),
  updateEmployee: vi.fn(),
  deactivateEmployee: vi.fn(),
}))

vi.mock('../services/departmentService.js', () => ({
  listDepartments: listDepartmentsMock,
}))

const employee = {
  id: 'employee-1',
  employee_code: 'EMP-01',
  first_name: 'Ada',
  last_name: 'Lovelace',
  email: 'ada@example.com',
  department_id: 'department-1',
  designation: 'Engineer',
  joining_date: '2024-01-15T00:00:00+00:00',
  status: 'active',
}

beforeEach(() => {
  authState.permissions = ['employees:read']
  listEmployeesMock.mockResolvedValue({
    items: [employee],
    meta: { page: 1, page_size: 20, total: 1, total_pages: 1 },
  })
  listDepartmentsMock.mockResolvedValue({
    items: [{ id: 'department-1', name: 'Operations' }],
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
      <Employees />
    </MemoryRouter>,
  )
}

describe('Employees page', () => {
  it('loads employee data through the service and hides write actions without permission', async () => {
    renderPage()

    expect(
      await screen.findByRole('link', { name: 'Ada Lovelace' }),
    ).toBeInTheDocument()
    expect(listEmployeesMock).toHaveBeenCalledWith(
      expect.objectContaining({ page: 1, page_size: 20 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )
    expect(screen.queryByRole('button', { name: 'Add employee' })).toBeNull()
    expect(screen.queryByRole('button', { name: 'Edit Ada Lovelace' })).toBeNull()
  })

  it('shows employee write actions for users with employees:write', async () => {
    authState.permissions = ['employees:read', 'employees:write']
    renderPage()

    expect(
      await screen.findByRole('button', { name: 'Add employee' }),
    ).toBeInTheDocument()
    expect(
      await screen.findByRole('button', { name: 'Edit Ada Lovelace' }),
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: 'Deactivate Ada Lovelace' }),
    ).toBeInTheDocument()
  })

  it('sends sorting choices to the server using its allowlisted field names', async () => {
    renderPage()
    await screen.findByRole('link', { name: 'Ada Lovelace' })

    fireEvent.click(screen.getByRole('button', { name: /Employee/ }))

    await waitFor(() =>
      expect(listEmployeesMock).toHaveBeenCalledWith(
        expect.objectContaining({ sort_by: 'first_name', sort_order: 'asc' }),
        expect.objectContaining({ signal: expect.any(AbortSignal) }),
      ),
    )
  })

  it('displays the backend forbidden message if directory access is denied', async () => {
    listEmployeesMock.mockRejectedValue({
      response: {
        status: 403,
        data: {
          success: false,
          error: {
            code: 'permission_denied',
            message: "The 'employees:read' permission is required.",
            details: {},
          },
        },
      },
    })
    renderPage()

    await waitFor(() =>
      expect(
        screen.getByText("The 'employees:read' permission is required."),
      ).toBeInTheDocument(),
    )
  })
})
