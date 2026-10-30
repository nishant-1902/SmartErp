import { StrictMode } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthContext.jsx'
import { ProtectedRoute } from '../components/ProtectedRoute.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { getAccessToken } from '../services/apiClient.js'

const authService = vi.hoisted(() => ({
  fetchCurrentUser: vi.fn(),
  login: vi.fn(),
  logout: vi.fn(),
  refreshSession: vi.fn(),
}))

vi.mock('../services/authService.js', () => authService)

function AuthStatus() {
  const { loading, user, role, permissions, hasPermission } = useAuth()
  if (loading) {
    return <p role="status">Loading session</p>
  }
  return (
    <div>
      <p>{user ? user.email : 'Signed out'}</p>
      <p>{role}</p>
      <p>{permissions.join(',')}</p>
      <p>{String(hasPermission('employees:read'))}</p>
    </div>
  )
}

function LoginAction() {
  const { login } = useAuth()
  return (
    <button onClick={() => login('new@example.test', 'password')}>
      Log in
    </button>
  )
}

function renderProvider(children = <AuthStatus />) {
  return render(
    <StrictMode>
      <MemoryRouter initialEntries={['/']}>
        <AuthProvider>{children}</AuthProvider>
      </MemoryRouter>
    </StrictMode>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
})

describe('AuthProvider', () => {
  it('restores a session through one refresh under React StrictMode', async () => {
    authService.refreshSession.mockResolvedValue({
      access_token: 'restored-token',
    })
    authService.fetchCurrentUser.mockResolvedValue({
      id: 'user-1',
      email: 'hr@example.test',
      role: 'hr_manager',
      permissions: ['employees:read', 'employees:write'],
    })

    renderProvider()

    expect(await screen.findByText('hr@example.test')).toBeInTheDocument()
    expect(authService.refreshSession).toHaveBeenCalledOnce()
    expect(authService.fetchCurrentUser).toHaveBeenCalledOnce()
    expect(getAccessToken()).toBe('restored-token')
    expect(screen.getByText('true')).toBeInTheDocument()
  })

  it('shows signed out after silent restore fails without redirecting', async () => {
    authService.refreshSession.mockRejectedValue(new Error('No refresh cookie'))

    renderProvider()

    expect(await screen.findByText('Signed out')).toBeInTheDocument()
    expect(authService.refreshSession).toHaveBeenCalledOnce()
    expect(authService.fetchCurrentUser).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).not.toBeInTheDocument()
  })

  it('redirects protected content to login after silent restore failure', async () => {
    authService.refreshSession.mockRejectedValue(new Error('No refresh cookie'))

    render(
      <StrictMode>
        <MemoryRouter initialEntries={['/']}>
          <AuthProvider>
            <Routes>
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <p>Private page</p>
                  </ProtectedRoute>
                }
              />
              <Route path="/login" element={<p>Login page</p>} />
            </Routes>
          </AuthProvider>
        </MemoryRouter>
      </StrictMode>,
    )

    await waitFor(() => {
      expect(screen.getByText('Login page')).toBeInTheDocument()
    })
    expect(screen.queryByText('Private page')).not.toBeInTheDocument()
  })

  it('stores the login token and exposes backend permissions in context', async () => {
    authService.refreshSession.mockRejectedValue(new Error('No refresh cookie'))
    authService.login.mockResolvedValue({
      access_token: 'login-token',
      user: {
        id: 'user-2',
        email: 'new@example.test',
        role: 'hr_manager',
        permissions: ['employees:read'],
      },
    })

    renderProvider(
      <>
        <AuthStatus />
        <LoginAction />
      </>,
    )
    await screen.findByText('Signed out')
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))

    expect(await screen.findByText('new@example.test')).toBeInTheDocument()
    expect(getAccessToken()).toBe('login-token')
    expect(authService.login).toHaveBeenCalledWith(
      'new@example.test',
      'password',
    )
  })
})
