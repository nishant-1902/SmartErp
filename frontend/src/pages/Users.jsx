import { useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SearchBar from '../components/SearchBar.jsx'
import UserFormModal from '../components/UserFormModal.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import {
  activateUser,
  createUser,
  deactivateUser,
  listUsers,
  resetUserPassword,
  updateUser,
} from '../services/userService.js'
import { getApiError } from '../utils/apiErrors.js'

const roleLabels = {
  super_admin: 'Super Admin',
  hr_manager: 'HR Manager',
  inventory_manager: 'Inventory Manager',
  purchase_manager: 'Purchase Manager',
  sales_manager: 'Sales Manager',
  employee: 'Employee',
}

/**
 * Lists and manages accounts through the users:manage API.
 *
 * @returns {JSX.Element}
 */
export default function Users() {
  const { user: currentUser } = useAuth()
  const { showToast } = useToast()
  const [editingUser, setEditingUser] = useState(null)
  const [showForm, setShowForm] = useState(false)
  const [accountAction, setAccountAction] = useState(null)
  const [actionBusy, setActionBusy] = useState(false)
  const [resettingUser, setResettingUser] = useState(null)
  const [resetBusy, setResetBusy] = useState(false)
  const list = usePaginatedList(listUsers)

  function closeForm() {
    setShowForm(false)
    setEditingUser(null)
  }

  async function saveUser(values) {
    if (editingUser) {
      await updateUser(editingUser.id, values)
      showToast('User updated successfully.')
    } else {
      await createUser(values)
      showToast('User created successfully.')
    }
    closeForm()
    list.refresh()
  }

  async function confirmAccountAction() {
    if (!accountAction) return
    setActionBusy(true)
    try {
      const action = accountAction.action === 'activate'
        ? activateUser
        : deactivateUser
      await action(accountAction.user.id)
      showToast(
        `${accountAction.user.full_name} was ${accountAction.action}d successfully.`,
      )
      setAccountAction(null)
      list.refresh()
    } catch (error) {
      showToast(getApiError(error).message, 'danger', 'Unable to update account')
    } finally {
      setActionBusy(false)
    }
  }

  async function confirmPasswordReset() {
    if (!resettingUser) return
    setResetBusy(true)
    try {
      await resetUserPassword(resettingUser.id)
      showToast(
        'A password reset link was generated. In development, check the backend console.',
      )
      setResettingUser(null)
    } catch (error) {
      showToast(getApiError(error).message, 'danger', 'Unable to reset password')
    } finally {
      setResetBusy(false)
    }
  }

  const columns = [
    { key: 'full_name', label: 'Name' },
    { key: 'email', label: 'Email' },
    {
      key: 'role',
      label: 'Role',
      render: (account) => roleLabels[account.role] ?? account.role,
    },
    {
      key: 'is_active',
      label: 'Status',
      render: (account) => (
        <span className={`badge ${account.is_active ? 'text-bg-success' : 'text-bg-secondary'}`}>
          {account.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    { key: 'employee_id', label: 'Employee ID' },
    {
      key: 'actions',
      label: 'Actions',
      render: (account) => (
        <div className="d-flex flex-wrap gap-2">
          <Button
            aria-label={`Edit ${account.full_name}`}
            onClick={() => {
              setEditingUser(account)
              setShowForm(true)
            }}
            size="sm"
            variant="outline-primary"
          >
            Edit
          </Button>
          <Button
            aria-label={`Reset password for ${account.full_name}`}
            onClick={() => setResettingUser(account)}
            size="sm"
            variant="outline-secondary"
          >
            Reset password
          </Button>
          {account.is_active ? (
            <Button
              aria-label={`Deactivate ${account.full_name}`}
              disabled={account.id === currentUser?.id}
              onClick={() => setAccountAction({ user: account, action: 'deactivate' })}
              size="sm"
              title={account.id === currentUser?.id ? 'You cannot deactivate your own account.' : undefined}
              variant="outline-danger"
            >
              Deactivate
            </Button>
          ) : (
            <Button
              aria-label={`Activate ${account.full_name}`}
              onClick={() => setAccountAction({ user: account, action: 'activate' })}
              size="sm"
              variant="outline-success"
            >
              Activate
            </Button>
          )}
        </div>
      ),
    },
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Administration</p>
          <h1>Users</h1>
          <p className="mb-0">Manage account roles, employee links, and access status.</p>
        </div>
        <Button
          onClick={() => {
            setEditingUser(null)
            setShowForm(true)
          }}
          variant="primary"
        >
          Create user
        </Button>
      </div>

      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-5">
          <SearchBar
            label="Search users"
            onSearch={list.setSearchInput}
            placeholder="Search name or email"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter users by role"
            onChange={(event) => list.setFilter('role', event.target.value)}
            value={list.filters.role ?? ''}
          >
            <option value="">All roles</option>
            {Object.entries(roleLabels).map(([role, label]) => (
              <option key={role} value={role}>{label}</option>
            ))}
          </Form.Select>
        </div>
        <div className="col-12 col-sm-6 col-lg-4">
          <Form.Select
            aria-label="Filter users by active status"
            onChange={(event) =>
              list.setFilter(
                'is_active',
                event.target.value === '' ? '' : event.target.value === 'true',
              )
            }
            value={
              list.filters.is_active === undefined
                ? ''
                : String(list.filters.is_active)
            }
          >
            <option value="">All account statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Form.Select>
        </div>
      </div>

      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No users match your search and filters."
        loading={list.loading}
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />

      {showForm && (
        <UserFormModal
          onHide={closeForm}
          onSave={saveUser}
          show
          user={editingUser}
        />
      )}
      <ConfirmDialog
        busy={actionBusy}
        confirmLabel={accountAction?.action === 'activate' ? 'Activate account' : 'Deactivate account'}
        confirmVariant={accountAction?.action === 'activate' ? 'primary' : 'danger'}
        message={
          accountAction?.action === 'activate'
            ? `Activate ${accountAction.user.full_name}'s account?`
            : `Deactivate ${accountAction?.user.full_name}'s account? They will lose access immediately.`
        }
        onCancel={() => setAccountAction(null)}
        onConfirm={confirmAccountAction}
        show={Boolean(accountAction)}
        title={accountAction?.action === 'activate' ? 'Activate user' : 'Deactivate user'}
      />
      <ConfirmDialog
        busy={resetBusy}
        confirmLabel="Generate reset link"
        confirmVariant="primary"
        message={`Generate a password reset link for ${resettingUser?.full_name}?`}
        onCancel={() => setResettingUser(null)}
        onConfirm={confirmPasswordReset}
        show={Boolean(resettingUser)}
        title="Reset user password"
      />
    </section>
  )
}
