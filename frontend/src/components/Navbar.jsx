import { useState } from 'react'
import Button from 'react-bootstrap/Button'
import Dropdown from 'react-bootstrap/Dropdown'
import { useAuth } from '../hooks/useAuth.js'
import { useToast } from '../hooks/useToast.js'

/**
 * Top application bar with mobile navigation toggle and account/logout menu.
 *
 * @param {{onMenuClick: () => void}} props
 */
export default function Navbar({ onMenuClick }) {
  const { user, role, logout } = useAuth()
  const { showToast } = useToast()
  const [loggingOut, setLoggingOut] = useState(false)

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

  return (
    <header className="app-navbar d-flex align-items-center justify-content-between gap-3">
      <div className="d-flex align-items-center gap-3">
        <Button
          aria-label="Open navigation menu"
          className="d-lg-none"
          onClick={onMenuClick}
          variant="outline-secondary"
        >
          <span aria-hidden="true">☰</span>
        </Button>
        <span className="app-navbar__title d-none d-sm-inline">Workspace</span>
      </div>
      <Dropdown align="end">
        <Dropdown.Toggle
          className="app-navbar__user bg-transparent border-0"
          id="user-menu"
          variant="light"
        >
          <span aria-hidden="true" className="me-2">●</span>
          {displayName}
        </Dropdown.Toggle>
        <Dropdown.Menu>
          <Dropdown.Header>
            <span className="d-block">{displayName}</span>
            <small className="text-muted">{role ?? 'User'}</small>
          </Dropdown.Header>
          <Dropdown.Divider />
          <Dropdown.Item disabled={loggingOut} onClick={handleLogout}>
            {loggingOut ? 'Signing out…' : 'Sign out'}
          </Dropdown.Item>
        </Dropdown.Menu>
      </Dropdown>
    </header>
  )
}
