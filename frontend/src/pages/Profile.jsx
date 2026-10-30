import { Link } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import CurrentUserDetails from '../components/CurrentUserDetails.jsx'
import { useAuth } from '../hooks/useAuth.js'

/**
 * Shows the current user's own account details.
 *
 * @returns {JSX.Element}
 */
export default function Profile() {
  const { user } = useAuth()

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Account</p>
          <h1>Profile</h1>
          <p className="mb-0">Your current account details and access status.</p>
        </div>
        <Button as={Link} to="/settings" variant="outline-primary">
          Account settings
        </Button>
      </div>
      <CurrentUserDetails user={user} />
    </section>
  )
}
