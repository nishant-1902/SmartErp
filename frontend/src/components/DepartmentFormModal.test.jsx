import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import DepartmentFormModal from './DepartmentFormModal.jsx'

const { listEmployeesMock, showToastMock } = vi.hoisted(() => ({
  listEmployeesMock: vi.fn(),
  showToastMock: vi.fn(),
}))

vi.mock('../services/employeeService.js', () => ({
  listEmployees: listEmployeesMock,
}))

vi.mock('../hooks/useToast.js', () => ({
  useToast: () => ({ showToast: showToastMock }),
}))

beforeEach(() => {
  listEmployeesMock.mockResolvedValue({
    items: [
      {
        id: 'manager-1',
        employee_code: 'EMP-01',
        first_name: 'Ada',
        last_name: 'Lovelace',
      },
    ],
  })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('DepartmentFormModal', () => {
  it('loads active employees as manager options and validates required fields', async () => {
    render(
      <DepartmentFormModal
        onHide={vi.fn()}
        onSave={vi.fn()}
        show
      />,
    )

    expect(await screen.findByRole('option', { name: /Ada Lovelace/ })).toBeInTheDocument()
    expect(listEmployeesMock).toHaveBeenCalledWith(
      expect.objectContaining({ status: 'active', page_size: 100 }),
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    )

    fireEvent.click(screen.getByRole('button', { name: 'Create department' }))
    expect(await screen.findByText('Department code is required.')).toBeInTheDocument()
    expect(screen.getByText('Department name is required.')).toBeInTheDocument()
  })

  it('maps a department conflict to a field error and an error toast', async () => {
    const onSave = vi.fn().mockRejectedValue({
      response: {
        status: 409,
        data: {
          success: false,
          error: {
            code: 'conflict',
            message: 'Department code already exists.',
            details: { code: 'Must be unique.' },
          },
        },
      },
    })
    render(<DepartmentFormModal onHide={vi.fn()} onSave={onSave} show />)
    await screen.findByRole('option', { name: /Ada Lovelace/ })

    fireEvent.change(screen.getByLabelText('Department code'), {
      target: { value: 'ops' },
    })
    fireEvent.change(screen.getByLabelText('Department name'), {
      target: { value: 'Operations' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Create department' }))

    await waitFor(() => expect(onSave).toHaveBeenCalledOnce())
    expect(onSave.mock.calls[0][0].code).toBe('OPS')
    expect(await screen.findByText('Department code already exists.')).toBeInTheDocument()
    expect(screen.getByText('Must be unique.')).toBeInTheDocument()
    expect(showToastMock).toHaveBeenCalledWith(
      'Department code already exists.',
      'danger',
      'Unable to save department',
    )
  })
})
