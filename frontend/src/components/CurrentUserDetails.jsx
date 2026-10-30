function formatRole(role = '') {
  return role
    .split('_')
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(' ')
}

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' })
        .format(date)
}

/**
 * Displays safe account details from the authenticated user's session profile.
 *
 * @param {{user: object}} props
 */
export default function CurrentUserDetails({ user }) {
  return (
    <div className="surface-card bg-white p-4">
      <h2 className="h5 mb-3">Your account</h2>
      <dl className="row mb-0">
        <dt className="col-sm-4">Name</dt>
        <dd className="col-sm-8">{user.full_name || '—'}</dd>
        <dt className="col-sm-4">Email</dt>
        <dd className="col-sm-8">{user.email || '—'}</dd>
        <dt className="col-sm-4">Role</dt>
        <dd className="col-sm-8">{formatRole(user.role)}</dd>
        <dt className="col-sm-4">Account status</dt>
        <dd className="col-sm-8">{user.is_active === false ? 'Inactive' : 'Active'}</dd>
        <dt className="col-sm-4">Employee link</dt>
        <dd className="col-sm-8">{user.employee_id || '—'}</dd>
        <dt className="col-sm-4">Last sign-in</dt>
        <dd className="col-sm-8">{formatDate(user.last_login_at)}</dd>
      </dl>
    </div>
  )
}
