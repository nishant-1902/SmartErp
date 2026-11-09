import { useMemo, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Dropdown from 'react-bootstrap/Dropdown'
import { Link, useLocation } from 'react-router-dom'
import { navigationItems } from '../config/navigation.js'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'

/** Responsive top bar with route context and account actions. */
export default function Navbar({ collapsed = false, onMenuClick, onSidebarToggle }) {
  const { user, role, logout } = useAuth()
  const { showToast } = useToast()
  const location = useLocation()
  const [loggingOut, setLoggingOut] = useState(false)

  const pageTitle = useMemo(() => {
    const route = navigationItems.find((item) => item.path !== '/' && (location.pathname === item.path || location.pathname.startsWith(`${item.path}/`)))
    if (route && location.pathname !== route.path) return `${route.label} · Details`
    return (route?.label === 'Overview' ? 'Dashboard' : route?.label) ?? (location.pathname === '/' ? 'Dashboard' : 'Workspace')
  }, [location.pathname])

  async function handleLogout() {
    setLoggingOut(true)
    try {
      await logout()
    } catch {
      showToast('Your session was closed, but the server could not confirm logout.', 'warning')
    } finally {
      setLoggingOut(false)
    }
  }

  const displayName = user?.name ?? user?.email ?? 'Account'
  const initials = displayName.split(/[\s@]/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join('')
  const roleLabel = (role ?? 'User').replaceAll('_', ' ')

  return (
    <header className="app-navbar d-flex align-items-center justify-content-between gap-3">
      <div className="d-flex align-items-center gap-3">
        <Button aria-label="Open navigation menu" className="d-lg-none" onClick={onMenuClick} variant="outline-secondary">☰</Button>
        <Button aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'} className="d-none d-lg-inline-flex" onClick={onSidebarToggle} variant="light">☷</Button>
        <div className="app-navbar__crumb"><span>Workspace</span><span className="mx-2">/</span><strong>{pageTitle}</strong></div>
      </div>
      <Dropdown align="end">
        <Dropdown.Toggle className="app-navbar__user bg-transparent border-0" id="user-menu" variant="light">
          <span aria-hidden="true" className="app-navbar__avatar">{initials || 'U'}</span>
          <span className="d-none d-sm-block text-start"><span className="d-block">{displayName}</span><small className="text-muted text-capitalize">{roleLabel}</small></span>
        </Dropdown.Toggle>
        <Dropdown.Menu>
          <Dropdown.Header><span className="d-block text-body">{displayName}</span><small className="text-muted text-capitalize">{roleLabel}</small></Dropdown.Header>
          <Dropdown.Divider />
          <Dropdown.Item as={Link} to="/profile">Profile</Dropdown.Item>
          <Dropdown.Item as={Link} to="/settings">Settings</Dropdown.Item>
          <Dropdown.Divider />
          <Dropdown.Item disabled={loggingOut} onClick={handleLogout}>{loggingOut ? 'Signing out…' : 'Sign out'}</Dropdown.Item>
        </Dropdown.Menu>
      </Dropdown>
    </header>
  )
}
