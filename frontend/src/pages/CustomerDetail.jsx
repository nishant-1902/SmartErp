import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import Pagination from '../components/Pagination.jsx'
import SalesStatusBadge from '../components/SalesStatusBadge.jsx'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { getCustomer, listCustomerSalesOrders } from '../services/customerService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

/**
 * Show a customer record and its paginated sales-order history.
 *
 * @returns {JSX.Element}
 */
export default function CustomerDetail() {
  const { customerId } = useParams()
  const [customerState, setCustomerState] = useState({
    id: null,
    customer: null,
    error: '',
  })
  const fetchHistory = useCallback(
    (params, options) => listCustomerSalesOrders(customerId, params, options),
    [customerId],
  )
  const history = usePaginatedList(fetchHistory)

  useEffect(() => {
    const controller = new AbortController()
    getCustomer(customerId, { signal: controller.signal })
      .then((customer) => setCustomerState({ id: customerId, customer, error: '' }))
      .catch((error) => {
        if (!controller.signal.aborted) {
          setCustomerState({
            id: customerId,
            customer: null,
            error: getApiError(error).message,
          })
        }
      })
    return () => controller.abort()
  }, [customerId])

  const loading = customerState.id !== customerId
  const customer = loading ? null : customerState.customer
  if (loading) return <LoadingSpinner label="Loading customer" />
  if (customerState.error) return <ErrorMessage message={customerState.error} />
  if (!customer) return <ErrorMessage message="Customer was not found." />

  const columns = [
    {
      key: 'order_number',
      label: 'Order',
      render: (order) => <Link to={`/sales-orders/${order.id}`}>{order.order_number}</Link>,
    },
    { key: 'created_at', label: 'Created', render: (order) => formatDate(order.created_at) },
    { key: 'status', label: 'Status', render: (order) => <SalesStatusBadge status={order.status} /> },
    { key: 'payment_status', label: 'Payment', render: (order) => <SalesStatusBadge status={order.payment_status} /> },
    { key: 'grand_total', label: 'Total', render: (order) => formatMoney(order.grand_total) },
  ]

  return (
    <section>
      <div className="page-heading">
        <Link className="small" to="/customers">← Customers</Link>
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mt-2">
          <div>
            <p className="text-primary text-uppercase fw-bold small mb-2">
              Customer · {customer.code}
            </p>
            <h1>{customer.name}</h1>
            <p className="mb-0">{customer.email || 'No email'} · {customer.phone || 'No phone'}</p>
          </div>
          <SalesStatusBadge status={customer.status} />
        </div>
      </div>
      {customer.tax_id && <p><strong>Tax ID:</strong> {customer.tax_id}</p>}
      {customer.credit_limit && (
        <p><strong>Credit limit:</strong> {formatMoney(customer.credit_limit)}</p>
      )}
      <div className="row g-4">
        {[
          ['Billing address', customer.billing_address],
          ['Shipping address', customer.shipping_address],
        ].map(([label, address]) => address && (
          <div className="col-md-6" key={label}>
            <h2 className="h6">{label}</h2>
            <address>
              {address.line1}
              {address.line2 && <><br />{address.line2}</>}
              <br />
              {[address.city, address.region, address.postal_code].filter(Boolean).join(', ')}
              <br />{address.country}
            </address>
          </div>
        ))}
      </div>
      <h2 className="h4 mt-4">Sales history</h2>
      {history.error && <ErrorMessage message={getApiError(history.error).message} />}
      <DataTable
        columns={columns}
        data={history.items}
        emptyMessage="This customer has no sales orders yet."
        loading={history.loading}
      />
      <Pagination
        onPageChange={history.setPage}
        page={history.meta.page ?? history.page}
        pageSize={history.meta.page_size ?? history.pageSize}
        totalItems={history.meta.total ?? 0}
      />
    </section>
  )
}
