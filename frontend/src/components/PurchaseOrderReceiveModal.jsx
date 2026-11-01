import { useRef, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import { useToast } from '../hooks/useToast.js'
import { getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import ModalWrapper from './ModalWrapper.jsx'

function collectMessages(value) {
  if (typeof value === 'string') return [value]
  if (Array.isArray(value)) return value.flatMap(collectMessages)
  if (value && typeof value === 'object') {
    return Object.values(value).flatMap(collectMessages)
  }
  return []
}

/**
 * Enter receipt quantities that do not exceed each PO line's remaining amount.
 *
 * @param {{show: boolean, purchaseOrder: object, onHide: () => void, onReceive: (values: object, key: string) => Promise<void>}} props
 */
export default function PurchaseOrderReceiveModal({
  show,
  purchaseOrder,
  onHide,
  onReceive,
}) {
  const { showToast } = useToast()
  const [quantities, setQuantities] = useState({})
  const [notes, setNotes] = useState('')
  const [serverError, setServerError] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [formError, setFormError] = useState('')
  const retryKey = useRef({ body: '', key: '' })

  function setQuantity(productId, value) {
    setQuantities((current) => ({ ...current, [productId]: value }))
    setServerError('')
    setFormError('')
  }

  async function submit(event) {
    event.preventDefault()
    setServerError('')
    setFormError('')
    const items = purchaseOrder.items
      .map((item) => ({
        product_id: item.product_id,
        quantity_received: Number(quantities[item.product_id] || 0),
      }))
      .filter((item) => item.quantity_received > 0)

    if (!items.length) {
      setFormError('Enter a positive quantity for at least one product.')
      return
    }
    const invalidQuantity = items.some((received) => {
      const line = purchaseOrder.items.find(
        (item) => item.product_id === received.product_id,
      )
      const remaining = line.quantity_ordered - line.quantity_received
      return (
        !Number.isSafeInteger(received.quantity_received) ||
        received.quantity_received > remaining
      )
    })
    if (invalidQuantity) {
      setFormError('Each received quantity must be a whole number within the remaining amount.')
      return
    }
    if (notes.trim() && notes.trim().length < 3) {
      setFormError('Notes must contain at least 3 characters.')
      return
    }

    const payload = JSON.stringify({ items, notes: notes.trim() || null })
    if (retryKey.current.body !== payload) {
      retryKey.current = { body: payload, key: crypto.randomUUID() }
    }

    setSubmitting(true)
    try {
      await onReceive(
        { items, ...(notes.trim() ? { notes: notes.trim() } : {}) },
        retryKey.current.key,
      )
      retryKey.current = { body: '', key: '' }
    } catch (error) {
      const apiError = getApiError(error)
      setServerError(apiError.message)
      const detailMessages = collectMessages(apiError.details)
      if (detailMessages.length) setFormError(detailMessages.join(' '))
      showToast(apiError.message, 'danger', 'Unable to receive purchase order')
    } finally {
      setSubmitting(false)
    }
  }

  const footer = (
    <>
      <Button disabled={submitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button
        disabled={submitting}
        form="purchase-receive-form"
        type="submit"
        variant="primary"
      >
        {submitting ? 'Receiving…' : 'Record receipt'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={`Receive ${purchaseOrder.po_number}`}
    >
      <ErrorMessage message={serverError} />
      <ErrorMessage message={formError} title="Receipt details" />
      <Form id="purchase-receive-form" onSubmit={submit}>
        {purchaseOrder.items.map((item) => {
          const remaining = item.quantity_ordered - item.quantity_received
          return (
            <Form.Group className="mb-3" key={item.product_id}>
              <Form.Label htmlFor={`receive-${item.product_id}`}>
                {item.name} ({item.sku}) — {item.quantity_received} received of{' '}
                {item.quantity_ordered}; {remaining} remaining
              </Form.Label>
              <Form.Control
                aria-label={`Receive quantity for ${item.name}`}
                id={`receive-${item.product_id}`}
                max={remaining}
                min={0}
                onChange={(event) =>
                  setQuantity(item.product_id, event.target.value)
                }
                type="number"
                step={1}
                value={quantities[item.product_id] ?? ''}
              />
            </Form.Group>
          )
        })}
        <Form.Group className="mb-3">
          <Form.Label htmlFor="receipt-notes">Notes (optional)</Form.Label>
          <Form.Control
            as="textarea"
            id="receipt-notes"
            maxLength={500}
            onChange={(event) => {
              setNotes(event.target.value)
              setServerError('')
              setFormError('')
            }}
            rows={2}
            value={notes}
          />
        </Form.Group>
      </Form>
    </ModalWrapper>
  )
}
