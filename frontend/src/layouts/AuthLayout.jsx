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
        <p className="text-primary fw-bold text-uppercase">SmartERP</p>
        <h1>One clear view of your business.</h1>
        <p className="fs-5 text-muted mt-3">
          A simpler workspace for the people and processes that move your
          organization forward.
        </p>
      </section>
      <section className="auth-layout__content">
        <div className="auth-card">{children ?? <Outlet />}</div>
      </section>
    </main>
  )
}
