import { useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import { useToast } from '../hooks/useToast.js'
import { getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import ModalWrapper from './ModalWrapper.jsx'

/**
 * Submit one stock adjustment with a fresh idempotency key.
 *
 * @param {{show: boolean, product: object | null, onHide: () => void, onSubmit: (values: object, key: string) => Promise<void>}} props
 */
export default function StockAdjustmentModal({
  show,
  product,
  onHide,
  onSubmit,
}) {
  const { showToast } = useToast()
  const [quantityChange, setQuantityChange] = useState('')
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [submitting, setSubmitting] = useState(false)

  async function submit(event) {
    event.preventDefault()
    if (!product || submitting) return
    const quantity = Number(quantityChange)
    if (!Number.isSafeInteger(quantity) || quantity === 0) {
      setError('Enter a non-zero whole number.')
      return
    }
    if (reason.trim().length < 3) {
      setError('Reason must contain at least 3 characters.')
      return
    }

    setError('')
    setSubmitting(true)
    try {
      await onSubmit(
        {
          product_id: product.id,
          quantity_change: quantity,
          reason: reason.trim(),
        },
        globalThis.crypto.randomUUID(),
      )
      setQuantityChange('')
      setReason('')
      onHide()
    } catch (submitError) {
      const apiError = getApiError(submitError)
      setError(apiError.message)
      showToast(apiError.message, 'danger', 'Unable to adjust stock')
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
        disabled={submitting || !product}
        form="stock-adjustment-form"
        type="submit"
      >
        {submitting ? 'Applying…' : 'Apply adjustment'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={`Adjust stock${product ? ` — ${product.name}` : ''}`}
    >
      <ErrorMessage message={error} />
      {product && (
        <p className="small text-muted">
          On hand: {product.quantity_on_hand} · Reserved: {product.reserved_quantity} ·
          Available: {product.quantity_on_hand - product.reserved_quantity}
        </p>
      )}
      <Form id="stock-adjustment-form" onSubmit={submit}>
        <Form.Group className="mb-3">
          <Form.Label htmlFor="quantity-change">Quantity change</Form.Label>
          <Form.Control
            id="quantity-change"
            onChange={(event) => setQuantityChange(event.target.value)}
            placeholder="Positive to add, negative to remove"
            step="1"
            type="number"
            value={quantityChange}
          />
        </Form.Group>
        <Form.Group>
          <Form.Label htmlFor="stock-reason">Reason</Form.Label>
          <Form.Control
            id="stock-reason"
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            value={reason}
          />
        </Form.Group>
      </Form>
    </ModalWrapper>
  )
}
