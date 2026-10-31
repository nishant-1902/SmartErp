import { useEffect } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import FormInput from './FormInput.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const moneyPattern = /^\d{1,16}(?:\.\d{1,2})?$/
function createProductSchema(isEditing) {
  return yup.object({
    ...(isEditing
      ? {}
      : {
          sku: yup
            .string()
            .trim()
            .required('SKU is required.')
            .max(64, 'SKU must be 64 characters or fewer.'),
        }),
    name: yup
      .string()
      .trim()
      .required('Product name is required.')
      .max(200, 'Product name must be 200 characters or fewer.'),
    description: yup
      .string()
      .nullable()
      .max(2000, 'Description must be 2000 characters or fewer.'),
    category: yup
      .string()
      .trim()
      .required('Category is required.')
      .max(100, 'Category must be 100 characters or fewer.'),
    unit: yup
      .string()
      .trim()
      .required('Unit is required.')
      .max(30, 'Unit must be 30 characters or fewer.'),
    cost_price: yup
      .string()
      .required('Cost price is required.')
      .matches(moneyPattern, 'Enter a positive amount with up to two decimals.')
      .test('positive', 'Cost price must be greater than zero.', (value) => {
        if (!value || !moneyPattern.test(value)) return true
        return BigInt(value.replace('.', '').replace(/^0+/, '') || '0') > 0n
      }),
    selling_price: yup
      .string()
      .required('Selling price is required.')
      .matches(moneyPattern, 'Enter a positive amount with up to two decimals.')
      .test('positive', 'Selling price must be greater than zero.', (value) => {
        if (!value || !moneyPattern.test(value)) return true
        return BigInt(value.replace('.', '').replace(/^0+/, '') || '0') > 0n
      }),
    min_stock_level: yup
      .number()
      .typeError('Minimum stock level must be a whole number.')
      .integer('Minimum stock level must be a whole number.')
      .min(0, 'Minimum stock level cannot be negative.')
      .required('Minimum stock level is required.'),
    is_active: yup.boolean().required(),
  })
}

function getDefaultValues(product) {
  return {
    sku: product?.sku ?? '',
    name: product?.name ?? '',
    description: product?.description ?? '',
    category: product?.category ?? '',
    unit: product?.unit ?? '',
    cost_price: product?.cost_price ?? '',
    selling_price: product?.selling_price ?? '',
    min_stock_level: product?.min_stock_level ?? 0,
    is_active: product?.is_active ?? true,
  }
}

/**
 * Create or edit product details without exposing stock quantity inputs.
 *
 * @param {{show: boolean, product?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function ProductFormModal({
  show,
  product = null,
  onHide,
  onSave,
}) {
  const isEditing = Boolean(product)
  const { showToast } = useToast()
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(createProductSchema(isEditing)),
    defaultValues: getDefaultValues(product),
  })

  useEffect(() => {
    if (show) reset(getDefaultValues(product))
  }, [product, reset, show])

  async function submit(values) {
    try {
      const { sku, ...editableValues } = values
      const payload = {
        ...editableValues,
        ...(!isEditing ? { sku: sku.trim().toUpperCase() } : {}),
        description: editableValues.description?.trim() || null,
        category: editableValues.category.trim(),
        unit: editableValues.unit.trim(),
      }
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      showToast(
        [apiError.message, ...remaining].join(' '),
        'danger',
        'Unable to save product',
      )
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button disabled={isSubmitting} form="product-form" type="submit">
        {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create product'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={isEditing ? 'Edit product' : 'Create product'}
    >
      <Form id="product-form" noValidate onSubmit={handleSubmit(submit)}>
        {!isEditing && (
          <FormInput
            autoComplete="off"
            error={errors.sku}
            label="SKU"
            name="sku"
            registerProps={register('sku')}
            hint="SKU is saved in uppercase and cannot be changed later."
          />
        )}
        {isEditing && (
          <Form.Group className="mb-3">
            <Form.Label htmlFor="product-sku">SKU</Form.Label>
            <Form.Control id="product-sku" readOnly value={product.sku} />
          </Form.Group>
        )}
        <FormInput
          error={errors.name}
          label="Product name"
          name="name"
          registerProps={register('name')}
        />
        <Form.Group className="mb-3">
          <Form.Label htmlFor="product-description">Description</Form.Label>
          <Form.Control
            as="textarea"
            id="product-description"
            isInvalid={Boolean(errors.description)}
            maxLength={2000}
            rows={2}
            {...register('description')}
          />
          {errors.description?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.description.message}
            </Form.Control.Feedback>
          )}
        </Form.Group>
        <div className="row">
          <div className="col-md-6">
            <FormInput
              error={errors.category}
              label="Category"
              name="category"
              registerProps={register('category')}
            />
          </div>
          <div className="col-md-6">
            <FormInput
              error={errors.unit}
              label="Unit"
              name="unit"
              registerProps={register('unit')}
            />
          </div>
        </div>
        <div className="row">
          <div className="col-md-6">
            <FormInput
              error={errors.cost_price}
              inputMode="decimal"
              label="Cost price"
              name="cost_price"
              registerProps={register('cost_price')}
            />
          </div>
          <div className="col-md-6">
            <FormInput
              error={errors.selling_price}
              inputMode="decimal"
              label="Selling price"
              name="selling_price"
              registerProps={register('selling_price')}
            />
          </div>
        </div>
        <FormInput
          error={errors.min_stock_level}
          label="Minimum stock level"
          min="0"
          name="min_stock_level"
          registerProps={register('min_stock_level', { valueAsNumber: true })}
          type="number"
        />
        <Form.Check
          id="product-active"
          label="Product is active"
          type="checkbox"
          {...register('is_active')}
        />
      </Form>
    </ModalWrapper>
  )
}
