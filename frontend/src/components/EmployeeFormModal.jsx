import { useEffect, useMemo, useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { listDepartments } from '../services/departmentService.js'
import { listDesignations } from '../services/employeeService.js'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import LoadingSpinner from './LoadingSpinner.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const phonePattern = /^\+?[0-9\s().-]+$/

const employeeSchema = yup.object({
  employee_code: yup
    .string()
    .trim()
    .required('Employee code is required.')
    .max(40, 'Employee code must be 40 characters or fewer.'),
  first_name: yup
    .string()
    .trim()
    .required('First name is required.')
    .max(100, 'First name must be 100 characters or fewer.'),
  last_name: yup
    .string()
    .trim()
    .required('Last name is required.')
    .max(100, 'Last name must be 100 characters or fewer.'),
  email: yup
    .string()
    .trim()
    .lowercase()
    .email('Enter a valid email address.')
    .required('Email is required.')
    .max(254, 'Email must be 254 characters or fewer.'),
  phone: yup
    .string()
    .transform((value) => (value === '' ? null : value?.trim()))
    .nullable()
    .notRequired()
    .max(30, 'Phone must be 30 characters or fewer.')
    .test(
      'phone-format',
      'Use 7 to 15 digits, with an optional leading + and common separators.',
      (value) => {
        if (!value) return true
        if (!phonePattern.test(value)) return false
        const digitCount = value.replace(/\D/g, '').length
        return digitCount >= 7 && digitCount <= 15
      },
    ),
  department_id: yup.string().required('Choose an active department.'),
  designation: yup
    .string()
    .trim()
    .required('Designation is required.')
    .max(100, 'Designation must be 100 characters or fewer.'),
  joining_date: yup
    .string()
    .required('Joining date is required.')
    .matches(/^\d{4}-\d{2}-\d{2}$/, 'Use a valid calendar date.')
    .test('not-future', 'Joining date cannot be in the future.', (value) => {
      if (!value || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return true
      const date = new Date(`${value}T00:00:00Z`)
      const normalizedDate = [
        date.getUTCFullYear(),
        String(date.getUTCMonth() + 1).padStart(2, '0'),
        String(date.getUTCDate()).padStart(2, '0'),
      ].join('-')
      return !Number.isNaN(date.getTime()) &&
        normalizedDate === value &&
        value <= new Date().toISOString().slice(0, 10)
    }),
  status: yup
    .string()
    .oneOf(['active', 'inactive', 'on_leave'])
    .required('Choose an employee status.'),
})

function getDefaultValues(employee) {
  return {
    employee_code: employee?.employee_code ?? '',
    first_name: employee?.first_name ?? '',
    last_name: employee?.last_name ?? '',
    email: employee?.email ?? '',
    phone: employee?.phone ?? '',
    department_id: employee?.department_id ?? '',
    designation: employee?.designation ?? '',
    joining_date: employee?.joining_date?.slice(0, 10) ?? '',
    status: employee?.status ?? 'active',
  }
}

/**
 * Create/edit employee form whose field limits mirror the backend serializer.
 *
 * @param {{show: boolean, employee?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function EmployeeFormModal({
  show,
  employee = null,
  onHide,
  onSave,
}) {
  const isEditing = Boolean(employee)
  const { showToast } = useToast()
  const [departments, setDepartments] = useState([])
  const [designations, setDesignations] = useState([])
  const [optionsLoading, setOptionsLoading] = useState(true)
  const [optionsError, setOptionsError] = useState('')
  const [serverError, setServerError] = useState('')
  const [formError, setFormError] = useState('')
  const designationListId = useMemo(
    () => `designation-options-${employee?.id ?? 'new'}`,
    [employee?.id],
  )
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(employeeSchema),
    defaultValues: getDefaultValues(employee),
  })

  useEffect(() => {
    if (!show) return undefined
    const controller = new AbortController()
    Promise.all([
      listDepartments(
        { page: 1, page_size: 100, is_active: true, sort_by: 'name' },
        { signal: controller.signal },
      ),
      listDesignations({ signal: controller.signal }),
    ])
      .then(([departmentResult, nextDesignations]) => {
        setDepartments(departmentResult.items)
        setDesignations(nextDesignations)
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setOptionsError(getApiError(error).message)
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setOptionsLoading(false)
      })

    return () => controller.abort()
  }, [employee, show])

  async function submit(values) {
    setServerError('')
    setFormError('')
    const payload = {
      ...values,
      employee_code: values.employee_code?.trim().toUpperCase(),
      email: values.email.trim().toLowerCase(),
      phone: values.phone || null,
      department_id: values.department_id,
      designation: values.designation.trim(),
    }
    if (isEditing) delete payload.employee_code

    try {
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setFormError(remaining.join(' '))
      showToast(apiError.message, 'danger', 'Unable to save employee')
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button
        disabled={isSubmitting || optionsLoading || Boolean(optionsError)}
        form="employee-form"
        type="submit"
        variant="primary"
      >
        {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create employee'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      size="lg"
      title={isEditing ? 'Edit employee' : 'Create employee'}
    >
      <ErrorMessage message={serverError} />
      <ErrorMessage message={formError} title="Additional validation details" />
      <ErrorMessage message={optionsError} title="Could not load form options" />
      {optionsLoading ? (
        <div className="text-center py-4">
          <LoadingSpinner label="Loading employee form options" />
        </div>
      ) : (
        <Form id="employee-form" noValidate onSubmit={handleSubmit(submit)}>
          <div className="row">
            {!isEditing && (
              <div className="col-md-6">
                <FormInput
                  error={errors.employee_code}
                  label="Employee code"
                  name="employee_code"
                  registerProps={register('employee_code')}
                />
              </div>
            )}
            <div className="col-md-6">
              <FormInput
                autoComplete="given-name"
                error={errors.first_name}
                label="First name"
                name="first_name"
                registerProps={register('first_name')}
              />
            </div>
            <div className="col-md-6">
              <FormInput
                autoComplete="family-name"
                error={errors.last_name}
                label="Last name"
                name="last_name"
                registerProps={register('last_name')}
              />
            </div>
            <div className="col-md-6">
              <FormInput
                autoComplete="email"
                error={errors.email}
                label="Email"
                name="email"
                registerProps={register('email')}
                type="email"
              />
            </div>
            <div className="col-md-6">
              <FormInput
                autoComplete="tel"
                error={errors.phone}
                hint="7 to 15 digits; a leading + and common separators are accepted."
                label="Phone (optional)"
                name="phone"
                registerProps={register('phone')}
                type="tel"
              />
            </div>
            <div className="col-md-6">
              <Form.Group className="mb-3">
                <Form.Label htmlFor="department_id">Department</Form.Label>
                <Form.Select
                  aria-describedby={
                    errors.department_id ? 'department_id-feedback' : undefined
                  }
                  aria-invalid={Boolean(errors.department_id)}
                  id="department_id"
                  isInvalid={Boolean(errors.department_id)}
                  {...register('department_id')}
                >
                  <option value="">Choose an active department</option>
                  {departments.map((department) => (
                    <option key={department.id} value={department.id}>
                      {department.name} ({department.code})
                    </option>
                  ))}
                </Form.Select>
                {errors.department_id?.message && (
                  <Form.Control.Feedback
                    id="department_id-feedback"
                    type="invalid"
                  >
                    {errors.department_id.message}
                  </Form.Control.Feedback>
                )}
              </Form.Group>
            </div>
            <div className="col-md-6">
              <FormInput
                error={errors.designation}
                label="Designation"
                name="designation"
                registerProps={register('designation')}
                list={designationListId}
              />
              <datalist id={designationListId}>
                {designations.map((designation) => (
                  <option key={designation} value={designation} />
                ))}
              </datalist>
            </div>
            <div className="col-md-6">
              <FormInput
                error={errors.joining_date}
                label="Joining date"
                name="joining_date"
                registerProps={register('joining_date')}
                type="date"
              />
            </div>
            <div className="col-md-6">
              <Form.Group className="mb-3">
                <Form.Label htmlFor="employee-status">Status</Form.Label>
                <Form.Select
                  aria-invalid={Boolean(errors.status)}
                  id="employee-status"
                  isInvalid={Boolean(errors.status)}
                  {...register('status')}
                >
                  <option value="active">Active</option>
                  <option value="on_leave">On leave</option>
                  {employee?.status === 'inactive' && (
                    <option disabled value="inactive">Inactive</option>
                  )}
                </Form.Select>
                {errors.status?.message && (
                  <Form.Control.Feedback type="invalid">
                    {errors.status.message}
                  </Form.Control.Feedback>
                )}
              </Form.Group>
            </div>
          </div>
        </Form>
      )}
    </ModalWrapper>
  )
}
