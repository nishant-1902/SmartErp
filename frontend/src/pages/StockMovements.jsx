import { useState } from 'react'
import Form from 'react-bootstrap/Form'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { listStockMovements } from '../services/productService.js'
import { getApiError } from '../utils/apiErrors.js'

const movementTypes = [
  'purchase_receipt',
  'sale_fulfilment',
  'sale_return',
  'adjustment',
  'reservation',
  'reservation_release',
]

function formatMovementType(value) {
  return value
    .split('_')
    .map((word) => word[0].toUpperCase() + word.slice(1))
    .join(' ')
}

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

/**
 * Search the append-only inventory movement ledger with server-side filters.
 *
 * @returns {JSX.Element}
 */
export default function StockMovements() {
  const list = usePaginatedList(listStockMovements)
  const [productId, setProductId] = useState('')
  const [userId, setUserId] = useState('')
  const [startDate, setStartDate] = useState('')
  const [endDate, setEndDate] = useState('')
  const [filterError, setFilterError] = useState('')

  function applyIdFilters() {
    const objectIdPattern = /^[a-f\d]{24}$/i
    if (productId && !objectIdPattern.test(productId.trim())) {
      setFilterError('Product ID must be a 24-character hexadecimal ObjectId.')
      return
    }
    if (userId && !objectIdPattern.test(userId.trim())) {
      setFilterError('User ID must be a 24-character hexadecimal ObjectId.')
      return
    }
    if (startDate && endDate && startDate > endDate) {
      setFilterError('End date must be on or after the start date.')
      return
    }
    setFilterError('')
    list.setFilter('product', productId.trim())
    list.setFilter('user', userId.trim())
    list.setFilter('start_date', startDate ? `${startDate}T00:00:00Z` : '')
    list.setFilter('end_date', endDate ? `${endDate}T23:59:59.999Z` : '')
  }

  function clearIdFilters() {
    setProductId('')
    setUserId('')
    setStartDate('')
    setEndDate('')
    setFilterError('')
    list.setFilter('product', '')
    list.setFilter('user', '')
    list.setFilter('type', '')
    list.setFilter('start_date', '')
    list.setFilter('end_date', '')
  }

  const columns = [
    { key: 'created_at', label: 'Date', render: (row) => formatDate(row.created_at) },
    {
      key: 'product_id',
      label: 'Product ID',
    },
    {
      key: 'movement_type',
      label: 'Type',
      render: (row) => formatMovementType(row.movement_type),
    },
    { key: 'quantity_change', label: 'Quantity change' },
    { key: 'reserved_change', label: 'Reserved change' },
    { key: 'quantity_before', label: 'On hand before' },
    { key: 'quantity_after', label: 'On hand after' },
    { key: 'reason', label: 'Reason' },
    { key: 'performed_by', label: 'User ID' },
  ]

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Inventory</p>
        <h1>Stock movements</h1>
        <p className="mb-0">Append-only history of every recorded stock change.</p>
      </div>
      <div className="row g-3 mb-3">
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Control
            aria-label="Filter movements by product ID"
            onChange={(event) => setProductId(event.target.value)}
            placeholder="Product ObjectId"
            value={productId}
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter movements by type"
            onChange={(event) => list.setFilter('type', event.target.value)}
            value={list.filters.type ?? ''}
          >
            <option value="">All movement types</option>
            {movementTypes.map((type) => (
              <option key={type} value={type}>
                {formatMovementType(type)}
              </option>
            ))}
          </Form.Select>
        </div>
        <div className="col-12 col-sm-6 col-lg-2">
          <Form.Control
            aria-label="Start date"
            onChange={(event) => setStartDate(event.target.value)}
            type="date"
            value={startDate}
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-2">
          <Form.Control
            aria-label="End date"
            onChange={(event) => setEndDate(event.target.value)}
            type="date"
            value={endDate}
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-2">
          <Form.Control
            aria-label="Filter movements by user ID"
            onChange={(event) => setUserId(event.target.value)}
            placeholder="User ID"
            value={userId}
          />
        </div>
        <div className="col-12 d-flex gap-2">
          <button className="btn btn-primary" onClick={applyIdFilters} type="button">
            Apply ID and date filters
          </button>
          <button className="btn btn-outline-secondary" onClick={clearIdFilters} type="button">
            Clear filters
          </button>
        </div>
      </div>
      {filterError && <ErrorMessage message={filterError} />}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No stock movements match these filters."
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
