import { useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { listAuditLogs } from '../services/auditService.js'
import { getApiError } from '../utils/apiErrors.js'

function formatDate(value) {
  if (!value) return '—'
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

/**
 * Shows a filterable, server-paginated audit log for audit:read users.
 *
 * @returns {JSX.Element}
 */
export default function AuditLogs() {
  const [draft, setDraft] = useState({
    user: '',
    action: '',
    start_date: '',
    end_date: '',
  })
  const [filterError, setFilterError] = useState('')
  const list = usePaginatedList(listAuditLogs)

  function applyFilters(event) {
    event.preventDefault()
    setFilterError('')
    if (draft.user && !/^[a-f\d]{24}$/i.test(draft.user.trim())) {
      setFilterError('Enter a valid 24-character user ID, or leave this filter empty.')
      return
    }
    if (
      draft.start_date &&
      draft.end_date &&
      draft.start_date > draft.end_date
    ) {
      setFilterError('The start date must be on or before the end date.')
      return
    }
    for (const field of Object.keys(draft)) {
      list.setFilter(field, draft[field].trim())
    }
  }

  function clearFilters() {
    const empty = { user: '', action: '', start_date: '', end_date: '' }
    setDraft(empty)
    setFilterError('')
    for (const field of Object.keys(empty)) list.setFilter(field, '')
  }

  const columns = [
    { key: 'actor_id', label: 'User ID' },
    { key: 'action', label: 'Action' },
    {
      key: 'entity_type',
      label: 'Resource',
      render: (record) =>
        record.entity_type
          ? `${record.entity_type}${record.entity_id ? ` · ${record.entity_id}` : ''}`
          : '—',
    },
    { key: 'outcome', label: 'Outcome' },
    {
      key: 'created_at',
      label: 'Date',
      render: (record) => formatDate(record.created_at),
    },
    { key: 'ip', label: 'IP address' },
  ]

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Administration</p>
        <h1>Audit logs</h1>
        <p className="mb-0">Review recorded account and system activity.</p>
      </div>

      <Form className="surface-card bg-white p-3 p-md-4 mb-4" onSubmit={applyFilters}>
        <div className="row g-3 align-items-end">
          <div className="col-12 col-md-6 col-xl-3">
            <Form.Label htmlFor="audit-user">User ID</Form.Label>
            <Form.Control
              autoComplete="off"
              id="audit-user"
              onChange={(event) =>
                setDraft((current) => ({ ...current, user: event.target.value }))
              }
              placeholder="24-character ID"
              value={draft.user}
            />
          </div>
          <div className="col-12 col-md-6 col-xl-3">
            <Form.Label htmlFor="audit-action">Action</Form.Label>
            <Form.Control
              id="audit-action"
              onChange={(event) =>
                setDraft((current) => ({ ...current, action: event.target.value }))
              }
              placeholder="e.g. user_created"
              value={draft.action}
            />
          </div>
          <div className="col-6 col-xl-2">
            <Form.Label htmlFor="audit-start-date">From</Form.Label>
            <Form.Control
              id="audit-start-date"
              onChange={(event) =>
                setDraft((current) => ({ ...current, start_date: event.target.value }))
              }
              type="date"
              value={draft.start_date}
            />
          </div>
          <div className="col-6 col-xl-2">
            <Form.Label htmlFor="audit-end-date">To</Form.Label>
            <Form.Control
              id="audit-end-date"
              onChange={(event) =>
                setDraft((current) => ({ ...current, end_date: event.target.value }))
              }
              type="date"
              value={draft.end_date}
            />
          </div>
          <div className="col-12 col-xl-2 d-flex gap-2">
            <Button className="flex-grow-1" type="submit">Apply</Button>
            <Button onClick={clearFilters} type="button" variant="outline-secondary">
              Clear
            </Button>
          </div>
        </div>
        <p className="small text-muted mt-2 mb-0">
          User filters use the MongoDB user ID and match the event actor or target.
        </p>
      </Form>

      {filterError && <ErrorMessage message={filterError} />}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No audit events match these filters."
        loading={list.loading}
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />
    </section>
  )
}
