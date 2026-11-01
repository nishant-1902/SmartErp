import { useEffect } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const schema = yup.object({
  reason: yup
    .string()
    .trim()
    .required('A rejection reason is required.')
    .min(3, 'Enter at least 3 characters.')
    .max(500, 'Reason must be 500 characters or fewer.'),
})

/**
 * Collect the required reason before rejecting a purchase order.
 *
 * @param {{show: boolean, onHide: () => void, onReject: (reason: string) => Promise<void>}} props
 */
export default function PurchaseOrderRejectModal({ show, onHide, onReject }) {
  const { showToast } = useToast()
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({ resolver: yupResolver(schema), defaultValues: { reason: '' } })

  useEffect(() => {
    if (show) reset({ reason: '' })
  }, [reset, show])

  async function submit(values) {
    try {
      await onReject(values.reason.trim())
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      showToast(
        [apiError.message, ...remaining].join(' '),
        'danger',
        'Unable to reject purchase order',
      )
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Keep order
      </Button>
      <Button
        disabled={isSubmitting}
        form="purchase-reject-form"
        type="submit"
        variant="danger"
      >
        {isSubmitting ? 'Rejecting…' : 'Reject order'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title="Reject purchase order"
    >
      <Form id="purchase-reject-form" noValidate onSubmit={handleSubmit(submit)}>
        <Form.Group>
          <Form.Label htmlFor="purchase-rejection-reason">Reason</Form.Label>
          <Form.Control
            as="textarea"
            id="purchase-rejection-reason"
            isInvalid={Boolean(errors.reason)}
            maxLength={500}
            rows={4}
            {...register('reason')}
          />
          {errors.reason?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.reason.message}
            </Form.Control.Feedback>
          )}
        </Form.Group>
        <ErrorMessage
          message={errors.reason?.type === 'server' ? errors.reason.message : ''}
        />
      </Form>
    </ModalWrapper>
  )
}
