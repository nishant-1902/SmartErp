import { Navigate, Outlet } from 'react-router-dom'
import LoadingSpinner from './LoadingSpinner.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { hasPermission } from '../utils/permissions.js'

/**
 * Blocks signed-out users from protected routes.
 *
 * @param {{children?: React.ReactNode}} props
 */
export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return (
      <div className="min-vh-100 d-grid place-items-center" role="status">
        <LoadingSpinner label="Restoring your session" />
      </div>
    )
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return children ?? <Outlet />
}

/**
 * UX-only role and permission guard; backend endpoints remain authoritative.
 *
 * @param {{roles?: string[], permission?: string, children?: React.ReactNode}} props
 */
export function RoleRoute({ roles, permission, children }) {
  const { role, user } = useAuth()
  const allowed =
    (!roles || roles.includes(role)) &&
    (!permission || hasPermission(user, permission))

  if (!allowed) {
    return <Navigate replace to="/403" />
  }
  return children ?? <Outlet />
}

// Route guards improve the user experience only; the backend enforces security.
