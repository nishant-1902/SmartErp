import { NavLink } from 'react-router-dom'
import { navigationItems } from '../config/navigation.js'
import { useAuth } from '../hooks/useAuth.js'

/**
 * Renders permission-filtered navigation; hidden links are only a UX aid.
 *
 * @param {{onNavigate?: () => void}} props
 */
export default function Sidebar({ onNavigate }) {
  const { user, role } = useAuth()
  const visibleItems = navigationItems.filter((item) => {
    const roleAllowed = !item.roles || item.roles.includes(role)
    const permissionAllowed =
      !item.requiredPermission ||
      user?.permissions?.includes(item.requiredPermission)
    return roleAllowed && permissionAllowed
  })

  return (
    <div className="h-100 d-flex flex-column">
      <NavLink className="sidebar-brand" onClick={onNavigate} to="/">
        <span aria-hidden="true" className="sidebar-brand__mark">S</span>
        <span>SmartERP</span>
      </NavLink>
      <div className="sidebar-section-label">Workspace</div>
      <nav aria-label="Main navigation" className="d-grid">
        {visibleItems.map((item) =>
          item.implemented ? (
            <NavLink
              className={({ isActive }) =>
                `sidebar-nav-link${isActive ? ' active' : ''}`
              }
              end={item.path === '/'}
              key={item.path}
              onClick={onNavigate}
              to={item.path}
            >
              <span className="sidebar-nav-link__label">
                <span aria-hidden="true" className="sidebar-nav-link__icon">
                  {item.icon}
                </span>
                {item.label}
              </span>
            </NavLink>
          ) : (
            <span
              aria-disabled="true"
              className="sidebar-nav-link disabled"
              key={item.path}
              title="Available in a later implementation step"
            >
              <span className="sidebar-nav-link__label">
                <span aria-hidden="true" className="sidebar-nav-link__icon">
                  {item.icon}
                </span>
                {item.label}
              </span>
              <span className="sidebar-soon">Soon</span>
            </span>
          ),
        )}
      </nav>
      <div className="mt-auto px-3 py-3 small text-white-50">ERP workspace</div>
    </div>
  )
}
