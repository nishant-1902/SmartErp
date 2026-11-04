import { useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ErrorMessage from './ErrorMessage.jsx'
import ModalWrapper from './ModalWrapper.jsx'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Select fulfilled quantities to return and require a return reason.
 *
 * @param {{show: boolean, order: object, onHide: () => void, onSubmit: (values: object) => Promise<void>}} props
 */
export default function SalesReturnModal({ show, order, onHide, onSubmit }) {
  const [quantities, setQuantities] = useState({})
  const [reason, setReason] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function submit(event) {
    event.preventDefault()
    setError('')
    const items = order.items
      .map((item) => ({
        product_id: item.product_id,
        quantity: Number(quantities[item.product_id] || 0),
      }))
      .filter((item) => item.quantity > 0)
    if (!items.length) {
      setError('Enter a positive return quantity for at least one product.')
      return
    }
    if (reason.trim().length < 3) {
      setError('Reason must contain at least 3 characters.')
      return
    }
    setBusy(true)
    try {
      await onSubmit({ items, reason: reason.trim() })
      setQuantities({})
      setReason('')
      onHide()
    } catch (requestError) {
      setError(getApiError(requestError).message)
    } finally {
      setBusy(false)
    }
  }

  const footer = (
    <>
      <Button disabled={busy} onClick={onHide} variant="outline-secondary">Cancel</Button>
      <Button disabled={busy} form="sales-return-form" type="submit">
        {busy ? 'Processing…' : 'Process return'}
      </Button>
    </>
  )

  return (
    <ModalWrapper footer={footer} onHide={onHide} show={show} title={`Return ${order.order_number}`}>
      <ErrorMessage message={error} />
      <Form id="sales-return-form" onSubmit={submit}>
        {order.items.map((item) => {
          const remaining = item.quantity - (item.returned_quantity ?? 0)
          return (
            <Form.Group className="mb-3" key={item.product_id}>
              <Form.Label htmlFor={`return-${item.product_id}`}>
                {item.name} ({item.sku}) — {remaining} returnable
              </Form.Label>
              <Form.Control
                id={`return-${item.product_id}`}
                max={remaining}
                min={0}
                onChange={(event) =>
                  setQuantities((current) => ({
                    ...current,
                    [item.product_id]: event.target.value,
                  }))
                }
                type="number"
                step={1}
                value={quantities[item.product_id] ?? ''}
              />
            </Form.Group>
          )
        })}
        <Form.Group>
          <Form.Label htmlFor="sales-return-reason">Reason</Form.Label>
          <Form.Control
            as="textarea"
            id="sales-return-reason"
            maxLength={500}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
            value={reason}
          />
        </Form.Group>
      </Form>
    </ModalWrapper>
  )
}
