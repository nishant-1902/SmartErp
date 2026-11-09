import { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { navigationItems } from '../config/navigation.js'
import { useAuth } from '../hooks/useAuth.js'

/** Renders grouped navigation links filtered by the signed-in user's permissions. */
export default function Sidebar({ onNavigate, collapsed = false }) {
  const { user, role } = useAuth()
  const [closedSections, setClosedSections] = useState([])
  const visibleItems = navigationItems.filter((item) => {
    const roleAllowed = !item.roles || item.roles.includes(role)
    return roleAllowed && (!item.requiredPermission || user?.permissions?.includes(item.requiredPermission))
  })
  const sections = [...new Set(visibleItems.map((item) => item.section))]

  function toggleSection(section) {
    setClosedSections((current) => current.includes(section)
      ? current.filter((value) => value !== section)
      : [...current, section])
  }

  return (
    <div className={`h-100 d-flex flex-column${collapsed ? ' sidebar-collapsed' : ''}`}>
      <NavLink aria-label="SmartERP dashboard" className="sidebar-brand" onClick={onNavigate} to="/">
        <span aria-hidden="true" className="sidebar-brand__mark">S</span>
        <span>SmartERP</span>
      </NavLink>
      <nav aria-label="Main navigation" className="d-grid">
        {sections.map((section) => {
          const items = visibleItems.filter((item) => item.section === section)
          const isOpen = !closedSections.includes(section)
          return (
            <div key={section}>
              {section !== 'Overview' && (
                <button aria-expanded={isOpen} className="sidebar-section-label" onClick={() => toggleSection(section)} title={collapsed ? section : undefined} type="button">
                  <span>{section}</span>{!collapsed && <span aria-hidden="true">{isOpen ? '−' : '+'}</span>}
                </button>
              )}
              {isOpen && items.map((item) => (
                <NavLink
                  aria-label={collapsed ? item.label : undefined}
                  className={({ isActive }) => `sidebar-nav-link${isActive ? ' active' : ''}`}
                  end={item.path === '/'}
                  key={item.path}
                  onClick={onNavigate}
                  title={collapsed ? item.label : undefined}
                  to={item.path}
                >
                  <span className="sidebar-nav-link__label">
                    <span aria-hidden="true" className="sidebar-nav-link__icon">{item.icon}</span>
                    <span>{item.label}</span>
                  </span>
                </NavLink>
              ))}
            </div>
          )
        })}
      </nav>
      <div className="sidebar-footer mt-auto px-3 py-3 small text-white-50">ERP workspace</div>
    </div>
  )
}
