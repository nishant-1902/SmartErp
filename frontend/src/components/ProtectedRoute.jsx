import { Navigate, Outlet } from 'react-router-dom'
import { useAuth } from '../hooks/useAuth.js'
import { hasPermission } from '../utils/permissions.js'

export function ProtectedRoute({ children }) {
  const { user, loading } = useAuth()

  if (loading) {
    return <p className="container py-4" role="status">Restoring your session…</p>
  }
  if (!user) {
    return <Navigate to="/login" replace />
  }
  return children ?? <Outlet />
}

export function RoleRoute({ roles, permission, children }) {
  const { role, user } = useAuth()
  const allowed =
    (!roles || roles.includes(role)) &&
    (!permission || hasPermission(user, permission))

  if (!allowed) {
    return <p className="container py-4" role="alert">You do not have access to this page.</p>
  }
  return children ?? <Outlet />
}

// Route guards improve the user experience only; the backend enforces security.
