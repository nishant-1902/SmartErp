import { useEffect, useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useFieldArray, useForm, useWatch } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import PurchaseOrderProductPicker from '../components/PurchaseOrderProductPicker.jsx'
import { useToast } from '../hooks/useToast.js'
import {
  createPurchaseOrder,
  getPurchaseOrder,
  updatePurchaseOrder,
} from '../services/purchaseOrderService.js'
import { listSuppliers } from '../services/supplierService.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'
import { calculatePurchasePreview } from '../utils/purchasePreview.js'
import * as yup from 'yup'

const moneyPattern = /^\d{1,16}(?:\.\d{1,2})?$/
const schema = yup.object({
  supplier_id: yup.string().required('Choose an active supplier.'),
  tax_rate: yup
    .string()
    .required('Tax rate is required.')
    .matches(/^\d{1,3}(?:\.\d{1,2})?$/, 'Enter a percentage with up to 2 decimals.')
    .test('max-rate', 'Tax rate cannot exceed 100%.', (value) => {
      if (!value || !/^\d{1,3}(?:\.\d{1,2})?$/.test(value)) return true
      return Number(value) <= 100
    }),
  items: yup
    .array()
    .of(
      yup.object({
        product_id: yup.string().required('Choose a product.'),
        quantity_ordered: yup
          .number()
          .typeError('Quantity must be a whole number.')
          .integer('Quantity must be a whole number.')
          .min(1, 'Quantity must be positive.')
          .required('Quantity is required.'),
        unit_cost: yup
          .string()
          .required('Unit cost is required.')
          .matches(moneyPattern, 'Enter a cost with up to 2 decimals.')
          .test('positive-cost', 'Unit cost must be greater than zero.', (value) => {
            if (!value || !moneyPattern.test(value)) return true
            return BigInt(value.replace('.', '').replace(/^0+/, '') || '0') > 0n
          }),
      }),
    )
    .min(1, 'Add at least one product.')
    .test('unique-products', 'Each product may only appear once.', (items) => {
      const ids = (items ?? []).map((item) => item.product_id).filter(Boolean)
      return ids.length === new Set(ids).size
    }),
})

const emptyValues = {
  supplier_id: '',
  tax_rate: '0.00',
  items: [{ product_id: '', name: '', sku: '', quantity_ordered: 1, unit_cost: '' }],
}

function getOrderValues(order) {
  return {
    supplier_id: order.supplier_id,
    tax_rate: order.tax_rate,
    items: order.items.map((item) => ({
      product_id: item.product_id,
      name: item.name,
      sku: item.sku,
      quantity_ordered: item.quantity_ordered,
      unit_cost: item.unit_cost,
    })),
  }
}

/**
 * Create or edit a Draft PO with searchable line items and a display-only total.
 *
 * @returns {JSX.Element}
 */
