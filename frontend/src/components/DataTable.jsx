import { useMemo, useState } from 'react'
import Table from 'react-bootstrap/Table'
import LoadingSpinner from './LoadingSpinner.jsx'

function getCellValue(row, column) {
  return typeof column.sortValue === 'function'
    ? column.sortValue(row)
    : row[column.key]
}

/**
 * Renders configurable, accessible table columns with sorting and empty/loading states.
 *
 * @param {{columns: Array<{key: string, label: string, sortable?: boolean, className?: string, render?: (row: object) => React.ReactNode, sortValue?: (row: object) => string | number}>, data?: object[], loading?: boolean, emptyMessage?: string, className?: string, onSort?: (key: string, direction: 'asc' | 'desc') => void}} props
 */
export default function DataTable({
  columns,
  data = [],
  className = '',
  loading = false,
  emptyMessage = 'No records to display.',
  onSort,
  serverSideSorting = false,
}) {
  const [sort, setSort] = useState({ key: null, direction: 'asc' })
  const sortedData = useMemo(() => {
    if (serverSideSorting) return data
    if (!sort.key) return data
    const column = columns.find((item) => item.key === sort.key)
    if (!column) return data

    return [...data].sort((first, second) => {
      const firstValue = getCellValue(first, column)
      const secondValue = getCellValue(second, column)
      const comparison =
        typeof firstValue === 'number' && typeof secondValue === 'number'
          ? firstValue - secondValue
          : String(firstValue ?? '').localeCompare(String(secondValue ?? ''), undefined, {
              numeric: true,
              sensitivity: 'base',
            })
      return sort.direction === 'asc' ? comparison : -comparison
    })
  }, [columns, data, serverSideSorting, sort])

  function handleSort(column) {
    const direction =
      sort.key === column.key && sort.direction === 'asc' ? 'desc' : 'asc'
    setSort({ key: column.key, direction })
    onSort?.(column.sortBy ?? column.key, direction)
  }

  return (
    <div className={`data-table-wrap table-responsive ${className}`.trim()}>
      <Table hover responsive="sm" className="align-middle">
        <thead>
          <tr>
            {columns.map((column) => {
              const activeSort = sort.key === column.key
              return (
                <th
                  aria-sort={
                    activeSort
                      ? sort.direction === 'asc'
                        ? 'ascending'
                        : 'descending'
                      : 'none'
                  }
                  key={column.key}
                  className={column.className}
                  scope="col"
                >
                  {column.sortable ? (
                    <button
                      className="data-table-sort"
                      onClick={() => handleSort(column)}
                      type="button"
                    >
                      {column.label}
                      <span aria-hidden="true" className="ms-2">
                        {activeSort ? (sort.direction === 'asc' ? '↑' : '↓') : '↕'}
                      </span>
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              )
            })}
          </tr>
        </thead>
        <tbody>
          {loading ? (
            <tr>
              <td className="py-5 text-center" colSpan={columns.length}>
                <LoadingSpinner label="Loading records" />
              </td>
            </tr>
          ) : sortedData.length === 0 ? (
            <tr>
              <td className="py-5 text-center text-muted" colSpan={columns.length}>
                {emptyMessage}
              </td>
            </tr>
          ) : (
            sortedData.map((row, index) => (
              <tr key={row.id ?? row._id ?? index}>
                {columns.map((column) => (
                  <td className={column.className} key={column.key}>
                    {column.render ? column.render(row) : row[column.key]}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </Table>
    </div>
  )
}
