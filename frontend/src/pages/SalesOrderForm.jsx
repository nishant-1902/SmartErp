import { useEffect, useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import SalesProductPicker from '../components/SalesProductPicker.jsx'
import { useToast } from '../hooks/useToast.js'
import { listCustomers } from '../services/customerService.js'
import { createSalesOrder } from '../services/salesOrderService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'
import { calculateSalesPreview } from '../utils/salesPreview.js'
import * as yup from 'yup'

const percentage = yup
  .string()
  .matches(/^\d{1,3}(?:\.\d{1,2})?$/, 'Enter a percentage with up to 2 decimals.')
  .test('range', 'Percentage must be between 0 and 100.', (value) => {
    if (!value || !/^\d{1,3}(?:\.\d{1,2})?$/.test(value)) return true
    return Number(value) <= 100
  })

const schema = yup.object({
  customer_id: yup.string().required('Choose an active customer.'),
  items: yup
    .array()
    .of(
      yup.object({
        product_id: yup.string().required('Choose a product.'),
        quantity: yup
          .number()
          .typeError('Quantity must be a whole number.')
          .integer('Quantity must be a whole number.')
          .min(1, 'Quantity must be positive.')
          .required('Quantity is required.')
          .test('availability', 'Quantity exceeds currently available stock.', function (value) {
            const available = this.parent.available_quantity
            return available === undefined || !value || value <= available
          }),
        discount_percent: percentage.required(),
        tax_percent: percentage.required(),
      }),
    )
    .min(1, 'Add at least one product.')
    .test('unique-products', 'Each product may only appear once.', (items) => {
      const ids = (items ?? []).map((item) => item.product_id).filter(Boolean)
      return ids.length === new Set(ids).size
    }),
})

const emptyValues = {
  customer_id: '',
  items: [{
    product_id: '',
    name: '',
    sku: '',
    selling_price: '',
    available_quantity: undefined,
    quantity: 1,
    discount_percent: '0.00',
    tax_percent: '0.00',
  }],
}

/**
 * Create a Draft order, select customers/products, and show a non-authoritative estimate.
 *
 * @returns {JSX.Element}
 */
export default function SalesOrderForm() {
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [customers, setCustomers] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState('')
  const [serverError, setServerError] = useState('')
  const {
    control,
    register,
    handleSubmit,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: emptyValues,
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'items' })
  const watchedItems = useWatch({ control, name: 'items' }) ?? []
  const preview = calculateSalesPreview(
    watchedItems.map((item) => ({
      ...item,
      unit_price: item.selling_price,
    })),
  )

  useEffect(() => {
    const controller = new AbortController()
    listCustomers(
      { page: 1, page_size: 100, status: 'active' },
      { signal: controller.signal },
    )
      .then(({ items }) => setCustomers(items))
      .catch((error) => {
        if (!controller.signal.aborted) setLoadError(getApiError(error).message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false)
      })
    return () => controller.abort()
  }, [])

  async function submit(values) {
    setServerError('')
    const payload = {
      customer_id: values.customer_id,
      items: values.items.map((item) => ({
        product_id: item.product_id,
        quantity: item.quantity,
        discount_percent: item.discount_percent,
        tax_percent: item.tax_percent,
      })),
    }
    try {
      const order = await createSalesOrder(payload)
      showToast('Sales order draft created.')
      navigate(`/sales-orders/${order.id}`)
    } catch (error) {
      setServerError(getApiError(error).message)
    }
  }

  if (loading) return <LoadingSpinner label="Loading sales-order form" />
  if (loadError) return <ErrorMessage message={loadError} />

  return (
    <section>
      <div className="page-heading">
        <Link className="small" to="/sales-orders">← Sales orders</Link>
        <h1 className="mt-2">Create sales order</h1>
      </div>
      <ErrorMessage message={serverError} />
      <Form noValidate onSubmit={handleSubmit(submit)}>
        <Form.Group className="mb-4 col-lg-6">
          <Form.Label htmlFor="sales-customer">Customer</Form.Label>
          <Form.Select
            id="sales-customer"
            isInvalid={Boolean(errors.customer_id)}
            {...register('customer_id')}
          >
            <option value="">Choose an active customer</option>
            {customers.map((customer) => (
              <option key={customer.id} value={customer.id}>
                {customer.name} ({customer.code})
              </option>
            ))}
          </Form.Select>
          {errors.customer_id?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.customer_id.message}
            </Form.Control.Feedback>
          )}
        </Form.Group>

        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
          <h2 className="h4 mb-0">Items</h2>
          <Button
            onClick={() => append({
              product_id: '',
              name: '',
              sku: '',
              selling_price: '',
              quantity: 1,
              discount_percent: '0.00',
              tax_percent: '0.00',
            })}
            type="button"
            variant="outline-primary"
          >
            Add item
          </Button>
        </div>
        {errors.items?.message && (
          <p className="text-danger small">{errors.items.message}</p>
        )}
        {fields.map((field, index) => {
          const itemErrors = errors.items?.[index] ?? {}
          const item = watchedItems[index] ?? {}
          return (
            <div className="border rounded p-3 mb-3" key={field.id}>
              <div className="row g-3 align-items-end">
                <div className="col-12 col-lg-5">
                  <SalesProductPicker
                    index={index}
                    label={`${field.name} (${field.sku})`}
                    onSelect={(product) => {
                      setValue(`items.${index}.product_id`, product.id, { shouldValidate: true })
                      setValue(`items.${index}.name`, product.name)
                      setValue(`items.${index}.sku`, product.sku)
                      setValue(`items.${index}.selling_price`, product.selling_price)
                      setValue(`items.${index}.available_quantity`, product.available_quantity)
                    }}
                    value={item.product_id ?? ''}
                  />
                  <input type="hidden" {...register(`items.${index}.product_id`)} />
                  {itemErrors.product_id?.message && (
                    <p className="text-danger small">{itemErrors.product_id.message}</p>
                  )}
                  {item.product_id && (
                    <div className="form-text">
                      Estimate price: {formatMoney(item.selling_price)} per item
                    </div>
                  )}
                </div>
                <div className="col-6 col-lg-2">
                  <Form.Label htmlFor={`sales-quantity-${index}`}>Quantity</Form.Label>
                  <Form.Control
                    id={`sales-quantity-${index}`}
                    isInvalid={Boolean(itemErrors.quantity)}
                    max={item.available_quantity}
                    min={1}
                    type="number"
                    step={1}
                    {...register(`items.${index}.quantity`, { valueAsNumber: true })}
                  />
                  {itemErrors.quantity?.message && (
                    <div className="text-danger small">{itemErrors.quantity.message}</div>
                  )}
                </div>
                <div className="col-6 col-lg-2">
                  <Form.Label htmlFor={`sales-discount-${index}`}>Discount %</Form.Label>
                  <Form.Control
                    id={`sales-discount-${index}`}
                    inputMode="decimal"
                    isInvalid={Boolean(itemErrors.discount_percent)}
                    {...register(`items.${index}.discount_percent`)}
                  />
                  {itemErrors.discount_percent?.message && (
                    <div className="text-danger small">{itemErrors.discount_percent.message}</div>
                  )}
                </div>
                <div className="col-6 col-lg-2">
                  <Form.Label htmlFor={`sales-tax-${index}`}>Tax %</Form.Label>
                  <Form.Control
                    id={`sales-tax-${index}`}
                    inputMode="decimal"
                    isInvalid={Boolean(itemErrors.tax_percent)}
                    {...register(`items.${index}.tax_percent`)}
                  />
                  {itemErrors.tax_percent?.message && (
                    <div className="text-danger small">{itemErrors.tax_percent.message}</div>
                  )}
                </div>
                <div className="col-6 col-lg-1">
                  <Button
                    aria-label={`Remove item ${index + 1}`}
                    disabled={fields.length === 1}
                    onClick={() => remove(index)}
                    type="button"
                    variant="outline-danger"
                  >
                    Remove
                  </Button>
                </div>
              </div>
            </div>
          )
        })}
        <div aria-live="polite" className="border rounded p-3 mb-4">
          <h2 className="h5">Estimated total</h2>
          {preview ? (
            <dl className="row mb-2">
              <dt className="col-6">Subtotal</dt>
              <dd className="col-6 text-end">{formatMoney(preview.subtotal)}</dd>
              <dt className="col-6">Discount</dt>
              <dd className="col-6 text-end">{formatMoney(preview.discountTotal)}</dd>
              <dt className="col-6">Tax</dt>
              <dd className="col-6 text-end">{formatMoney(preview.taxTotal)}</dd>
              <dt className="col-6">Estimated grand total</dt>
              <dd className="col-6 text-end fw-bold">{formatMoney(preview.grandTotal)}</dd>
            </dl>
          ) : (
            <p className="text-muted">Select products and enter valid amounts to see an estimate.</p>
          )}
          <p className="small text-muted mb-0">
            Estimate only. The server reads final prices and calculates the saved totals.
          </p>
        </div>
        <Button disabled={isSubmitting} type="submit">
          {isSubmitting ? 'Creating…' : 'Create draft'}
        </Button>
      </Form>
    </section>
  )
}
