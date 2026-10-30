import { useCallback, useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import DataTable from '../components/DataTable.jsx'
import EmployeeFormModal from '../components/EmployeeFormModal.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SearchBar from '../components/SearchBar.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import { listDepartments } from '../services/departmentService.js'
import {
  createEmployee,
  deactivateEmployee,
  listEmployees,
  updateEmployee,
} from '../services/employeeService.js'
import { getApiError } from '../utils/apiErrors.js'

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

/**
 * Lists employees with backend search, filtering, sorting, and pagination.
 *
 * @returns {JSX.Element}
 */
export default function Employees() {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('employees:write')
  const { showToast } = useToast()
  const [departments, setDepartments] = useState([])
  const [departmentsError, setDepartmentsError] = useState(null)
  const [editingEmployee, setEditingEmployee] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [deactivatingEmployee, setDeactivatingEmployee] = useState(null)
  const [deactivating, setDeactivating] = useState(false)
  const list = usePaginatedList(listEmployees)

  useEffect(() => {
    const controller = new AbortController()
    listDepartments(
      { page: 1, page_size: 100, sort_by: 'name' },
      { signal: controller.signal },
    )
      .then(({ items }) => setDepartments(items))
      .catch((error) => {
        if (!controller.signal.aborted) setDepartmentsError(error)
      })
    return () => controller.abort()
  }, [])

  const closeForm = useCallback(() => {
    setShowForm(false)
    setEditingEmployee(null)
  }, [])

  function openCreateForm() {
    setEditingEmployee(null)
    setShowForm(true)
  }

  function openEditForm(employee) {
    setEditingEmployee(employee)
    setShowForm(true)
  }

  async function saveEmployee(values) {
    if (editingEmployee) {
      await updateEmployee(editingEmployee.id, values)
      showToast('Employee updated successfully.')
    } else {
      await createEmployee(values)
      showToast('Employee created successfully.')
    }
    closeForm()
    list.refresh()
  }

  async function confirmDeactivation() {
    if (!deactivatingEmployee) return
    setDeactivating(true)
    try {
      await deactivateEmployee(deactivatingEmployee.id)
      showToast(`${deactivatingEmployee.first_name} ${deactivatingEmployee.last_name} was deactivated.`)
      setDeactivatingEmployee(null)
      list.refresh()
    } catch (error) {
      showToast(getApiError(error).message, 'danger', 'Unable to deactivate')
    } finally {
      setDeactivating(false)
    }
  }

  const departmentNames = new Map(
    departments.map((department) => [department.id, department.name]),
  )
  const columns = [
    { key: 'employee_code', label: 'Code', sortable: true },
    {
      key: 'name',
      label: 'Employee',
      sortable: true,
      sortBy: 'first_name',
      sortValue: (employee) => employee.first_name,
      render: (employee) => (
        <Link to={`/employees/${employee.id}`}>
          {employee.first_name} {employee.last_name}
        </Link>
      ),
    },
    { key: 'email', label: 'Email', sortable: true },
    {
      key: 'department_id',
      label: 'Department',
      sortable: true,
      render: (employee) =>
        departmentNames.get(employee.department_id) ?? '—',
    },
    { key: 'designation', label: 'Designation', sortable: true },
    {
      key: 'joining_date',
      label: 'Joined',
      sortable: true,
      render: (employee) => formatDate(employee.joining_date),
    },
    {
      key: 'status',
      label: 'Status',
      sortable: true,
      render: (employee) => (
        <span
          className={`badge ${
            employee.status === 'active'
              ? 'text-bg-success'
              : employee.status === 'on_leave'
                ? 'text-bg-warning'
                : 'text-bg-secondary'
          }`}
        >
          {employee.status === 'on_leave' ? 'On leave' : employee.status}
        </span>
      ),
    },
    ...(canWrite
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (employee) => (
              <div className="d-flex gap-2">
                <Button
                  aria-label={`Edit ${employee.first_name} ${employee.last_name}`}
                  onClick={() => openEditForm(employee)}
                  size="sm"
                  variant="outline-primary"
                >
                  Edit
                </Button>
                {employee.status !== 'inactive' && (
                  <Button
                    aria-label={`Deactivate ${employee.first_name} ${employee.last_name}`}
                    onClick={() => setDeactivatingEmployee(employee)}
                    size="sm"
                    variant="outline-danger"
                  >
                    Deactivate
                  </Button>
                )}
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">People</p>
          <h1>Employees</h1>
          <p className="mb-0">Search and manage employee records.</p>
        </div>
        {canWrite && (
          <Button onClick={openCreateForm} variant="primary">
            Add employee
          </Button>
        )}
      </div>

      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-6">
          <SearchBar
            delay={0}
            label="Search employees"
            onSearch={list.setSearchInput}
            placeholder="Search name, email or employee code"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter by department"
            onChange={(event) => list.setFilter('department_id', event.target.value)}
            value={list.filters?.department_id ?? ''}
          >
            <option value="">All departments</option>
            {departments.map((department) => (
              <option key={department.id} value={department.id}>
                {department.name}
              </option>
            ))}
          </Form.Select>
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter by status"
            onChange={(event) => list.setFilter('status', event.target.value)}
            value={list.filters?.status ?? ''}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
            <option value="on_leave">On leave</option>
          </Form.Select>
        </div>
      </div>

      {departmentsError && (
        <ErrorMessage message={getApiError(departmentsError).message} />
      )}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No employees match your search and filters."
        loading={list.loading}
        onSort={list.setSorting}
        serverSideSorting
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />

      {canWrite && showForm && (
        <>
          <EmployeeFormModal
            employee={editingEmployee}
            onHide={closeForm}
            onSave={saveEmployee}
            show={showForm}
          />
          <ConfirmDialog
            busy={deactivating}
            confirmLabel="Deactivate employee"
            message={
              <>
                Deactivate{' '}
                <strong>
                  {deactivatingEmployee?.first_name}{' '}
                  {deactivatingEmployee?.last_name}
                </strong>
                ? The employee record will be kept.
              </>
            }
            onCancel={() => setDeactivatingEmployee(null)}
            onConfirm={confirmDeactivation}
            show={Boolean(deactivatingEmployee)}
            title="Deactivate employee"
          />
        </>
      )}
    </section>
  )
}
