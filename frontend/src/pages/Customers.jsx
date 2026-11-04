import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import CustomerFormModal from '../components/CustomerFormModal.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SearchBar from '../components/SearchBar.jsx'
import SalesStatusBadge from '../components/SalesStatusBadge.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import { createCustomer, listCustomers, updateCustomer } from '../services/customerService.js'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Search, list, create, and edit customer records.
 *
 * @returns {JSX.Element}
 */
export default function Customers() {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('customers:write')
  const { showToast } = useToast()
  const list = usePaginatedList(listCustomers)
  const [formOpen, setFormOpen] = useState(false)
  const [editingCustomer, setEditingCustomer] = useState(null)

  function closeForm() {
    setFormOpen(false)
    setEditingCustomer(null)
  }

  async function saveCustomer(values) {
    if (editingCustomer) {
      await updateCustomer(editingCustomer.id, values)
      showToast('Customer updated successfully.')
    } else {
      await createCustomer(values)
      showToast('Customer created successfully.')
    }
    closeForm()
    list.refresh()
  }

  const columns = [
    { key: 'code', label: 'Code', sortable: true },
    {
      key: 'name',
      label: 'Customer',
      sortable: true,
      render: (customer) => (
        <Link to={`/customers/${customer.id}`}>{customer.name}</Link>
      ),
    },
    { key: 'email', label: 'Email' },
    { key: 'phone', label: 'Phone' },
    {
      key: 'status',
      label: 'Status',
      render: (customer) => <SalesStatusBadge status={customer.status} />,
    },
    ...(canWrite
      ? [{
          key: 'actions',
          label: 'Actions',
          render: (customer) => (
            <Button
              aria-label={`Edit ${customer.name}`}
              onClick={() => {
                setEditingCustomer(customer)
                setFormOpen(true)
              }}
              size="sm"
              variant="outline-primary"
            >
              Edit
            </Button>
          ),
        }]
      : []),
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap justify-content-between align-items-end gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Sales</p>
          <h1>Customers</h1>
          <p className="mb-0">Manage customer contacts and review their sales history.</p>
        </div>
        {canWrite && (
          <Button onClick={() => setFormOpen(true)}>Add customer</Button>
        )}
      </div>
      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-7">
          <SearchBar
            label="Search customers"
            onSearch={list.setSearchInput}
            placeholder="Search customer name or code"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <select
            aria-label="Filter customers by status"
            className="form-select"
            onChange={(event) => list.setFilter('status', event.target.value)}
            value={list.filters.status ?? ''}
          >
            <option value="">All statuses</option>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </select>
        </div>
      </div>
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No customers match your search and filters."
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
      <CustomerFormModal
        customer={editingCustomer}
        onHide={closeForm}
        onSave={saveCustomer}
        show={formOpen}
      />
    </section>
  )
}
