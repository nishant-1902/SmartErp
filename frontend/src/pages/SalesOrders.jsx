import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import SalesStatusBadge from '../components/SalesStatusBadge.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { listCustomers } from '../services/customerService.js'
import { listSalesOrders } from '../services/salesOrderService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

/**
 * Browse sales orders with customer, order-status, and payment-status filters.
 *
 * @returns {JSX.Element}
 */
export default function SalesOrders() {
  const { hasPermission } = useAuth()
  const canReadCustomers = hasPermission('customers:read')
  const list = usePaginatedList(listSalesOrders)
  const [customers, setCustomers] = useState([])
  const [customerError, setCustomerError] = useState('')

  useEffect(() => {
    if (!canReadCustomers) return undefined

    const controller = new AbortController()
    listCustomers(
      { page: 1, page_size: 100, status: 'active' },
      { signal: controller.signal },
    )
      .then(({ items }) => setCustomers(items))
      .catch((error) => {
        if (!controller.signal.aborted) {
          setCustomerError(getApiError(error).message)
        }
      })
    return () => controller.abort()
  }, [canReadCustomers])

  const columns = [
    {
      key: 'order_number',
      label: 'Order',
      render: (order) => <Link to={`/sales-orders/${order.id}`}>{order.order_number}</Link>,
    },
    { key: 'customer_snapshot', label: 'Customer', render: (order) => order.customer_snapshot?.name ?? '—' },
    { key: 'created_at', label: 'Created', render: (order) => formatDate(order.created_at) },
    { key: 'status', label: 'Status', render: (order) => <SalesStatusBadge status={order.status} /> },
    { key: 'payment_status', label: 'Payment', render: (order) => <SalesStatusBadge status={order.payment_status} /> },
    { key: 'grand_total', label: 'Total', render: (order) => formatMoney(order.grand_total) },
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap justify-content-between align-items-end gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Sales</p>
          <h1>Sales orders</h1>
          <p className="mb-0">Review order progress, payment status, and totals.</p>
        </div>
        {hasPermission('sales:create') && (
          <Button as={Link} to="/sales-orders/new">Create sales order</Button>
        )}
      </div>
      {customerError && <ErrorMessage message={customerError} />}
      <div className="row g-3 mb-3">
        <div className="col-sm-6 col-lg-4">
          <label className="form-label" htmlFor="sales-filter-status">Order status</label>
          <select
            className="form-select"
            id="sales-filter-status"
            onChange={(event) => list.setFilter('status', event.target.value)}
            value={list.filters.status ?? ''}
          >
            <option value="">All statuses</option>
            {['draft', 'confirmed', 'fulfilled', 'cancelled'].map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </div>
        <div className="col-sm-6 col-lg-4">
          <label className="form-label" htmlFor="sales-filter-payment">Payment status</label>
          <select
            className="form-select"
            id="sales-filter-payment"
            onChange={(event) => list.setFilter('payment_status', event.target.value)}
            value={list.filters.payment_status ?? ''}
          >
            <option value="">All payment statuses</option>
            {['unpaid', 'partial', 'paid'].map((status) => (
              <option key={status} value={status}>{status}</option>
            ))}
          </select>
        </div>
        {canReadCustomers && (
          <div className="col-lg-4">
            <label className="form-label" htmlFor="sales-filter-customer">Customer</label>
            <select
              className="form-select"
              id="sales-filter-customer"
              onChange={(event) => list.setFilter('customer_id', event.target.value)}
              value={list.filters.customer_id ?? ''}
            >
              <option value="">All customers</option>
              {customers.map((customer) => (
                <option key={customer.id} value={customer.id}>
                  {customer.name} ({customer.code})
                </option>
              ))}
            </select>
          </div>
        )}
      </div>
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No sales orders match these filters."
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
