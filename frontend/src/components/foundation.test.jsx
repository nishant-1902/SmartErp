import { act, cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BrowserRouter } from 'react-router-dom'
import DashboardCard from './DashboardCard.jsx'
import DataTable from './DataTable.jsx'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import Pagination from './Pagination.jsx'
import SearchBar from './SearchBar.jsx'
import Sidebar from './Sidebar.jsx'
import { ToastProvider } from '../context/ToastContext.jsx'
import { useToast } from '../hooks/useToast.js'

const { sidebarAuth } = vi.hoisted(() => ({
  sidebarAuth: { user: { permissions: ['departments:read'] }, role: 'hr_manager' },
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: () => sidebarAuth,
}))

beforeEach(() => {
  sidebarAuth.user.permissions = ['departments:read']
  sidebarAuth.role = 'hr_manager'
})

afterEach(() => {
  cleanup()
  vi.useRealTimers()
})

describe('UI foundation components', () => {
  it('renders DataTable empty and loading states', () => {
    const columns = [{ key: 'name', label: 'Name' }]
    const { rerender } = render(<DataTable columns={columns} />)

    expect(screen.getByText('No records to display.')).toBeInTheDocument()

    rerender(<DataTable columns={columns} loading />)
    expect(screen.getByRole('status')).toBeInTheDocument()
  })

  it('sorts DataTable rows and reports the selected sort', async () => {
    const onSort = vi.fn()
    render(
      <DataTable
        columns={[{ key: 'name', label: 'Name', sortable: true }]}
        data={[{ id: 'b', name: 'Bravo' }, { id: 'a', name: 'Alpha' }]}
        onSort={onSort}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: /Name/ }))
    const rows = screen.getAllByRole('row')
    expect(rows[1]).toHaveTextContent('Alpha')
    expect(onSort).toHaveBeenCalledWith('name', 'asc')
  })

  it('debounces SearchBar and skips an initial empty search', () => {
    vi.useFakeTimers()
    const onSearch = vi.fn()
    render(<SearchBar delay={300} onSearch={onSearch} />)

    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(onSearch).not.toHaveBeenCalled()

    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: '  employee  ' },
    })
    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(onSearch).not.toHaveBeenCalled()

    act(() => {
      vi.advanceTimersByTime(1)
    })
    expect(onSearch).toHaveBeenCalledWith('employee')

    fireEvent.change(screen.getByRole('searchbox'), {
      target: { value: '' },
    })
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(onSearch).toHaveBeenLastCalledWith('')
  })

  it('connects FormInput labels and validation feedback accessibly', () => {
    render(
      <FormInput
        error={{ message: 'Email is required.' }}
        label="Email"
        name="email"
        type="email"
      />,
    )
    const input = screen.getByLabelText('Email')

    expect(input).toHaveAttribute('aria-invalid', 'true')
    expect(input).toHaveAttribute('aria-describedby', 'email-feedback')
    expect(screen.getByText('Email is required.')).toBeInTheDocument()
  })

  it('filters Sidebar navigation using the signed-in user permissions', () => {
    render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>,
    )

    expect(screen.getByRole('link', { name: /Overview/ })).toBeInTheDocument()
    expect(screen.getByText('Departments')).toBeInTheDocument()
    expect(screen.queryByText('Employees')).not.toBeInTheDocument()
  })

  it('shows account navigation only when the matching permissions are present', () => {
    sidebarAuth.role = 'super_admin'
    sidebarAuth.user.permissions = [
      'users:manage',
      'audit:read',
      'own-profile:read',
      'own-password:change',
    ]
    render(
      <BrowserRouter>
        <Sidebar />
      </BrowserRouter>,
    )

    expect(screen.getByRole('link', { name: /Users/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Audit logs/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Profile/ })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: /Settings/ })).toBeInTheDocument()
  })

  it('renders DashboardCard content and ErrorMessage accessibly', () => {
    render(
      <>
        <DashboardCard detail="Up 4%" label="Active users" value="28" />
        <ErrorMessage message="Could not load data." title="Request failed" />
      </>,
    )

    expect(screen.getByRole('region', { name: 'Active users' })).toHaveTextContent(
      '28',
    )
    expect(screen.getByRole('alert')).toHaveTextContent('Could not load data.')
  })

  it('moves to the next Pagination page', () => {
    const onPageChange = vi.fn()
    render(
      <Pagination
        onPageChange={onPageChange}
        page={1}
        pageSize={10}
        totalItems={24}
      />,
    )

    fireEvent.click(screen.getByRole('button', { name: 'Go to next page' }))
    expect(onPageChange).toHaveBeenCalledWith(2)
    expect(screen.getByText('Showing 1–10 of 24')).toBeInTheDocument()
  })

  it('shows toast messages through the provider hook', () => {
    function ToastTrigger() {
      const { showToast } = useToast()
      return (
        <button onClick={() => showToast('Saved successfully.')} type="button">
          Show toast
        </button>
      )
    }

    render(
      <ToastProvider>
        <ToastTrigger />
      </ToastProvider>,
    )
    fireEvent.click(screen.getByRole('button', { name: 'Show toast' }))

    expect(screen.getByText('Saved successfully.')).toBeInTheDocument()
  })
})
