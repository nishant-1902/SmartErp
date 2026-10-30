/**
 * Temporary overview placeholder for the shared authenticated layout.
 *
 * @returns {JSX.Element}
 */
function Home() {
  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Overview</p>
        <h1>Welcome to SmartERP</h1>
        <p className="mb-0">
          The shared interface foundation is ready. Business pages will be added
          in later steps.
        </p>
      </div>
      <div className="surface-card bg-white p-4 p-md-5">
        <h2 className="h5">Your workspace is ready</h2>
        <p className="text-muted mb-0">
          Use the navigation to access features as they become available.
        </p>
      </div>
    </section>
  )
}

export default Home
