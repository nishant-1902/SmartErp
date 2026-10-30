import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import EmployeeFormModal from './EmployeeFormModal.jsx'

const { listDepartmentsMock, listDesignationsMock, showToastMock } = vi.hoisted(() => ({
  listDepartmentsMock: vi.fn(),
  listDesignationsMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../services/departmentService.js', () => ({
  listDepartments: listDepartmentsMock,
}))

vi.mock('../services/employeeService.js', () => ({
  listDesignations: listDesignationsMock,
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

beforeEach(() => {
  listDepartmentsMock.mockResolvedValue({
    items: [{ id: 'department-1', code: 'OPS', name: 'Operations' }],
  })
  listDesignationsMock.mockResolvedValue(['Engineer'])
})

afterEach(() => {
  cleanup()
})

describe('EmployeeFormModal', () => {
  it('validates required employee fields using accessible form errors', async () => {
    render(
      <EmployeeFormModal
        onHide={vi.fn()}
        onSave={vi.fn()}
        show
      />,
    )
    await screen.findByLabelText('Employee code')

    fireEvent.click(screen.getAllByRole('button', { name: 'Create employee' })[0])

    expect(await screen.findByText('Employee code is required.')).toBeInTheDocument()
    expect(screen.getByText('First name is required.')).toBeInTheDocument()
    expect(screen.getByText('Joining date is required.')).toBeInTheDocument()
  })

  it('maps a backend duplicate conflict to both a message and field validation', async () => {
    const onSave = vi.fn().mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: {
            code: 'conflict',
            message: 'Employee email already exists.',
            details: { email: 'Must be unique.' },
          },
        },
      },
    })
    render(<EmployeeFormModal onHide={vi.fn()} onSave={onSave} show />)
    await screen.findByLabelText('Employee code')

    fireEvent.change(screen.getByLabelText('Employee code'), {
      target: { value: 'emp-002' },
    })
    fireEvent.change(screen.getByLabelText('First name'), {
      target: { value: 'Grace' },
    })
    fireEvent.change(screen.getByLabelText('Last name'), {
      target: { value: 'Hopper' },
    })
    fireEvent.change(screen.getByLabelText('Email'), {
      target: { value: 'grace@example.com' },
    })
    fireEvent.change(screen.getByLabelText('Department'), {
      target: { value: 'department-1' },
    })
    fireEvent.change(screen.getByLabelText('Designation'), {
      target: { value: 'Engineer' },
    })
    fireEvent.change(screen.getByLabelText('Joining date'), {
      target: { value: '2024-01-15' },
    })
    fireEvent.click(screen.getAllByRole('button', { name: 'Create employee' })[0])

    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    expect(onSave.mock.calls[0][0].employee_code).toBe('EMP-002')
    expect(onSave.mock.calls[0][0].email).toBe('grace@example.com')
    expect(await screen.findByText('Employee email already exists.')).toBeInTheDocument()
    expect(screen.getByText('Must be unique.')).toBeInTheDocument()
  })
})
