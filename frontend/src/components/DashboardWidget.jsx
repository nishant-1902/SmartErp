import Button from 'react-bootstrap/Button'
import ErrorMessage from './ErrorMessage.jsx'

/**
 * Presents independent loading, unavailable, and error states for a dashboard widget.
 *
 * @param {{title: string, loading?: boolean, error?: string, available?: boolean, onRetry?: () => void, children: React.ReactNode}} props
 */
export default function DashboardWidget({
  title,
  loading = false,
  error = '',
  available = true,
  onRetry,
  children,
}) {
  if (loading) {
    return (
      <section aria-label={`Loading ${title}`} className="surface-card dashboard-widget p-3">
        <div className="placeholder-glow">
          <span className="placeholder col-5 mb-3" />
          <span className="placeholder col-12 dashboard-widget__skeleton" />
          <span className="placeholder col-7 mt-3" />
        </div>
      </section>
    )
  }

  if (error || !available) {
    return (
      <section aria-label={title} className="surface-card dashboard-widget p-3">
        <h2 className="h6">{title}</h2>
        <ErrorMessage
          message={error || 'This widget is not available for your account.'}
        />
        {error && onRetry && (
          <Button onClick={onRetry} size="sm" variant="outline-primary">
            Retry
          </Button>
        )}
      </section>
    )
  }

  return (
    <section aria-label={title} className="dashboard-widget">
      {children}
    </section>
  )
}
