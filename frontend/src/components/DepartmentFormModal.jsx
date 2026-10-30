import { useEffect, useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { listEmployees } from '../services/employeeService.js'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import LoadingSpinner from './LoadingSpinner.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const departmentSchema = yup.object({
  code: yup
    .string()
    .trim()
    .required('Department code is required.')
    .max(40, 'Department code must be 40 characters or fewer.'),
  name: yup
    .string()
    .trim()
    .required('Department name is required.')
    .max(120, 'Department name must be 120 characters or fewer.'),
  description: yup
    .string()
    .nullable()
    .max(2000, 'Description must be 2000 characters or fewer.'),
  manager_employee_id: yup.string().nullable(),
  is_active: yup.boolean().required(),
})

function getDefaultValues(department) {
  return {
    code: department?.code ?? '',
    name: department?.name ?? '',
    description: department?.description ?? '',
    manager_employee_id: department?.manager_employee_id ?? '',
    is_active: department?.is_active ?? true,
  }
}

/**
 * Create/edit department form with an active-employee manager selector.
 *
 * @param {{show: boolean, department?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function DepartmentFormModal({
  show,
  department = null,
  onHide,
  onSave,
}) {
  const isEditing = Boolean(department)
  const { showToast } = useToast()
  const [managers, setManagers] = useState([])
  const [optionsLoading, setOptionsLoading] = useState(true)
  const [optionsError, setOptionsError] = useState('')
  const [serverError, setServerError] = useState('')
  const [formError, setFormError] = useState('')
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(departmentSchema),
    defaultValues: getDefaultValues(department),
  })

  useEffect(() => {
    if (!show) return undefined
    const controller = new AbortController()
    listEmployees(
      { page: 1, page_size: 100, status: 'active', sort_by: 'first_name' },
      { signal: controller.signal },
    )
      .then(({ items }) => setManagers(items))
      .catch((error) => {
        if (!controller.signal.aborted) setOptionsError(getApiError(error).message)
      })
      .finally(() => {
        if (!controller.signal.aborted) setOptionsLoading(false)
      })

    return () => controller.abort()
  }, [department, show])

  async function submit(values) {
    setServerError('')
    setFormError('')
    const payload = {
      ...values,
      code: values.code.trim().toUpperCase(),
      name: values.name.trim(),
      description: values.description || null,
      manager_employee_id: values.manager_employee_id || null,
    }

    try {
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setFormError(remaining.join(' '))
      showToast(apiError.message, 'danger', 'Unable to save department')
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button
        disabled={isSubmitting || optionsLoading || Boolean(optionsError)}
        form="department-form"
        type="submit"
        variant="primary"
      >
        {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create department'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={isEditing ? 'Edit department' : 'Create department'}
    >
      <ErrorMessage message={serverError} />
      <ErrorMessage message={formError} title="Additional validation details" />
      <ErrorMessage message={optionsError} title="Could not load manager options" />
      {optionsLoading ? (
        <div className="text-center py-4">
          <LoadingSpinner label="Loading active employees" />
        </div>
      ) : (
        <Form id="department-form" noValidate onSubmit={handleSubmit(submit)}>
          <FormInput
            error={errors.code}
            label="Department code"
            name="code"
            registerProps={register('code')}
          />
          <FormInput
            error={errors.name}
            label="Department name"
            name="name"
            registerProps={register('name')}
          />
          <Form.Group className="mb-3">
            <Form.Label htmlFor="department-description">Description</Form.Label>
            <Form.Control
              as="textarea"
              id="department-description"
              isInvalid={Boolean(errors.description)}
              maxLength={2000}
              rows={3}
              {...register('description')}
            />
            {errors.description?.message && (
              <Form.Control.Feedback type="invalid">
                {errors.description.message}
              </Form.Control.Feedback>
            )}
          </Form.Group>
          <Form.Group className="mb-3">
            <Form.Label htmlFor="manager_employee_id">Manager (optional)</Form.Label>
            <Form.Select
              aria-invalid={Boolean(errors.manager_employee_id)}
              id="manager_employee_id"
              isInvalid={Boolean(errors.manager_employee_id)}
              {...register('manager_employee_id')}
            >
              <option value="">No manager assigned</option>
              {managers.map((manager) => (
                <option key={manager.id} value={manager.id}>
                  {manager.first_name} {manager.last_name} ({manager.employee_code})
                </option>
              ))}
            </Form.Select>
            {errors.manager_employee_id?.message && (
              <Form.Control.Feedback type="invalid">
                {errors.manager_employee_id.message}
              </Form.Control.Feedback>
            )}
            <Form.Text className="text-muted">
              Only active employees can manage a department.
            </Form.Text>
          </Form.Group>
          <Form.Check
            id="department-active"
            label="Department is active"
            type="checkbox"
            {...register('is_active')}
          />
        </Form>
      )}
    </ModalWrapper>
  )
}
