import { useCallback } from 'react'
import DataTable from './DataTable.jsx'
import ModalWrapper from './ModalWrapper.jsx'
import SearchBar from './SearchBar.jsx'
import Pagination from './Pagination.jsx'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { listDepartmentEmployees } from '../services/departmentService.js'
import { getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'

const columns = [
  { key: 'employee_code', label: 'Code', sortable: true },
  {
    key: 'name',
    label: 'Employee',
    sortable: true,
    sortBy: 'first_name',
    sortValue: (employee) => `${employee.first_name} ${employee.last_name}`,
    render: (employee) => `${employee.first_name} ${employee.last_name}`,
  },
  { key: 'email', label: 'Email', sortable: true },
  { key: 'designation', label: 'Designation', sortable: true },
  { key: 'status', label: 'Status', sortable: true },
]

/**
 * Shows the server-paginated employee list for a selected department.
 *
 * @param {{show: boolean, department?: object | null, onHide: () => void}} props
 */
export default function DepartmentEmployeesModal({
  show,
  department,
  onHide,
}) {
  const departmentId = department?.id
  const fetchEmployees = useCallback(
    (params, options) => listDepartmentEmployees(departmentId, params, options),
    [departmentId],
  )
  const list = usePaginatedList(fetchEmployees, {
    debounceMs: 300,
    pageSize: 10,
    scopeKey: department?.id ?? '',
  })
  const columnsWithSort = columns.map((column) => ({
    ...column,
    sortable: true,
  }))

  return (
    <ModalWrapper
      onHide={onHide}
      show={show}
      size="xl"
      title={`Employees — ${department?.name ?? 'Department'}`}
    >
      <div className="mb-3">
        <SearchBar
          delay={0}
          label="Search department employees"
          onSearch={list.setSearchInput}
          placeholder="Search name, email or code"
        />
      </div>
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columnsWithSort}
        data={list.items}
        emptyMessage="No employees are assigned to this department."
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
    </ModalWrapper>
  )
}
