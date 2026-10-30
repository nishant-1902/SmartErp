import Button from 'react-bootstrap/Button'

/**
 * Provides compact accessible pagination controls for a result set.
 *
 * @param {{page: number, pageSize: number, totalItems: number, onPageChange: (page: number) => void}} props
 */
export default function Pagination({
  page,
  pageSize,
  totalItems,
  onPageChange,
}) {
  const totalPages = Math.ceil(totalItems / pageSize)
  if (totalPages <= 1) return null

  const start = (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, totalItems)

  return (
    <nav
      aria-label="Pagination"
      className="d-flex flex-wrap align-items-center justify-content-between gap-3 mt-3"
    >
      <span className="small text-muted">
        Showing {start}–{end} of {totalItems}
      </span>
      <div className="d-flex align-items-center gap-2">
        <Button
          aria-label="Go to previous page"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
          size="sm"
          variant="outline-secondary"
        >
          Previous
        </Button>
        <span aria-current="page" className="small px-2">
          Page {page} of {totalPages}
        </span>
        <Button
          aria-label="Go to next page"
          disabled={page >= totalPages}
          onClick={() => onPageChange(page + 1)}
          size="sm"
          variant="outline-secondary"
        >
          Next
        </Button>
      </div>
    </nav>
  )
}
