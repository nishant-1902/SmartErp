/** Permission-aware navigation for routes that currently exist in the app. */
export const navigationItems = [
  { section: 'Overview', label: 'Overview', path: '/', icon: '◈', requiredPermission: null },
  { section: 'Organization', label: 'Employees', path: '/employees', icon: '◉', requiredPermission: 'employees:read', roles: ['super_admin', 'hr_manager', 'inventory_manager', 'purchase_manager', 'sales_manager'] },
  { section: 'Organization', label: 'Departments', path: '/departments', icon: '▦', requiredPermission: 'departments:read' },
  { section: 'Organization', label: 'Users', path: '/users', icon: '♙', requiredPermission: 'users:manage' },
  { section: 'Inventory', label: 'Products', path: '/products', icon: '◇', requiredPermission: 'products:read' },
  { section: 'Inventory', label: 'Inventory', path: '/inventory', icon: '▤', requiredPermission: 'stock:read' },
  { section: 'Inventory', label: 'Stock movements', path: '/stock-movements', icon: '↔', requiredPermission: 'stock:read' },
  { section: 'Purchasing', label: 'Suppliers', path: '/suppliers', icon: '▱', requiredPermission: 'suppliers:read' },
  { section: 'Purchasing', label: 'Purchase orders', path: '/purchase-orders', icon: '▣', requiredPermission: 'purchase:read' },
  { section: 'Sales', label: 'Customers', path: '/customers', icon: '♧', requiredPermission: 'customers:read' },
  { section: 'Sales', label: 'Sales orders', path: '/sales-orders', icon: '↗', requiredPermission: 'sales:read' },
  { section: 'Analytics', label: 'Reports', path: '/reports', icon: '▥', requiredPermission: 'reports:read' },
  { section: 'Administration', label: 'Profile', path: '/profile', icon: '◯', requiredPermission: 'own-profile:read' },
  { section: 'Administration', label: 'Settings', path: '/settings', icon: '⚙', requiredPermission: 'own-password:change' },
  { section: 'Administration', label: 'Audit logs', path: '/audit-logs', icon: '≡', requiredPermission: 'audit:read' },
]
