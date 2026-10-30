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
    roles: [
      'super_admin',
      'hr_manager',
      'inventory_manager',
      'purchase_manager',
      'sales_manager',
    ],
    implemented: true,
  },
  {
    label: 'Departments',
    path: '/departments',
    icon: '▦',
    requiredPermission: 'departments:read',
    implemented: true,
  },
  {
    label: 'Users',
    path: '/users',
    icon: '♙',
    requiredPermission: 'users:manage',
    implemented: true,
  },
  {
    label: 'Audit logs',
    path: '/audit-logs',
    icon: '▤',
    requiredPermission: 'audit:read',
    implemented: true,
  },
  {
    label: 'Profile',
    path: '/profile',
    icon: '○',
    requiredPermission: 'own-profile:read',
    implemented: true,
  },
  {
    label: 'Settings',
    path: '/settings',
    icon: '⚙',
    requiredPermission: 'own-password:change',
    implemented: true,
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
