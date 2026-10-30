/**
 * Accessible Bootstrap spinner for pending page or data operations.
 *
 * @param {{label?: string, size?: 'sm' | 'default'}} props
 */
export default function LoadingSpinner({ label = 'Loading', size = 'default' }) {
  return (
    <span className="d-inline-flex align-items-center gap-2" role="status">
      <span
        aria-hidden="true"
        className={`spinner-border${size === 'sm' ? ' spinner-border-sm' : ''}`}
      />
      <span className="visually-hidden">{label}</span>
    </span>
  )
}
