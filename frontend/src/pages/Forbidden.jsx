import { Link } from 'react-router-dom'

/**
 * Explains that the signed-in user is not authorized to view a page.
 *
 * @returns {JSX.Element}
 */
export default function Forbidden() {
  return (
    <section className="text-center py-5">
      <p className="text-primary fw-bold">403</p>
      <h1 className="h2">Access denied</h1>
      <p className="text-muted">Your account does not have permission to view this page.</p>
      <Link className="btn btn-primary mt-2" to="/">
        Return to overview
      </Link>
    </section>
  )
}
