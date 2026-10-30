/**
 * Navigation metadata used by the sidebar to filter links by permission.
 */
export const navigationItems = [
  {
    label: 'Overview',
    path: '/',
    icon: '⌂',
    requiredPermission: null,
    implemented: true,
  },
  {
    label: 'Employees',
    path: '/employees',
    icon: '◎',
    requiredPermission: 'employees:read',
    implemented: false,
  },
  {
    label: 'Departments',
    path: '/departments',
    icon: '▦',
    requiredPermission: 'departments:read',
    implemented: false,
  },
  {
    label: 'Inventory',
    path: '/inventory',
    icon: '◇',
    requiredPermission: 'inventory:read',
    implemented: false,
  },
  {
    label: 'Sales',
    path: '/sales',
    icon: '↗',
    requiredPermission: 'sales:read',
    implemented: false,
  },
]
