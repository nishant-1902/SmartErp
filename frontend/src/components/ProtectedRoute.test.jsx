import { cleanup, render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ProtectedRoute, RoleRoute } from './ProtectedRoute.jsx'

const { useAuthMock } = vi.hoisted(() => ({
  useAuthMock: vi.fn(),
}))

vi.mock('../hooks/useAuth.js', () => ({
  useAuth: useAuthMock,
}))

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function renderProtectedRoute(auth, guard = <ProtectedRoute />) {
  useAuthMock.mockReturnValue(auth)
  return render(
    <MemoryRouter
      future={{
        v7_relativeSplatPath: true,
        v7_startTransition: true,
      }}
      initialEntries={['/private']}
    >
      <Routes>
        <Route element={guard} path="/private">
          <Route element={<p>Private content</p>} index />
        </Route>
        <Route element={<p>Login page</p>} path="/login" />
        <Route element={<p>Forbidden page</p>} path="/403" />
      </Routes>
    </MemoryRouter>,
  )
}

describe('ProtectedRoute', () => {
  it('keeps content hidden while session restoration is loading', () => {
    renderProtectedRoute({ loading: true, user: null })

    expect(screen.getAllByRole('status')).toHaveLength(2)
    expect(screen.getByText('Restoring your session')).toBeInTheDocument()
    expect(screen.queryByText('Private content')).not.toBeInTheDocument()
  })

  it('redirects signed-out users to login', () => {
    renderProtectedRoute({ loading: false, user: null })

    expect(screen.getByText('Login page')).toBeInTheDocument()
    expect(screen.queryByText('Private content')).not.toBeInTheDocument()
  })

  it('renders the protected child for an authenticated user', () => {
    renderProtectedRoute({
      loading: false,
      user: { id: 'user-1', permissions: [] },
    })

    expect(screen.getByText('Private content')).toBeInTheDocument()
  })

  it('redirects users who lack a required role or permission', () => {
    renderProtectedRoute(
      {
        loading: false,
        user: { id: 'user-1', permissions: [] },
        role: 'employee',
      },
      <RoleRoute roles={['super_admin']} permission="users:manage" />,
    )

    expect(screen.getByText('Forbidden page')).toBeInTheDocument()
    expect(screen.queryByText('Private content')).not.toBeInTheDocument()
  })
})
