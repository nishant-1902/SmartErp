import { useState } from 'react'
import { yupResolver } from '@hookform/resolvers/yup'
import { useForm } from 'react-hook-form'
import { Navigate, useNavigate } from 'react-router-dom'
import * as yup from 'yup'
import ErrorMessage from '../components/ErrorMessage.jsx'
import FormInput from '../components/FormInput.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import { useAuth } from '../hooks/useAuth.js'

const loginSchema = yup.object({
  email: yup
    .string()
    .trim()
    .lowercase()
    .email('Enter a valid email address.')
    .required('Email is required.'),
  password: yup.string().required('Password is required.'),
})

const genericLoginError =
  'Unable to sign in. Check your email and password, then try again.'

/**
 * Validates credentials with React Hook Form and shows generic auth errors.
 *
 * @returns {JSX.Element}
 */
export default function Login() {
  const { login, loading, user } = useAuth()
  const navigate = useNavigate()
  const [authError, setAuthError] = useState('')
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm({
    resolver: yupResolver(loginSchema),
    defaultValues: { email: '', password: '' },
  })

  if (loading) {
    return (
      <div className="text-center py-5">
        <LoadingSpinner label="Checking your session" />
      </div>
    )
  }
  if (user) {
    return <Navigate replace to="/" />
  }

  async function submitCredentials(values) {
    setAuthError('')
    try {
      await login(values.email, values.password)
      navigate('/', { replace: true })
    } catch {
      setAuthError(genericLoginError)
    }
  }

  return (
    <section aria-labelledby="login-title" className="card auth-card border-0">
      <div className="card-body p-4 p-md-5">
        <p className="text-primary text-uppercase fw-bold small mb-2">Welcome back</p>
        <h1 className="h3 mb-2" id="login-title">Sign in to SmartERP</h1>
        <p className="text-muted mb-4">Use your work account to continue.</p>
        <ErrorMessage message={authError} />
        <form noValidate onSubmit={handleSubmit(submitCredentials)}>
          <FormInput
            autoComplete="username"
            error={errors.email}
            label="Email"
            name="email"
            placeholder="you@company.com"
            registerProps={register('email')}
            type="email"
          />
          <FormInput
            autoComplete="current-password"
            error={errors.password}
            label="Password"
            name="password"
            registerProps={register('password')}
            type="password"
          />
          <button
            className="btn btn-primary w-100 mt-2 py-2"
            disabled={isSubmitting || loading}
            type="submit"
          >
            {isSubmitting ? (
              <span className="d-inline-flex align-items-center gap-2">
                <LoadingSpinner label="Signing in" size="sm" />
                Signing in…
              </span>
            ) : (
              'Sign in'
            )}
          </button>
        </form>
      </div>
    </section>
  )
}
