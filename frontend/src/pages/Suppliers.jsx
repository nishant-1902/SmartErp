import { useState } from 'react'
import { Link } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SearchBar from '../components/SearchBar.jsx'
import SupplierFormModal from '../components/SupplierFormModal.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import {
  createSupplier,
  listSuppliers,
  updateSupplier,
} from '../services/supplierService.js'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Search, create, and edit suppliers.
 *
 * @returns {JSX.Element}
 */
export default function Suppliers() {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('suppliers:write')
  const { showToast } = useToast()
  const list = usePaginatedList(listSuppliers)
  const [editingSupplier, setEditingSupplier] = useState(null)
  const [formOpen, setFormOpen] = useState(false)

  function closeForm() {
    setFormOpen(false)
    setEditingSupplier(null)
  }

  async function saveSupplier(values) {
    if (editingSupplier) {
      await updateSupplier(editingSupplier.id, values)
      showToast('Supplier updated successfully.')
    } else {
      await createSupplier(values)
      showToast('Supplier created successfully.')
    }
    closeForm()
    list.refresh()
  }

  const columns = [
    { key: 'code', label: 'Code', sortable: true },
    {
      key: 'name',
      label: 'Supplier',
      sortable: true,
      render: (supplier) => (
        <Link to={`/suppliers/${supplier.id}`}>{supplier.name}</Link>
      ),
    },
    { key: 'contact_person', label: 'Contact' },
    { key: 'email', label: 'Email' },
    {
      key: 'status',
      label: 'Status',
      render: (supplier) => (
        <span
          className={`badge ${
            supplier.status === 'active' ? 'text-bg-success' : 'text-bg-secondary'
          }`}
        >
          {supplier.status === 'active' ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    ...(canWrite
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (supplier) => (
              <Button
                aria-label={`Edit ${supplier.name}`}
                onClick={() => {
                  setEditingSupplier(supplier)
                  setFormOpen(true)
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
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Purchasing</p>
          <h1>Suppliers</h1>
          <p className="mb-0">Manage supplier records and their active status.</p>
        </div>
        {canWrite && (
          <Button
            onClick={() => {
              setEditingSupplier(null)
              setFormOpen(true)
            }}
          >
            Add supplier
          </Button>
        )}
      </div>
      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-7">
          <SearchBar
            label="Search suppliers"
            onSearch={list.setSearchInput}
            placeholder="Search supplier name or code"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <select
            aria-label="Filter suppliers by status"
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
        emptyMessage="No suppliers match your search and filters."
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
      <SupplierFormModal
        onHide={closeForm}
        onSave={saveSupplier}
        show={formOpen}
        supplier={editingSupplier}
      />
    </section>
  )
}
