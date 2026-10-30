import { useEffect, useMemo, useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import { listEmployees } from '../services/employeeService.js'
import { useToast } from '../hooks/useToast.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import { isCommonPassword } from '../utils/passwordStrength.js'
import ErrorMessage from './ErrorMessage.jsx'
import FormInput from './FormInput.jsx'
import ModalWrapper from './ModalWrapper.jsx'

const roles = [
  ['super_admin', 'Super Admin'],
  ['hr_manager', 'HR Manager'],
  ['inventory_manager', 'Inventory Manager'],
  ['purchase_manager', 'Purchase Manager'],
  ['sales_manager', 'Sales Manager'],
  ['employee', 'Employee'],
]

function getUserSchema(isEditing) {
  return yup.object({
    email: yup
      .string()
      .trim()
      .lowercase()
      .email('Enter a valid email address.')
      .required('Email is required.')
      .max(254, 'Email must be 254 characters or fewer.'),
    full_name: yup
      .string()
      .trim()
      .required('Full name is required.')
      .max(200, 'Full name must be 200 characters or fewer.'),
    role: yup.string().oneOf(roles.map(([role]) => role)).required('Select a role.'),
    employee_id: yup.string().nullable(),
    ...(isEditing
      ? {}
      : {
          password: yup
            .string()
            .required('Password is required.')
            .min(10, 'Password must contain at least 10 characters.')
            .test(
              'not-email',
              'Password must not be the same as the email address.',
              (password, context) =>
                !password ||
                password.toLowerCase() !==
                  String(context.parent.email ?? '').trim().toLowerCase(),
            )
            .test(
              'not-common',
              'Choose a password that is not commonly used.',
              (password) => !password || !isCommonPassword(password),
            ),
        }),
  })
}

function getDefaultValues(user) {
  return {
    email: user?.email ?? '',
    full_name: user?.full_name ?? '',
    role: user?.role ?? 'employee',
    employee_id: user?.employee_id ?? '',
    password: '',
  }
}

/**
 * Create or edit an account, with an optional link to an employee record.
 *
 * @param {{show: boolean, user?: object | null, onHide: () => void, onSave: (values: object) => Promise<void>}} props
 */
export default function UserFormModal({
  show,
  user = null,
  onHide,
  onSave,
}) {
  const isEditing = Boolean(user)
  const { showToast } = useToast()
  const [employees, setEmployees] = useState([])
  const [employeeLoadError, setEmployeeLoadError] = useState('')
  const [serverError, setServerError] = useState('')
  const [formError, setFormError] = useState('')
  const schema = useMemo(() => getUserSchema(isEditing), [isEditing])
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: getDefaultValues(user),
  })

  useEffect(() => {
    if (!show) return undefined
    const controller = new AbortController()
    listEmployees({ page: 1, page_size: 100 }, { signal: controller.signal })
      .then(({ items }) => setEmployees(items))
      .catch((error) => {
        if (!controller.signal.aborted) {
          setEmployeeLoadError(getApiError(error).message)
        }
      })
    return () => controller.abort()
  }, [show])

  async function submit(values) {
    setServerError('')
    setFormError('')
    const payload = {
      ...values,
      email: values.email.trim().toLowerCase(),
      full_name: values.full_name.trim(),
      employee_id: values.employee_id || null,
    }
    if (isEditing) delete payload.password

    try {
      await onSave(payload)
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setFormError(remaining.join(' '))
      showToast(apiError.message, 'danger', 'Unable to save user')
    }
  }

  const footer = (
    <>
      <Button disabled={isSubmitting} onClick={onHide} variant="outline-secondary">
        Cancel
      </Button>
      <Button
        disabled={isSubmitting}
        form="user-form"
        type="submit"
        variant="primary"
      >
        {isSubmitting ? 'Saving…' : isEditing ? 'Save changes' : 'Create user'}
      </Button>
    </>
  )

  return (
    <ModalWrapper
      footer={footer}
      onHide={onHide}
      show={show}
      title={isEditing ? 'Edit user' : 'Create user'}
    >
      <ErrorMessage message={serverError} />
      <ErrorMessage message={formError} title="Additional validation details" />
      <ErrorMessage
        message={employeeLoadError}
        title="Could not load employee options"
      />
      <Form id="user-form" noValidate onSubmit={handleSubmit(submit)}>
        <FormInput
          autoComplete="email"
          error={errors.email}
          label="Email"
          name="email"
          registerProps={register('email')}
          type="email"
        />
        <FormInput
          autoComplete="name"
          error={errors.full_name}
          label="Full name"
          name="full_name"
          registerProps={register('full_name')}
        />
        {!isEditing && (
          <FormInput
            autoComplete="new-password"
            error={errors.password}
            hint="Use at least 10 characters. Avoid the account email and common passwords."
            label="Temporary password"
            name="password"
            registerProps={register('password')}
            type="password"
          />
        )}
        <Form.Group className="mb-3">
          <Form.Label htmlFor="user-role">Role</Form.Label>
          <Form.Select
            aria-invalid={Boolean(errors.role)}
            id="user-role"
            isInvalid={Boolean(errors.role)}
            {...register('role')}
          >
            {roles.map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </Form.Select>
          {errors.role?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.role.message}
            </Form.Control.Feedback>
          )}
        </Form.Group>
        <Form.Group className="mb-3">
          <Form.Label htmlFor="user-employee">Employee link (optional)</Form.Label>
          <Form.Select
            aria-invalid={Boolean(errors.employee_id)}
            id="user-employee"
            isInvalid={Boolean(errors.employee_id)}
            {...register('employee_id')}
          >
            <option value="">No employee linked</option>
            {employees.map((employee) => (
              <option key={employee.id} value={employee.id}>
                {employee.first_name} {employee.last_name} ({employee.employee_code})
              </option>
            ))}
          </Form.Select>
          {errors.employee_id?.message && (
            <Form.Control.Feedback type="invalid">
              {errors.employee_id.message}
            </Form.Control.Feedback>
          )}
          <Form.Text className="text-muted">
            The list shows up to 100 employee records.
          </Form.Text>
        </Form.Group>
      </Form>
    </ModalWrapper>
  )
}
