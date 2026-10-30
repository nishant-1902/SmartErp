import { useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import Alert from 'react-bootstrap/Alert'
import Button from 'react-bootstrap/Button'
import { Link } from 'react-router-dom'
import * as yup from 'yup'
import ErrorMessage from '../components/ErrorMessage.jsx'
import FormInput from '../components/FormInput.jsx'
import { requestPasswordReset } from '../services/authService.js'
import { getApiError } from '../utils/apiErrors.js'

const emailSchema = yup.object({
  email: yup
    .string()
    .trim()
    .lowercase()
    .email('Enter a valid email address.')
    .required('Email is required.'),
})

/**
 * Starts the public password-reset flow without revealing whether an email exists.
 *
 * @returns {JSX.Element}
 */
export default function ForgotPassword() {
  const [serverError, setServerError] = useState('')
  const [requestSent, setRequestSent] = useState(false)
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(emailSchema),
    defaultValues: { email: '' },
  })

  async function submit({ email }) {
    setServerError('')
    setRequestSent(false)
    try {
      await requestPasswordReset(email)
      setRequestSent(true)
    } catch (error) {
      setServerError(getApiError(error).message)
    }
  }

  return (
    <section aria-labelledby="forgot-password-title" className="card auth-card border-0">
      <div className="card-body p-4 p-md-5">
        <p className="text-primary text-uppercase fw-bold small mb-2">Account recovery</p>
        <h1 className="h3 mb-2" id="forgot-password-title">Forgot password?</h1>
        <p className="text-muted mb-4">
          Enter your work email to request a password-reset link.
        </p>
        {requestSent && (
          <Alert role="status" variant="success">
            If an account matches this email, a password reset link has been generated.
          </Alert>
        )}
        <ErrorMessage message={serverError} />
        <form noValidate onSubmit={handleSubmit(submit)}>
          <FormInput
            autoComplete="email"
            error={errors.email}
            label="Email"
            name="email"
            placeholder="you@company.com"
            registerProps={register('email')}
            type="email"
          />
          <Button className="w-100" disabled={isSubmitting} type="submit">
            {isSubmitting ? 'Requesting…' : 'Request reset link'}
          </Button>
        </form>
        <p className="mt-3 mb-0 text-center">
          <Link to="/login">Back to sign in</Link>
        </p>
      </div>
    </section>
  )
}
