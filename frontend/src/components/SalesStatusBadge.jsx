const statusVariants = {
  draft: 'secondary',
  confirmed: 'primary',
  fulfilled: 'success',
  cancelled: 'dark',
  unpaid: 'secondary',
  partial: 'warning',
  paid: 'success',
  none: 'secondary',
  full: 'success',
}

/**
 * Display a sales or payment status using a consistent badge.
 *
 * @param {{status: string, label?: string}} props
 */
export default function SalesStatusBadge({ status, label }) {
  const text = label ?? status.replaceAll('_', ' ')
  return (
    <span className={`badge text-bg-${statusVariants[status] ?? 'secondary'}`}>
      {text}
    </span>
  )
}
