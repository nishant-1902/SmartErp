import { Link } from 'react-router-dom'

/**
 * Provides a friendly 404 page for routes that are not implemented or unknown.
 *
 * @returns {JSX.Element}
 */
export default function NotFound() {
  return (
    <section className="text-center py-5">
      <p className="text-primary fw-bold">404</p>
      <h1 className="h2">Page not found</h1>
      <p className="text-muted">The page may have moved or is not available yet.</p>
      <Link className="btn btn-primary mt-2" to="/">
        Return to overview
      </Link>
    </section>
  )
}
