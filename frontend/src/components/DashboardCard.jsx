/**
 * Displays one summary metric in a reusable dashboard surface.
 *
 * @param {{label: string, value: React.ReactNode, detail?: React.ReactNode, icon?: React.ReactNode}} props
 */
export default function DashboardCard({ label, value, detail, icon }) {
  return (
    <section aria-label={label} className="dashboard-card surface-card">
      <div className="d-flex align-items-start justify-content-between gap-3">
        <div>
          <p className="dashboard-card__label">{label}</p>
          <p className="dashboard-card__value">{value}</p>
        </div>
        {icon && (
          <span aria-hidden="true" className="text-primary fs-4">
            {icon}
          </span>
        )}
      </div>
      {detail && <div className="small text-muted mt-2">{detail}</div>}
    </section>
  )
}
