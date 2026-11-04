import { useRef, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ErrorMessage from './ErrorMessage.jsx'
import ModalWrapper from './ModalWrapper.jsx'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Capture a payment while retaining its idempotency key across retry attempts.
 *
 * @param {{show: boolean, outstanding: string, onHide: () => void, onSubmit: (values: object, key: string) => Promise<void>}} props
 */
export default function RecordPaymentModal({
  show,
  outstanding,
  onHide,
  onSubmit,
}) {
  const [amount, setAmount] = useState('')
  const [method, setMethod] = useState('cash')
  const [reference, setReference] = useState('')
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)
  const [fieldError, setFieldError] = useState('')
  const retry = useRef({ body: '', key: '' })

  function close() {
    if (busy) return
    setAmount('')
    setMethod('cash')
    setReference('')
    setError('')
    setFieldError('')
    retry.current = { body: '', key: '' }
    onHide()
  }

  async function submit(event) {
    event.preventDefault()
    setError('')
    setFieldError('')
    if (!/^\d{1,16}(?:\.\d{1,2})?$/.test(amount) || /^0+(?:\.0{1,2})?$/.test(amount)) {
      setFieldError('Enter a payment amount greater than zero with up to 2 decimals.')
      return
    }

    const values = {
      amount,
      method,
      ...(reference.trim() ? { reference: reference.trim() } : {}),
    }
    const body = JSON.stringify(values)
    if (retry.current.body !== body) {
      retry.current = { body, key: crypto.randomUUID() }
    }

    setBusy(true)
    try {
      await onSubmit(values, retry.current.key)
      retry.current = { body: '', key: '' }
      setAmount('')
      setMethod('cash')
      setReference('')
      onHide()
    } catch (requestError) {
      setError(getApiError(requestError).message)
    } finally {
      setBusy(false)
    }
  }

  const footer = (
    <>
      <Button disabled={busy} onClick={close} variant="outline-secondary">Cancel</Button>
      <Button disabled={busy} form="sales-payment-form" type="submit">
        {busy ? 'Recording…' : 'Record payment'}
      </Button>
    </>
  )

  return (
    <ModalWrapper footer={footer} onHide={close} show={show} title="Record payment">
      <ErrorMessage message={error || fieldError} />
      <p>Outstanding balance: <strong>{outstanding}</strong></p>
      <Form id="sales-payment-form" onSubmit={submit}>
        <Form.Group className="mb-3">
          <Form.Label htmlFor="sales-payment-amount">Amount</Form.Label>
          <Form.Control
            autoComplete="off"
            id="sales-payment-amount"
            inputMode="decimal"
            onChange={(event) => setAmount(event.target.value)}
            value={amount}
          />
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label htmlFor="sales-payment-method">Method</Form.Label>
          <Form.Select
            id="sales-payment-method"
            onChange={(event) => setMethod(event.target.value)}
            value={method}
          >
            <option value="cash">Cash</option>
            <option value="bank_transfer">Bank transfer</option>
            <option value="card">Card</option>
            <option value="other">Other</option>
          </Form.Select>
        </Form.Group>
        <Form.Group>
          <Form.Label htmlFor="sales-payment-reference">Reference (optional)</Form.Label>
          <Form.Control
            id="sales-payment-reference"
            maxLength={200}
            onChange={(event) => setReference(event.target.value)}
            value={reference}
          />
        </Form.Group>
      </Form>
    </ModalWrapper>
  )
}
