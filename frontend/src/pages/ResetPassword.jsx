import { useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Alert from 'react-bootstrap/Alert'
import Button from 'react-bootstrap/Button'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'
import * as yup from 'yup'
import ErrorMessage from '../components/ErrorMessage.jsx'
import FormInput from '../components/FormInput.jsx'
import { confirmPasswordReset } from '../services/authService.js'
import { applyApiFieldErrors, getApiError } from '../utils/apiErrors.js'
import { isCommonPassword } from '../utils/passwordStrength.js'

const schema = yup.object({
  email: yup
    .string()
    .trim()
    .lowercase()
    .email('Enter a valid email address.')
    .required('Email is required.'),
  password: yup
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
    ),
  confirm_password: yup
    .string()
    .required('Confirm your new password.')
    .oneOf([yup.ref('password')], 'Passwords do not match.'),
})

/**
 * Completes the single-use password reset using the token in the URL query.
 *
 * @returns {JSX.Element}
 */
export default function ResetPassword() {
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const token = searchParams.get('token') ?? ''
  const [serverError, setServerError] = useState('')
  const [formError, setFormError] = useState('')
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(schema),
    defaultValues: {
      email: searchParams.get('email') ?? '',
      password: '',
      confirm_password: '',
    },
  })

  async function submit(values) {
    setServerError('')
    setFormError('')
    try {
      await confirmPasswordReset({ ...values, token })
      navigate('/login', {
        replace: true,
        state: { successMessage: 'Your password was reset. Sign in with your new password.' },
      })
    } catch (error) {
      const apiError = getApiError(error)
      const remaining = applyApiFieldErrors(apiError.details, setError)
      setServerError(apiError.message)
      setFormError(remaining.join(' '))
    }
  }

  return (
    <section aria-labelledby="reset-password-title" className="card auth-card border-0">
      <div className="card-body p-4 p-md-5">
        <p className="text-primary text-uppercase fw-bold small mb-2">Account recovery</p>
        <h1 className="h3 mb-2" id="reset-password-title">Set a new password</h1>
        {!token ? (
          <>
            <Alert variant="warning">
              This reset link is incomplete. Request a new link to continue.
            </Alert>
            <Link to="/forgot-password">Request another reset link</Link>
          </>
        ) : (
          <form noValidate onSubmit={handleSubmit(submit)}>
            <ErrorMessage message={serverError} />
            <ErrorMessage message={formError} title="Additional validation details" />
            <FormInput
              autoComplete="email"
              error={errors.email}
              label="Email"
              name="email"
              registerProps={register('email')}
              type="email"
            />
            <FormInput
              autoComplete="new-password"
              error={errors.password}
              hint="Use at least 10 characters. Avoid the account email and common passwords."
              label="New password"
              name="password"
              registerProps={register('password')}
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
            <Button className="w-100" disabled={isSubmitting} type="submit">
              {isSubmitting ? 'Saving…' : 'Reset password'}
            </Button>
          </form>
        )}
      </div>
    </section>
  )
}
