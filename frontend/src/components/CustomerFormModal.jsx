import { useEffect } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const addressShape = {
  line1: yup.string().max(200),
  line2: yup.string().max(200),
  city: yup.string().max(100),
  region: yup.string().max(100),
  postal_code: yup.string().max(30),
  country: yup.string().max(100),
}

function isCompleteOrEmpty(address) {
  const values = Object.values(address ?? {})
  if (!values.some((value) => value?.trim())) return true
  return Boolean(address?.line1?.trim() && address.city?.trim() && address.country?.trim())
}

const addressSchema = yup
  .object(addressShape)
  .test('complete-address', 'Provide street, city, and country.', isCompleteOrEmpty)

const customerSchema = yup.object({
  code: yup.string().trim().required('Customer code is required.').max(40),
  name: yup.string().trim().required('Customer name is required.').max(200),
  email: yup.string().trim().email('Enter a valid email address.').max(254).nullable(),
  phone: yup.string().trim().max(30).nullable(),
  tax_id: yup.string().trim().max(100).nullable(),
  status: yup.string().oneOf(['active', 'inactive']).required(),
  credit_limit: yup
    .string()
    .matches(/^\d{1,16}(?:\.\d{1,2})?$/, 'Enter a non-negative amount with up to 2 decimals.')
    .nullable()
    .transform((value) => (value === '' ? null : value)),
  billing_address: addressSchema,
  shipping_address: addressSchema,
})

function getAddress(address) {
  return {
    line1: address?.line1 ?? '',
    line2: address?.line2 ?? '',
    city: address?.city ?? '',
    region: address?.region ?? '',
    postal_code: address?.postal_code ?? '',
    country: address?.country ?? '',
  }
}

function getValues(customer) {
  return {
    code: customer?.code ?? '',
    name: customer?.name ?? '',
    email: customer?.email ?? '',
    phone: customer?.phone ?? '',
    tax_id: customer?.tax_id ?? '',
    status: customer?.status ?? 'active',
    credit_limit: customer?.credit_limit ?? '',
    billing_address: getAddress(customer?.billing_address),
    shipping_address: getAddress(customer?.shipping_address),
  }
}

function addressPayload(address) {
  if (!Object.values(address ?? {}).some((value) => value?.trim())) return null
  return {
    line1: address.line1.trim(),
    line2: address.line2.trim() || null,
    city: address.city.trim(),
    region: address.region.trim() || null,
    postal_code: address.postal_code.trim() || null,
    country: address.country.trim(),
  }
}

/**
 * Create or update a customer with optional billing and shipping addresses.
 *
 * @param {{show: boolean, customer?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function CustomerFormModal({
  show,
  customer = null,
  onHide,
  onSave,
}) {
  const editing = Boolean(customer)
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(customerSchema),
    defaultValues: getValues(customer),
  })

  useEffect(() => {
    if (show) reset(getValues(customer))
  }, [customer, reset, show])

  async function submit(values) {
    const payload = {
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      email: values.email?.trim() || null,
      phone: values.phone?.trim() || null,
      tax_id: values.tax_id?.trim().toUpperCase() || null,
      status: values.status,
      credit_limit: values.credit_limit || null,
      billing_address: addressPayload(values.billing_address),
      shipping_address: addressPayload(values.shipping_address),
    }
    try {
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      if (remaining.length) {
        setError('root.server', { message: `${apiError.message} ${remaining.join(' ')}` })
      } else {
        setError('root.server', { message: apiError.message })
      }
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Close
      </Button>
      <Button disabled={isSubmitting} form="customer-form" type="submit">
        {isSubmitting ? 'Saving…' : editing ? 'Save changes' : 'Create customer'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      size="lg"
      title={editing ? 'Edit customer' : 'Create customer'}
    >
      <Form id="customer-form" noValidate onSubmit={handleSubmit(submit)}>
        <ErrorMessage message={errors.root?.server?.message} />
        <div className="row">
          <div className="col-md-4">
            <FormInput error={errors.code} label="Customer code" name="customer-code" registerProps={register('code')} />
          </div>
          <div className="col-md-8">
            <FormInput error={errors.name} label="Customer name" name="customer-name" registerProps={register('name')} />
          </div>
          <div className="col-md-6">
            <FormInput error={errors.email} label="Email" name="customer-email" type="email" registerProps={register('email')} />
          </div>
          <div className="col-md-6">
            <FormInput error={errors.phone} label="Phone" name="customer-phone" registerProps={register('phone')} />
          </div>
          <div className="col-md-6">
            <FormInput error={errors.tax_id} label="Tax ID (optional)" name="customer-tax-id" registerProps={register('tax_id')} />
          </div>
          <div className="col-md-3">
            <FormInput error={errors.credit_limit} hint="Leave blank for no limit." label="Credit limit" name="customer-credit-limit" registerProps={register('credit_limit')} />
          </div>
          <div className="col-md-3">
            <Form.Group className="mb-3">
              <Form.Label htmlFor="customer-status">Status</Form.Label>
              <Form.Select id="customer-status" {...register('status')}>
                <option value="active">Active</option>
                <option value="inactive">Inactive</option>
              </Form.Select>
            </Form.Group>
          </div>
        </div>
        {['billing_address', 'shipping_address'].map((prefix) => (
          <fieldset className="border rounded p-3 mb-3" key={prefix}>
            <legend className="float-none w-auto px-2 fs-6">
              {prefix === 'billing_address' ? 'Billing address' : 'Shipping address'}
            </legend>
            <div className="row">
              {[
                ['line1', 'Street address'],
                ['line2', 'Address line 2'],
                ['city', 'City'],
                ['region', 'Region / state'],
                ['postal_code', 'Postal code'],
                ['country', 'Country'],
              ].map(([field, label]) => (
                <div className={field === 'line1' || field === 'line2' ? 'col-12' : 'col-md-6'} key={field}>
                  <FormInput
                    error={errors[prefix]?.[field]}
                    label={label}
                    name={`${prefix}-${field}`}
                    registerProps={register(`${prefix}.${field}`)}
                  />
                </div>
              ))}
              {errors[prefix]?.message && (
                <p className="text-danger small">{errors[prefix].message}</p>
              )}
            </div>
          </fieldset>
        ))}
      </Form>
    </ModalWrapper>
  )
}
