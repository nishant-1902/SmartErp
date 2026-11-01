import { useEffect } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const supplierSchema = yup.object({
  code: yup.string().trim().max(40, 'Code must be 40 characters or fewer.'),
  name: yup
    .string()
    .trim()
    .required('Supplier name is required.')
    .max(200, 'Name must be 200 characters or fewer.'),
  contact_person: yup.string().nullable().max(150),
  email: yup.string().nullable().email('Enter a valid email address.').max(254),
  phone: yup.string().nullable().max(30),
  payment_terms: yup.string().nullable().max(500),
  address: yup
    .object({
      line1: yup.string().max(200),
      line2: yup.string().max(200),
      city: yup.string().max(100),
      region: yup.string().max(100),
      postal_code: yup.string().max(30),
      country: yup.string().max(100),
    })
    .test(
      'complete-address',
      'Address needs a street, city, and country.',
      (address) => {
        const hasAddress = Object.values(address ?? {}).some((value) =>
          value?.trim(),
        )
        return (
          !hasAddress ||
          Boolean(address?.line1?.trim() && address.city?.trim() && address.country?.trim())
        )
      },
    ),
  status: yup.string().oneOf(['active', 'inactive']).required(),
})

function getDefaultValues(supplier) {
  return {
    code: supplier?.code ?? '',
    name: supplier?.name ?? '',
    contact_person: supplier?.contact_person ?? '',
    email: supplier?.email ?? '',
    phone: supplier?.phone ?? '',
    payment_terms: supplier?.payment_terms ?? '',
    address: {
      line1: supplier?.address?.line1 ?? '',
      line2: supplier?.address?.line2 ?? '',
      city: supplier?.address?.city ?? '',
      region: supplier?.address?.region ?? '',
      postal_code: supplier?.address?.postal_code ?? '',
      country: supplier?.address?.country ?? '',
    },
    status: supplier?.status ?? 'active',
  }
}

/**
 * Create or edit supplier details, including active/inactive status.
 *
 * @param {{show: boolean, supplier?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function SupplierFormModal({
  show,
  supplier = null,
  onHide,
  onSave,
}) {
  const isEditing = Boolean(supplier)
  const { showToast } = useToast()
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(supplierSchema),
    defaultValues: getDefaultValues(supplier),
  })

  useEffect(() => {
    if (show) reset(getDefaultValues(supplier))
  }, [reset, show, supplier])

  async function submit(values) {
    try {
      const payload = {
        ...values,
        ...(values.code.trim()
          ? { code: values.code.trim().toUpperCase() }
          : { code: undefined }),
        name: values.name.trim(),
        contact_person: values.contact_person?.trim() || null,
        email: values.email?.trim() || null,
        phone: values.phone?.trim() || null,
        payment_terms: values.payment_terms?.trim() || null,
        address: Object.values(values.address ?? {}).some((value) => value?.trim())
          ? {
              line1: values.address.line1.trim(),
              line2: values.address.line2.trim() || null,
              city: values.address.city.trim(),
              region: values.address.region.trim() || null,
              postal_code: values.address.postal_code.trim() || null,
              country: values.address.country.trim(),
            }
          : null,
      }
      if (payload.code === undefined) delete payload.code
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      showToast(
        [apiError.message, ...remaining].join(' '),
        'danger',
        'Unable to save supplier',
      )
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button
        disabled={isSubmitting}
        form="supplier-form"
        type="submit"
        variant="primary"
      >
        {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create supplier'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={isEditing ? 'Edit supplier' : 'Create supplier'}
    >
      <Form id="supplier-form" noValidate onSubmit={handleSubmit(submit)}>
        <FormInput error={errors.code} label="Supplier code (optional)" name="code" registerProps={register('code')} />
        <FormInput error={errors.name} label="Supplier name" name="name" registerProps={register('name')} />
        <FormInput error={errors.contact_person} label="Contact person" name="contact_person" registerProps={register('contact_person')} />
        <FormInput error={errors.email} label="Email" name="email" registerProps={register('email')} />
        <FormInput error={errors.phone} label="Phone" name="phone" registerProps={register('phone')} />
        <h2 className="h6 mt-4">Postal address (optional)</h2>
        <FormInput error={errors.address?.line1} label="Street address" name="address-line1" registerProps={register('address.line1')} />
        <FormInput error={errors.address?.line2} label="Address line 2" name="address-line2" registerProps={register('address.line2')} />
        <FormInput error={errors.address?.city} label="City" name="address-city" registerProps={register('address.city')} />
        <div className="row">
          <div className="col-md-6">
            <FormInput error={errors.address?.region} label="Region / state" name="address-region" registerProps={register('address.region')} />
          </div>
          <div className="col-md-6">
            <FormInput error={errors.address?.postal_code} label="Postal code" name="address-postal-code" registerProps={register('address.postal_code')} />
          </div>
        </div>
        <FormInput error={errors.address?.country} label="Country" name="address-country" registerProps={register('address.country')} />
        <Form.Group className="mb-3">
          <Form.Label htmlFor="supplier-payment-terms">Payment terms</Form.Label>
          <Form.Control
            as="textarea"
            id="supplier-payment-terms"
            isInvalid={Boolean(errors.payment_terms)}
            rows={2}
            {...register('payment_terms')}
          />
          {errors.payment_terms?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.payment_terms.message}
            </Form.Control.Feedback>
          )}
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label htmlFor="supplier-status">Status</Form.Label>
          <Form.Select id="supplier-status" {...register('status')}>
            <option value="active">Active</option>
            <option value="inactive">Inactive</option>
          </Form.Select>
        </Form.Group>
        <ErrorMessage
          message={Object.values(errors)
            .map((error) => error?.message)
            .filter(Boolean)
            .join(' ')}
        />
      </Form>
    </ModalWrapper>
  )
}
