import { useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Table from 'react-bootstrap/Table'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import RecordPaymentModal from '../components/RecordPaymentModal.jsx'
import SalesReturnModal from '../components/SalesReturnModal.jsx'
import SalesStatusBadge from '../components/SalesStatusBadge.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'
import { listInvoices } from '../services/invoiceService.js'
import {
  fulfilSalesOrder,
  getSalesOrder,
  recordSalesOrderPayment,
  returnSalesOrderItems,
  transitionSalesOrder,
} from '../services/salesOrderService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

function subtractMoney(total, paid) {
  const toCents = (value) => {
    const [whole, fraction = ''] = String(value ?? '0').split('.')
    return BigInt(whole) * 100n + BigInt(`${fraction}00`.slice(0, 2))
  }
  const outstanding = toCents(total) - toCents(paid)
  return `${outstanding / 100n}.${String(outstanding % 100n).padStart(2, '0')}`
}

/**
 * Show order details, timeline, invoice link, and permission-gated sales actions.
 *
 * @returns {JSX.Element}
 */
export default function SalesOrderDetail() {
  const { salesOrderId } = useParams()
  const { hasPermission } = useAuth()
  const { showToast } = useToast()
  const [orderState, setOrderState] = useState({ id: null, order: null, error: '' })
  const [invoiceState, setInvoiceState] = useState({ id: null, invoice: null })
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [dialogAction, setDialogAction] = useState('')
  const [paymentOpen, setPaymentOpen] = useState(false)
  const [returnOpen, setReturnOpen] = useState(false)
  const fulfillmentKey = useRef('')
  const canReadInvoice = hasPermission('invoices:read')

  useEffect(() => {
    const controller = new AbortController()
    getSalesOrder(salesOrderId, { signal: controller.signal })
      .then((order) => {
        setOrderState({ id: salesOrderId, order, error: '' })
        if (order.status === 'fulfilled' && canReadInvoice) {
          listInvoices(
            { sales_order_id: salesOrderId, page: 1, page_size: 1 },
            { signal: controller.signal },
          )
            .then((result) => {
              if (!controller.signal.aborted) {
                setInvoiceState({ id: salesOrderId, invoice: result.items[0] ?? null })
              }
            })
            .catch((error) => {
              if (!controller.signal.aborted) {
                setActionError(getApiError(error).message)
              }
            })
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setOrderState({
            id: salesOrderId,
            order: null,
            error: getApiError(error).message,
          })
        }
      })
    return () => controller.abort()
  }, [canReadInvoice, salesOrderId])

  const loading = orderState.id !== salesOrderId
  const order = loading ? null : orderState.order
  const invoice = invoiceState.id === salesOrderId ? invoiceState.invoice : null
  const error = loading ? '' : orderState.error || actionError

  async function transition(action) {
    setActionError('')
    setBusy(true)
    try {
      const updated = await transitionSalesOrder(salesOrderId, action)
      setOrderState({ id: salesOrderId, order: updated, error: '' })
      setDialogAction('')
      showToast(`Sales order moved to ${updated.status}.`)
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
    } finally {
      setBusy(false)
    }
  }

  async function fulfill() {
    setActionError('')
    setBusy(true)
    if (!fulfillmentKey.current) fulfillmentKey.current = crypto.randomUUID()
    try {
      const result = await fulfilSalesOrder(salesOrderId, fulfillmentKey.current)
      fulfillmentKey.current = ''
      setOrderState({
        id: salesOrderId,
        order: result.sales_order,
        error: '',
      })
      setInvoiceState({ id: salesOrderId, invoice: result.invoice })
      showToast('Sales order fulfilled and invoice created.')
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
    } finally {
      setBusy(false)
    }
  }

  async function submitPayment(values, key) {
    setActionError('')
    setBusy(true)
    try {
      const result = await recordSalesOrderPayment(salesOrderId, values, key)
      setOrderState({ id: salesOrderId, order: result.sales_order, error: '' })
      showToast('Payment recorded.')
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
      throw requestError
    } finally {
      setBusy(false)
    }
  }

  async function submitReturn(values) {
    setActionError('')
    setBusy(true)
    try {
      const result = await returnSalesOrderItems(salesOrderId, values)
      setOrderState({ id: salesOrderId, order: result.sales_order, error: '' })
      showToast(`Return ${result.sales_return.credit_note_number} processed.`)
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
      throw requestError
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingSpinner label="Loading sales order" />
  if (orderState.error && !order) return <ErrorMessage message={orderState.error} />
  if (!order) return <ErrorMessage message="Sales order was not found." />

  const status = order.status
  const outstanding = subtractMoney(order.grand_total, order.paid_total)
  const canReturn = order.items.some(
    (item) => item.quantity > (item.returned_quantity ?? 0),
  )

  return (
    <section>
      <div className="page-heading">
        <Link className="small" to="/sales-orders">← Sales orders</Link>
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mt-2">
          <div>
            <p className="text-primary text-uppercase fw-bold small mb-2">Sales order</p>
            <h1>{order.order_number}</h1>
            <p className="mb-0">{order.customer_snapshot?.name ?? 'Customer'} · Created {formatDate(order.created_at)}</p>
          </div>
          <div className="d-flex flex-wrap gap-2">
            <SalesStatusBadge status={status} />
            <SalesStatusBadge status={order.payment_status} />
            {order.return_status !== 'none' && <SalesStatusBadge status={order.return_status} label={`${order.return_status} return`} />}
          </div>
        </div>
      </div>
      {error && <ErrorMessage message={error} />}

      <div className="d-flex flex-wrap gap-2 mb-4">
        {status === 'draft' && hasPermission('sales:confirm') && (
          <Button disabled={busy} onClick={() => setDialogAction('confirm')}>Confirm</Button>
        )}
        {status === 'confirmed' && hasPermission('sales:fulfil') && (
          <Button disabled={busy} onClick={fulfill} variant="success">
            {busy ? 'Fulfilling…' : 'Fulfil'}
          </Button>
        )}
        {['draft', 'confirmed'].includes(status) && hasPermission('sales:cancel') && (
          <Button disabled={busy} onClick={() => setDialogAction('cancel')} variant="outline-danger">
            Cancel order
          </Button>
        )}
        {status === 'fulfilled' && hasPermission('payments:record') && outstanding !== '0.00' && (
          <Button disabled={busy} onClick={() => setPaymentOpen(true)} variant="outline-primary">
            Record payment
          </Button>
        )}
        {status === 'fulfilled' && canReturn && hasPermission('returns:process') && (
          <Button disabled={busy} onClick={() => setReturnOpen(true)} variant="outline-secondary">
            Process return
          </Button>
        )}
        {invoice && canReadInvoice && (
          <Link className="btn btn-outline-primary" to={`/invoices/${invoice.id}`}>
            View invoice
          </Link>
        )}
      </div>
      {status === 'draft' && hasPermission('sales:create') && (
        <p><Link to="/sales-orders/new">Create another order</Link></p>
      )}

      <h2 className="h4">Items</h2>
      <div className="table-responsive">
        <Table bordered hover>
          <thead>
            <tr>
              <th>SKU</th><th>Product</th><th>Quantity</th><th>Returned</th>
              <th>Unit price</th><th>Discount</th><th>Tax</th><th>Line total</th>
            </tr>
          </thead>
          <tbody>
            {order.items.map((item) => (
              <tr key={item.product_id}>
                <td>{item.sku}</td><td>{item.name}</td><td>{item.quantity}</td>
                <td>{item.returned_quantity ?? 0}</td>
                <td>{formatMoney(item.unit_price)}</td>
                <td>{item.discount_percent}%</td><td>{formatMoney(item.line_tax)}</td>
                <td>{formatMoney(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      <dl className="row col-md-6 ms-auto">
        <dt className="col-6">Subtotal</dt><dd className="col-6 text-end">{formatMoney(order.subtotal)}</dd>
        <dt className="col-6">Discount</dt><dd className="col-6 text-end">{formatMoney(order.discount_total)}</dd>
        <dt className="col-6">Tax</dt><dd className="col-6 text-end">{formatMoney(order.tax_total)}</dd>
        <dt className="col-6">Grand total</dt><dd className="col-6 text-end fw-bold">{formatMoney(order.grand_total)}</dd>
        <dt className="col-6">Paid</dt><dd className="col-6 text-end">{formatMoney(order.paid_total ?? '0.00')}</dd>
        <dt className="col-6">Outstanding</dt><dd className="col-6 text-end">{formatMoney(outstanding)}</dd>
      </dl>

      <h2 className="h4 mt-4">Status timeline</h2>
      <ol className="list-group list-group-numbered">
        {order.status_history.map((entry, index) => (
          <li className="list-group-item" key={`${entry.status}-${entry.at}-${index}`}>
            <div className="d-flex flex-wrap justify-content-between gap-2">
              <strong>{entry.status}</strong><span className="text-muted">{formatDate(entry.at)}</span>
            </div>
            {entry.note && <div>{entry.note}</div>}
            <div className="small text-muted">By {entry.by}</div>
          </li>
        ))}
      </ol>

      <ConfirmDialog
        busy={busy}
        confirmLabel={dialogAction === 'cancel' ? 'Cancel sales order' : 'Confirm order'}
        confirmVariant={dialogAction === 'cancel' ? 'danger' : 'primary'}
        message={dialogAction === 'cancel'
          ? 'Cancel this order? A confirmed order will release its stock reservation.'
          : 'Confirm this order and reserve the available stock?'}
        onCancel={() => setDialogAction('')}
        onConfirm={() => transition(dialogAction)}
        show={Boolean(dialogAction)}
        title={dialogAction === 'cancel' ? 'Cancel sales order' : 'Confirm sales order'}
      />
      <RecordPaymentModal
        onHide={() => setPaymentOpen(false)}
        onSubmit={submitPayment}
        outstanding={formatMoney(outstanding)}
        show={paymentOpen}
      />
      <SalesReturnModal
        onHide={() => setReturnOpen(false)}
        onSubmit={submitReturn}
        order={order}
        show={returnOpen}
      />
    </section>
  )
}
