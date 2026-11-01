import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { listPurchaseOrders } from '../services/purchaseOrderService.js'
import { listSuppliers } from '../services/supplierService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

const statuses = [
  'draft',
  'pending_approval',
  'approved',
  'rejected',
  'partially_received',
  'received',
  'cancelled',
]

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

/**
 * Browse purchase orders and filter by workflow status, supplier, and creation date.
 *
 * @returns {JSX.Element}
 */
export default function Purchases() {
  const { hasPermission } = useAuth()
  const navigate = useNavigate()
  const list = usePaginatedList(listPurchaseOrders)
  const [suppliers, setSuppliers] = useState([])
  const [supplierError, setSupplierError] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [filterError, setFilterError] = useState('')

  useEffect(() => {
    const controller = new AbortController()
    listSuppliers({ page: 1, page_size: 100 }, { signal: controller.signal })
      .then(({ items }) => setSuppliers(items))
      .catch((error) => {
        if (!controller.signal.aborted) {
          setSupplierError(getApiError(error).message)
        }
      })
    return () => controller.abort()
  }, [])

  function applyDateFilters() {
    if (startDate && endDate && startDate > endDate) {
      setFilterError('End date must be on or after the start date.')
      return
    }
    setFilterError('')
    list.setFilter('start_date', startDate ? `${startDate}T00:00:00Z` : '')
    list.setFilter('end_date', endDate ? `${endDate}T23:59:59.999Z` : '')
  }

  function clearDateFilters() {
    setStartDate('')
    setEndDate('')
    setFilterError('')
    list.setFilter('start_date', '')
    list.setFilter('end_date', '')
  }

  const columns = [
    {
      key: 'po_number',
      label: 'PO number',
      render: (order) => (
        <Link to={`/purchase-orders/${order.id}`}>{order.po_number}</Link>
      ),
    },
    {
      key: 'supplier_snapshot',
      label: 'Supplier',
      render: (order) => order.supplier_snapshot?.name ?? '—',
    },
    {
      key: 'status',
      label: 'Status',
      render: (order) => (
        <span className="badge text-bg-secondary">
          {order.status.replaceAll('_', ' ')}
        </span>
      ),
    },
    { key: 'created_at', label: 'Created', render: (order) => formatDate(order.created_at) },
    { key: 'grand_total', label: 'Total', render: (order) => formatMoney(order.grand_total) },
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Purchasing</p>
          <h1>Purchase orders</h1>
          <p className="mb-0">Review orders, approvals, and receiving progress.</p>
        </div>
        {hasPermission('purchase:create') && (
          <Button onClick={() => navigate('/purchase-orders/new')}>
            Create purchase order
          </Button>
        )}
      </div>
      <div className="row g-3 align-items-end mb-3">
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter purchase orders by status"
            onChange={(event) => list.setFilter('status', event.target.value)}
            value={list.filters.status ?? ''}
          >
            <option value="">All statuses</option>
            {statuses.map((status) => (
              <option key={status} value={status}>{status.replaceAll('_', ' ')}</option>
            ))}
          </Form.Select>
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter purchase orders by supplier"
            onChange={(event) => list.setFilter('supplier_id', event.target.value)}
            value={list.filters.supplier_id ?? ''}
          >
            <option value="">All suppliers</option>
            {suppliers.map((supplier) => (
              <option key={supplier.id} value={supplier.id}>{supplier.name}</option>
            ))}
          </Form.Select>
        </div>
        <div className="col-6 col-lg-2">
          <Form.Label htmlFor="purchase-start-date">Created from</Form.Label>
          <Form.Control
            id="purchase-start-date"
            onChange={(event) => setStartDate(event.target.value)}
            type="date"
            value={startDate}
          />
        </div>
        <div className="col-6 col-lg-2">
          <Form.Label htmlFor="purchase-end-date">Created to</Form.Label>
          <Form.Control
            id="purchase-end-date"
            onChange={(event) => setEndDate(event.target.value)}
            type="date"
            value={endDate}
          />
        </div>
        <div className="col-12 col-lg-2 d-flex gap-2">
          <Button onClick={applyDateFilters} size="sm" type="button">Apply dates</Button>
          <Button onClick={clearDateFilters} size="sm" type="button" variant="outline-secondary">
            Clear
          </Button>
        </div>
      </div>
      {supplierError && <ErrorMessage message={supplierError} title="Could not load suppliers" />}
      {filterError && <ErrorMessage message={filterError} />}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No purchase orders match these filters."
        loading={list.loading}
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />
    </section>
  )
}
