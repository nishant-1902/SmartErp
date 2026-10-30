import { useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import * as yup from 'yup'
import CurrentUserDetails from '../components/CurrentUserDetails.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import FormInput from '../components/FormInput.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'
import { changePassword } from '../services/authService.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import { isCommonPassword } from '../utils/passwordStrength.js'

const passwordSchema = yup
  .string()
  .required('New password is required.')
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
  )

/**
 * Shows account information and lets the signed-in user change their password.
 *
 * @returns {JSX.Element}
 */
export default function Settings() {
  const { user, logoutLocally } = useAuth()
  const { showToast } = useToast()
  const [serverError, setServerError] = useState('')
  const [formError, setFormError] = useState('')
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(
      yup.object({
        old_password: yup.string().required('Current password is required.'),
        new_password: passwordSchema,
        email: yup.string().email(),
        confirm_password: yup
          .string()
          .required('Confirm your new password.')
          .oneOf([yup.ref('new_password')], 'Passwords do not match.'),
      }),
    ),
    defaultValues: {
      email: user.email,
      old_password: '',
      new_password: '',
      confirm_password: '',
    },
  })

  async function submit(values) {
    setServerError('')
    setFormError('')
    try {
      await changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
        confirm_password: values.confirm_password,
      })
      logoutLocally({
        successMessage: 'Your password was changed. Please sign in again.',
      })
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setFormError(remaining.join(' '))
      showToast(apiError.message, 'danger', 'Unable to change password')
    }
  }

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Account</p>
        <h1>Settings</h1>
        <p className="mb-0">Review your account and update your password.</p>
      </div>
      <div className="row g-4">
        <div className="col-12 col-xl-6">
          <CurrentUserDetails user={user} />
        </div>
        <div className="col-12 col-xl-6">
          <div className="surface-card bg-white p-4">
            <h2 className="h5 mb-3">Change password</h2>
            <p className="small text-muted">
              Use at least 10 characters. Your password must not match your email
              or be commonly used. Changing it signs out every session.
            </p>
            <ErrorMessage message={serverError} />
            <ErrorMessage message={formError} title="Additional validation details" />
            <Form noValidate onSubmit={handleSubmit(submit)}>
              <Form.Control type="hidden" {...register('email')} />
              <FormInput
                autoComplete="current-password"
                error={errors.old_password}
                label="Current password"
                name="old_password"
                registerProps={register('old_password')}
                type="password"
              />
              <FormInput
                autoComplete="new-password"
                error={errors.new_password}
                label="New password"
                name="new_password"
                registerProps={register('new_password')}
                type="password"
              />
              <FormInput
                autoComplete="new-password"
                error={errors.confirm_password}
                label="Confirm new password"
                name="confirm_password"
                registerProps={register('confirm_password')}
                type="password"
              />
              <Button disabled={isSubmitting} type="submit" variant="primary">
                {isSubmitting ? 'Saving…' : 'Change password'}
              </Button>
            </Form>
          </div>
        </div>
      </div>
    </section>
  )
}
