import { useState } from 'react'
import Offcanvas from 'react-bootstrap/Offcanvas'
import { Outlet } from 'react-router-dom'
import Navbar from '../components/Navbar.jsx'
import Sidebar from '../components/Sidebar.jsx'

/**
 * Shared authenticated shell with a responsive offcanvas navigation sidebar.
 *
 * @returns {JSX.Element}
 */
export default function MainLayout() {
  const [showMenu, setShowMenu] = useState(false)
  const [collapsed, setCollapsed] = useState(false)

  return (
    <div className="app-shell d-flex">
      <Offcanvas
        className={`app-sidebar${collapsed ? ' desktop-collapsed' : ''}`}
        onHide={() => setShowMenu(false)}
        responsive="lg"
        show={showMenu}
      >
        <Offcanvas.Header className="d-lg-none" closeButton>
          <Offcanvas.Title>Navigation</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body className="p-0">
          <Sidebar collapsed={collapsed} onNavigate={() => setShowMenu(false)} />
        </Offcanvas.Body>
      </Offcanvas>
      <div className="app-content-shell">
        <Navbar collapsed={collapsed} onMenuClick={() => setShowMenu(true)} onSidebarToggle={() => setCollapsed((value) => !value)} />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
