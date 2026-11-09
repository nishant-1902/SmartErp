import { Outlet } from 'react-router-dom'

/**
 * Presents authentication pages in a branded, responsive split-screen layout.
 *
 * @param {{children?: React.ReactNode}} props
 */
export default function AuthLayout({ children }) {
  return (
    <main className="auth-layout">
      <section aria-label="SmartERP introduction" className="auth-layout__intro">
        <div className="auth-brand"><span aria-hidden="true" className="auth-brand__mark">S</span>SmartERP</div>
        <h1>Run your business with clarity.</h1>
        <p className="fs-5 text-muted mt-3">
          The connected workspace for your people, inventory, purchasing, and sales.
        </p>
      </section>
      <section className="auth-layout__content">
        <div className="auth-card">{children ?? <Outlet />}</div>
      </section>
    </main>
  )
}
