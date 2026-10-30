import { useEffect, useState } from 'react'
import Button from 'react-bootstrap/Button'
import ConfirmDialog from './ConfirmDialog.jsx'
import DataTable from './DataTable.jsx'
import EmployeeFormModal from './EmployeeFormModal.jsx'
import ErrorMessage from './ErrorMessage.jsx'
import LoadingSpinner from './LoadingSpinner.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'
import {
  deactivateEmployee,
  getEmployee,
  updateEmployee,
} from '../services/employeeService.js'
import { getApiError } from '../utils/apiErrors.js'

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? value
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(date)
}

const profileColumns = [
  { key: 'field', label: 'Field' },
  { key: 'value', label: 'Value' },
]

/**
 * Fetches and displays a single employee profile with authorized actions.
 *
 * @param {{employeeId: string}} props
 */
export default function EmployeeProfileDetails({ employeeId }) {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('employees:write')
  const { showToast } = useToast()
  const [employee, setEmployee] = useState(null)
  const [loadedEmployeeId, setLoadedEmployeeId] = useState(null)
  const [error, setError] = useState(null)
  const [showEdit, setShowEdit] = useState(false)
  const [showDeactivate, setShowDeactivate] = useState(false)
  const [deactivating, setDeactivating] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getEmployee(employeeId, { signal: controller.signal })
      .then((record) => {
        setEmployee(record)
        setError(null)
        setLoadedEmployeeId(employeeId)
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) {
          setError(requestError)
          setLoadedEmployeeId(employeeId)
        }
      })
    return () => controller.abort()
  }, [employeeId])

  async function saveEmployee(values) {
    const updated = await updateEmployee(employeeId, values)
    setEmployee(updated)
    setShowEdit(false)
    showToast('Employee updated successfully.')
  }

  async function confirmDeactivation() {
    setDeactivating(true)
    try {
      const updated = await deactivateEmployee(employeeId)
      setEmployee(updated)
      setShowDeactivate(false)
      showToast('Employee deactivated successfully.')
    } catch (requestError) {
      showToast(getApiError(requestError).message, 'danger', 'Unable to deactivate')
    } finally {
      setDeactivating(false)
    }
  }

  if (loadedEmployeeId !== employeeId) {
    return (
      <div className="text-center py-5">
        <LoadingSpinner label="Loading employee profile" />
      </div>
    )
  }
  if (error) return <ErrorMessage message={getApiError(error).message} />
  if (!employee) return <ErrorMessage message="Employee profile was not found." />

  const values = [
    ['Employee code', employee.employee_code],
    ['First name', employee.first_name],
    ['Last name', employee.last_name],
    ['Email', employee.email],
    ['Phone', employee.phone || '—'],
    ['Department ID', employee.department_id],
    ['Designation', employee.designation],
    ['Joining date', formatDate(employee.joining_date)],
    ['Status', employee.status === 'on_leave' ? 'On leave' : employee.status],
    ['Created', formatDate(employee.created_at)],
    ['Last updated', formatDate(employee.updated_at)],
  ].map(([field, value]) => ({ field, value }))

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">
            Employee profile
          </p>
          <h1>{employee.first_name} {employee.last_name}</h1>
          <p className="mb-0">{employee.employee_code}</p>
        </div>
        {canWrite && (
          <div className="d-flex gap-2">
            <Button onClick={() => setShowEdit(true)} variant="outline-primary">
              Edit
            </Button>
            {employee.status !== 'inactive' && (
              <Button
                onClick={() => setShowDeactivate(true)}
                variant="outline-danger"
              >
                Deactivate
              </Button>
            )}
          </div>
        )}
      </div>
      <DataTable columns={profileColumns} data={values} />
      {canWrite && (
        <>
          {showEdit && (
            <EmployeeFormModal
              employee={employee}
              onHide={() => setShowEdit(false)}
              onSave={saveEmployee}
              show
            />
          )}
          <ConfirmDialog
            busy={deactivating}
            confirmLabel="Deactivate employee"
            message="This employee will be marked inactive. Their record will be kept."
            onCancel={() => setShowDeactivate(false)}
            onConfirm={confirmDeactivation}
            show={showDeactivate}
            title="Deactivate employee"
          />
        </>
      )}
    </section>
  )
}