export default function PurchaseOrderForm() {
  const { purchaseOrderId } = useParams()
  const editing = Boolean(purchaseOrderId)
  const navigate = useNavigate()
  const { showToast } = useToast()
  const [suppliers, setSuppliers] = useState([])
  const formKey = purchaseOrderId ?? 'new'
  const [loadState, setLoadState] = useState({ key: null, error: '' })
  const [serverError, setServerError] = useState('')
  const [additionalErrors, setAdditionalErrors] = useState('')
  const {
    control,
    register,
    handleSubmit,
    reset,
    setError,
    setValue,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: emptyValues,
  })
  const { fields, append, remove } = useFieldArray({ control, name: 'items' })
  const watchedItems = useWatch({ control, name: 'items' }) ?? []
  const taxRate = useWatch({ control, name: 'tax_rate' }) ?? ''
  const preview = calculatePurchasePreview(watchedItems, taxRate)
  const loading = loadState.key !== formKey
  const loadError = loading ? '' : loadState.error

  useEffect(() => {
    const controller = new AbortController()
    Promise.all([
      listSuppliers(
        { page: 1, page_size: 100, status: 'active' },
        { signal: controller.signal },
      ),
      editing
        ? getPurchaseOrder(purchaseOrderId, { signal: controller.signal })
        : Promise.resolve(null),
    ])
      .then(([supplierResult, order]) => {
        setSuppliers(supplierResult.items)
        if (order && order.status !== 'draft') {
          setLoadState({
            key: formKey,
            error: 'Only Draft purchase orders can be edited.',
          })
          return
        }
        reset(order ? getOrderValues(order) : emptyValues)
        setLoadState({ key: formKey, error: '' })
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setLoadState({ key: formKey, error: getApiError(error).message })
        }
      })
    return () => controller.abort()
  }, [editing, formKey, purchaseOrderId, reset])

  async function submit(values) {
    setServerError('')
    setAdditionalErrors('')
    const payload = {
      supplier_id: values.supplier_id,
      tax_rate: values.tax_rate,
      items: values.items.map((item) => ({
        product_id: item.product_id,
        quantity_ordered: item.quantity_ordered,
        unit_cost: item.unit_cost,
      })),
    }
    try {
      const order = editing
        ? await updatePurchaseOrder(purchaseOrderId, payload)
        : await createPurchaseOrder(payload)
      showToast(editing ? 'Purchase order updated.' : 'Purchase order created.')
      navigate(`/purchase-orders/${order.id}`)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setAdditionalErrors(remaining.join(' '))
    }
  }

  if (loading) {
    return <LoadingSpinner label="Loading purchase-order form" />
  }

  if (loadError) {
    return (
      <section>
        <ErrorMessage message={loadError} />
        {purchaseOrderId && (
          <Link className="btn btn-outline-secondary" to={`/purchase-orders/${purchaseOrderId}`}>
            Return to purchase order
          </Link>
        )}
      </section>
    )
  }

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Purchasing</p>
        <h1>{editing ? 'Edit draft purchase order' : 'Create purchase order'}</h1>
      </div>
      <ErrorMessage message={serverError} />
      <ErrorMessage message={additionalErrors} title="Additional validation details" />
      <Form noValidate onSubmit={handleSubmit(submit)}>
        <div className="row g-3">
          <div className="col-12 col-md-6">
            <Form.Group>
              <Form.Label htmlFor="purchase-supplier">Supplier</Form.Label>
              <Form.Select
                id="purchase-supplier"
                isInvalid={Boolean(errors.supplier_id)}
                {...register('supplier_id')}
              >
                <option value="">Choose an active supplier</option>
                {suppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name} ({supplier.code})
                  </option>
                ))}
              </Form.Select>
              {errors.supplier_id?.message && (
                <Form.Control.Feedback type="invalid">
                  {errors.supplier_id.message}
                </Form.Control.Feedback>
              )}
            </Form.Group>
          </div>
          <div className="col-12 col-md-6">
            <Form.Group>
              <Form.Label htmlFor="purchase-tax-rate">Tax rate (%)</Form.Label>
              <Form.Control
                id="purchase-tax-rate"
                isInvalid={Boolean(errors.tax_rate)}
                inputMode="decimal"
                {...register('tax_rate')}
              />
              {errors.tax_rate?.message && (
                <Form.Control.Feedback type="invalid">
                  {errors.tax_rate.message}
                </Form.Control.Feedback>
              )}
            </Form.Group>
          </div>
        </div>

        <div className="d-flex flex-wrap justify-content-between align-items-center gap-2 mt-4 mb-2">
          <h2 className="h4 mb-0">Items</h2>
          <Button
            onClick={() =>
              append({
                product_id: '',
                name: '',
                sku: '',
                quantity_ordered: 1,
                unit_cost: '',
              })
            }
            type="button"
            variant="outline-primary"
          >
            Add item
          </Button>
        </div>
        {fields.map((field, index) => {
          const itemErrors = errors.items?.[index] ?? {}
          return (
            <div className="border rounded p-3 mb-3" key={field.id}>
              <div className="row g-3 align-items-end">
                <div className="col-12 col-lg-5">
                  <PurchaseOrderProductPicker
                    index={index}
                    label={`${watchedItems[index]?.name ?? field.name} (${watchedItems[index]?.sku ?? field.sku})`}
                    onSelect={(product) => {
                      setValue(`items.${index}.product_id`, product.id, {
                        shouldValidate: true,
                      })
                      setValue(`items.${index}.name`, product.name)
                      setValue(`items.${index}.sku`, product.sku)
                      if (!watchedItems[index]?.unit_cost) {
                        setValue(`items.${index}.unit_cost`, product.cost_price, {
                          shouldValidate: true,
                        })
                      }
                    }}
                    value={watchedItems[index]?.product_id ?? ''}
                  />
                  <input
                    type="hidden"
                    {...register(`items.${index}.product_id`)}
                  />
                  {itemErrors.product_id?.message && (
                    <div className="text-danger small mt-1">
                      {itemErrors.product_id.message}
                    </div>
                  )}
                  {errors.items?.message && (
                    <div className="text-danger small mt-1">{errors.items.message}</div>
                  )}
                </div>
                <div className="col-6 col-lg-2">
                  <Form.Label htmlFor={`purchase-quantity-${index}`}>Quantity</Form.Label>
                  <Form.Control
                    id={`purchase-quantity-${index}`}
                    isInvalid={Boolean(itemErrors.quantity_ordered)}
                    min={1}
                    step={1}
                    type="number"
                    {...register(`items.${index}.quantity_ordered`, {
                      valueAsNumber: true,
                    })}
                  />
                  {itemErrors.quantity_ordered?.message && (
                    <div className="text-danger small mt-1">
                      {itemErrors.quantity_ordered.message}
                    </div>
                  )}
                </div>
                <div className="col-6 col-lg-3">
                  <Form.Label htmlFor={`purchase-cost-${index}`}>Unit cost</Form.Label>
                  <Form.Control
                    id={`purchase-cost-${index}`}
                    inputMode="decimal"
                    isInvalid={Boolean(itemErrors.unit_cost)}
                    {...register(`items.${index}.unit_cost`)}
                  />
                  {itemErrors.unit_cost?.message && (
                    <div className="text-danger small mt-1">
                      {itemErrors.unit_cost.message}
                    </div>
                  )}
                </div>
                <div className="col-12 col-lg-2">
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
        <div className="border rounded p-3 mb-3">
          <h2 className="h5">Estimated totals</h2>
          {preview ? (
            <dl className="row mb-2">
              <dt className="col-6">Subtotal</dt>
              <dd className="col-6 text-end">{formatMoney(preview.subtotal)}</dd>
              <dt className="col-6">Estimated tax</dt>
              <dd className="col-6 text-end">{formatMoney(preview.taxTotal)}</dd>
              <dt className="col-6">Estimated total</dt>
              <dd className="col-6 text-end fw-bold">{formatMoney(preview.grandTotal)}</dd>
            </dl>
          ) : (
            <p className="mb-2 text-muted">Enter valid quantities and unit costs to preview.</p>
          )}
          <p className="small text-muted mb-0">
            Preview only. The server calculates and stores the final totals.
          </p>
        </div>
        <div className="d-flex gap-2">
          <Button disabled={isSubmitting} type="submit">
            {isSubmitting
              ? 'Saving…'
              : editing
                ? 'Save draft'
                : 'Create draft'}
          </Button>
          <Button
            onClick={() =>
              navigate(
                purchaseOrderId
                  ? `/purchase-orders/${purchaseOrderId}`
                  : '/purchase-orders',
              )
            }
            type="button"
            variant="outline-secondary"
          >
            Cancel
          </Button>
        </div>
      </Form>
    </section>
  )
}
