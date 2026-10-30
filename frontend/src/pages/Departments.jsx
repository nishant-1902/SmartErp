import { useEffect, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import DepartmentEmployeesModal from '../components/DepartmentEmployeesModal.jsx'
import DepartmentFormModal from '../components/DepartmentFormModal.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SearchBar from '../components/SearchBar.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import { listDepartments } from '../services/departmentService.js'
import { listEmployees } from '../services/employeeService.js'
import { createDepartment, updateDepartment } from '../services/departmentService.js'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Lists and manages departments, including their assigned employee lists.
 *
 * @returns {JSX.Element}
 */
export default function Departments() {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('departments:write')
  const { showToast } = useToast()
  const [managers, setManagers] = useState([])
  const [managersError, setManagersError] = useState(null)
  const [editingDepartment, setEditingDepartment] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [viewingDepartment, setViewingDepartment] = useState(null)
  const list = usePaginatedList(listDepartments)

  useEffect(() => {
    const controller = new AbortController()
    listEmployees(
      { page: 1, page_size: 100, status: 'active', sort_by: 'first_name' },
      { signal: controller.signal },
    )
      .then(({ items }) => setManagers(items))
      .catch((error) => {
        if (!controller.signal.aborted) setManagersError(error)
      })
    return () => controller.abort()
  }, [])

  const managerNames = new Map(
    managers.map((employee) => [
      employee.id,
      `${employee.first_name} ${employee.last_name}`,
    ]),
  )

  function closeForm() {
    setShowForm(false)
    setEditingDepartment(null)
  }

  async function saveDepartment(values) {
    if (editingDepartment) {
      await updateDepartment(editingDepartment.id, values)
      showToast('Department updated successfully.')
    } else {
      await createDepartment(values)
      showToast('Department created successfully.')
    }
    closeForm()
    list.refresh()
  }

  function openCreateForm() {
    setEditingDepartment(null)
    setShowForm(true)
  }

  const columns = [
    { key: 'code', label: 'Code', sortable: true },
    { key: 'name', label: 'Department', sortable: true },
    {
      key: 'manager_employee_id',
      label: 'Manager',
      render: (department) =>
        department.manager_employee_id
          ? managerNames.get(department.manager_employee_id) ??
            'Active employee'
          : '—',
    },
    {
      key: 'is_active',
      label: 'Status',
      sortable: true,
      render: (department) => (
        <span
          className={`badge ${
            department.is_active ? 'text-bg-success' : 'text-bg-secondary'
          }`}
        >
          {department.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    ...(canWrite
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (department) => (
              <Button
                aria-label={`Edit ${department.name}`}
                onClick={() => {
                  setEditingDepartment(department)
                  setShowForm(true)
                }}
                size="sm"
                variant="outline-primary"
              >
                Edit
              </Button>
            ),
          },
        ]
      : []),
    {
      key: 'employees',
      label: 'Employees',
      render: (department) => (
        <Button
          aria-label={`View employees in ${department.name}`}
          onClick={() => setViewingDepartment(department)}
          size="sm"
          variant="outline-secondary"
        >
          View employees
        </Button>
      ),
    },
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">
            Organization
          </p>
          <h1>Departments</h1>
          <p className="mb-0">Manage departments and their employee assignments.</p>
        </div>
        {canWrite && (
          <Button onClick={openCreateForm} variant="primary">
            Add department
          </Button>
        )}
      </div>
      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-8">
          <SearchBar
            delay={0}
            label="Search departments"
            onSearch={list.setSearchInput}
            placeholder="Search department name or code"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-4">
          <Form.Select
            aria-label="Filter by department status"
            onChange={(event) =>
              list.setFilter(
                'is_active',
                event.target.value === ''
                  ? ''
                  : event.target.value === 'true',
              )
            }
            value={
              list.filters?.is_active === undefined
                ? ''
                : String(list.filters.is_active)
            }
          >
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Form.Select>
        </div>
      </div>
      {managersError && (
        <ErrorMessage message={getApiError(managersError).message} />
      )}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No departments match your search and filters."
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
        <DepartmentFormModal
          department={editingDepartment}
          onHide={closeForm}
          onSave={saveDepartment}
          show={showForm}
        />
      )}
      {viewingDepartment && (
        <DepartmentEmployeesModal
          department={viewingDepartment}
          onHide={() => setViewingDepartment(null)}
          show
        />
      )}
    </section>
  )
}
