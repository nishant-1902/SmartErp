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

  return (
    <div className="app-shell d-flex">
      <Offcanvas
        className="app-sidebar"
        onHide={() => setShowMenu(false)}
        responsive="lg"
        show={showMenu}
      >
        <Offcanvas.Header className="d-lg-none" closeButton>
          <Offcanvas.Title>Navigation</Offcanvas.Title>
        </Offcanvas.Header>
        <Offcanvas.Body className="p-0">
          <Sidebar onNavigate={() => setShowMenu(false)} />
        </Offcanvas.Body>
      </Offcanvas>
      <div className="app-content-shell">
        <Navbar onMenuClick={() => setShowMenu(true)} />
        <main className="app-main">
          <Outlet />
        </main>
      </div>
    </div>
  )
}
