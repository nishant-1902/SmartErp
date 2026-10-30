import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.js'

function getErrorMessage(error) {
  return (
    error.response?.data?.error?.message ??
    'Unable to sign in. Check your email and password, then try again.'
  )
}

function Login() {
  const { login, loading, user } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errorMessage, setErrorMessage] = useState('')
  const [submitting, setSubmitting] = useState(false)

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setErrorMessage('')
    setSubmitting(true)
    try {
      await login(email, password)
      navigate('/', { replace: true })
    } catch (error) {
      setErrorMessage(getErrorMessage(error))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <main className="container py-5">
      <div className="row justify-content-center">
        <div className="col-12 col-md-7 col-lg-5">
          <section className="card border-0 shadow-sm">
            <div className="card-body p-4 p-md-5">
              <p className="text-uppercase text-primary fw-semibold mb-2">
                SmartERP
              </p>
              <h1 className="h3 mb-4">Sign in</h1>
              <form onSubmit={handleSubmit}>
                <div className="mb-3">
                  <label className="form-label" htmlFor="email">
                    Email
                  </label>
                  <input
                    autoComplete="username"
                    className="form-control"
                    id="email"
                    onChange={(event) => setEmail(event.target.value)}
                    required
                    type="email"
                    value={email}
                  />
                </div>
                <div className="mb-3">
                  <label className="form-label" htmlFor="password">
                    Password
                  </label>
                  <input
                    autoComplete="current-password"
                    className="form-control"
                    id="password"
                    onChange={(event) => setPassword(event.target.value)}
                    required
                    type="password"
                    value={password}
                  />
                </div>
                {errorMessage && (
                  <p className="alert alert-danger" role="alert">
                    {errorMessage}
                  </p>
                )}
                <button
                  className="btn btn-primary w-100"
                  disabled={submitting || loading}
                  type="submit"
                >
                  {submitting ? 'Signing in…' : 'Sign in'}
                </button>
              </form>
            </div>
          </section>
        </div>
      </div>
    </main>
  )
}

export default Login
