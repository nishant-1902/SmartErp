import { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Table from 'react-bootstrap/Table'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import PurchaseOrderReceiveModal from '../components/PurchaseOrderReceiveModal.jsx'
import PurchaseOrderRejectModal from '../components/PurchaseOrderRejectModal.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'
import {
  getPurchaseOrder,
  receivePurchaseOrder,
  transitionPurchaseOrder,
} from '../services/purchaseOrderService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatStatus(status) {
  return status.replaceAll('_', ' ')
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
 * Display a purchase order, its status timeline, and permission-gated actions.
 *
 * @returns {JSX.Element}
 */
export default function PurchaseOrderDetail() {
  const { purchaseOrderId } = useParams()
  const { user, role, hasPermission } = useAuth()
  const { showToast } = useToast()
  const [orderState, setOrderState] = useState({
    id: null,
    order: null,
    error: '',
  })
  const [busy, setBusy] = useState(false)
  const [actionError, setActionError] = useState('')
  const [showReject, setShowReject] = useState(false)
  const [showReceive, setShowReceive] = useState(false)
  const [showCancel, setShowCancel] = useState(false)

  useEffect(() => {
    const controller = new AbortController()
    getPurchaseOrder(purchaseOrderId, { signal: controller.signal })
      .then((order) => {
        setActionError('')
        setOrderState({ id: purchaseOrderId, order, error: '' })
      })
      .catch((requestError) => {
        if (!controller.signal.aborted) {
          setOrderState({
            id: purchaseOrderId,
            order: null,
            error: getApiError(requestError).message,
          })
        }
      })
    return () => controller.abort()
  }, [purchaseOrderId])

  const loading = orderState.id !== purchaseOrderId
  const purchaseOrder = loading ? null : orderState.order
  const error = loading ? '' : orderState.error || actionError

  async function runTransition(action, values = {}, modal = false) {
    setActionError('')
    setBusy(true)
    try {
      const updated = await transitionPurchaseOrder(
        purchaseOrderId,
        action,
        values,
      )
      setOrderState({ id: purchaseOrderId, order: updated, error: '' })
      showToast(`Purchase order moved to ${formatStatus(updated.status)}.`)
      if (action === 'reject') setShowReject(false)
      if (action === 'cancel') setShowCancel(false)
      return updated
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
      if (modal) throw requestError
      return null
    } finally {
      setBusy(false)
    }
  }

  async function submitReceipt(values, idempotencyKey) {
    setActionError('')
    setBusy(true)
    try {
      const receipt = await receivePurchaseOrder(
        purchaseOrderId,
        values,
        idempotencyKey,
      )
      const updated = await getPurchaseOrder(purchaseOrderId)
      setOrderState({ id: purchaseOrderId, order: updated, error: '' })
      setShowReceive(false)
      showToast(`Receipt ${receipt.receipt_reference} recorded.`)
    } catch (requestError) {
      setActionError(getApiError(requestError).message)
      throw requestError
    } finally {
      setBusy(false)
    }
  }

  if (loading) return <LoadingSpinner label="Loading purchase order" />
  if (error && !purchaseOrder) return <ErrorMessage message={error} />
  if (!purchaseOrder) return <ErrorMessage message="Purchase order was not found." />

  const status = purchaseOrder.status
  const isCreator = purchaseOrder.created_by === user?.id
  const canApprove =
    status === 'pending_approval' &&
    hasPermission('purchase:approve') &&
    (!isCreator || role === 'super_admin')
  const canCancel =
    ['draft', 'pending_approval'].includes(status) &&
    hasPermission('purchase:cancel')
  const canReceive =
    ['approved', 'partially_received'].includes(status) &&
    hasPermission('purchase:receive')

  return (
    <section>
      <div className="page-heading">
        <Link className="small" to="/purchase-orders">← Purchase orders</Link>
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mt-2">
          <div>
            <p className="text-primary text-uppercase fw-bold small mb-2">Purchase order</p>
            <h1>{purchaseOrder.po_number}</h1>
            <p className="mb-0">
              {purchaseOrder.supplier_snapshot?.name ?? 'Supplier'} · Created{' '}
              {formatDate(purchaseOrder.created_at)}
            </p>
          </div>
          <span className="badge text-bg-secondary fs-6">{formatStatus(status)}</span>
        </div>
      </div>
      {error && <ErrorMessage message={error} />}

      <div className="d-flex flex-wrap gap-2 mb-4">
        {status === 'draft' && hasPermission('purchase:submit') && (
          <Button disabled={busy} onClick={() => runTransition('submit')}>
            Submit
          </Button>
        )}
        {canApprove && (
          <Button disabled={busy} onClick={() => runTransition('approve')}>
            Approve
          </Button>
        )}
        {status === 'pending_approval' && hasPermission('purchase:reject') && (
          <Button
            disabled={busy}
            onClick={() => setShowReject(true)}
            variant="outline-danger"
          >
            Reject
          </Button>
        )}
        {canReceive && (
          <Button
            disabled={busy}
            onClick={() => setShowReceive(true)}
            variant="success"
          >
            Receive
          </Button>
        )}
        {status === 'draft' &&
          hasPermission('purchase:create') &&
          purchaseOrder.created_by === user?.id && (
            <Button
              as={Link}
              to={`/purchase-orders/${purchaseOrder.id}/edit`}
              variant="outline-primary"
            >
              Edit draft
            </Button>
          )}
        {canCancel && (
          <Button
            disabled={busy}
            onClick={() => setShowCancel(true)}
            variant="outline-secondary"
          >
            Cancel order
          </Button>
        )}
      </div>

      <h2 className="h4">Items</h2>
      <div className="table-responsive">
        <Table bordered hover>
          <thead>
            <tr>
              <th>SKU</th>
              <th>Product</th>
              <th>Ordered</th>
              <th>Received</th>
              <th>Unit cost</th>
              <th>Line total</th>
            </tr>
          </thead>
          <tbody>
            {purchaseOrder.items.map((item) => (
              <tr key={item.product_id}>
                <td>{item.sku}</td>
                <td>{item.name}</td>
                <td>{item.quantity_ordered}</td>
                <td>{item.quantity_received}</td>
                <td>{formatMoney(item.unit_cost)}</td>
                <td>{formatMoney(item.line_total)}</td>
              </tr>
            ))}
          </tbody>
        </Table>
      </div>
      <dl className="row col-md-6 ms-auto">
        <dt className="col-6">Subtotal</dt>
        <dd className="col-6 text-end">{formatMoney(purchaseOrder.subtotal)}</dd>
        <dt className="col-6">Tax ({purchaseOrder.tax_rate}%)</dt>
        <dd className="col-6 text-end">{formatMoney(purchaseOrder.tax_total)}</dd>
        <dt className="col-6">Grand total</dt>
        <dd className="col-6 text-end fw-bold">{formatMoney(purchaseOrder.grand_total)}</dd>
      </dl>

      <h2 className="h4 mt-4">Status timeline</h2>
      <ol className="list-group list-group-numbered">
        {purchaseOrder.status_history.map((entry, index) => (
          <li className="list-group-item" key={`${entry.status}-${entry.at}-${index}`}>
            <div className="d-flex flex-wrap justify-content-between gap-2">
              <strong>{formatStatus(entry.status)}</strong>
              <span className="text-muted">{formatDate(entry.at)}</span>
            </div>
            {entry.note && <div>{entry.note}</div>}
            <div className="small text-muted">By {entry.by}</div>
          </li>
        ))}
      </ol>

      <PurchaseOrderRejectModal
        onHide={() => setShowReject(false)}
        onReject={(reason) => runTransition('reject', { reason }, true)}
        show={showReject}
      />
      {showReceive && (
        <PurchaseOrderReceiveModal
          onHide={() => setShowReceive(false)}
          onReceive={submitReceipt}
          purchaseOrder={purchaseOrder}
          show
        />
      )}
      <ConfirmDialog
        busy={busy}
        confirmLabel="Cancel purchase order"
        message="This action cannot be undone. Cancel this purchase order?"
        onCancel={() => setShowCancel(false)}
        onConfirm={() => runTransition('cancel')}
        show={showCancel}
        title="Cancel purchase order"
      />
    </section>
  )
}
