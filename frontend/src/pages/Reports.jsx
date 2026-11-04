import { useEffect, useMemo, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import DataTable from '../components/DataTable.jsx'
import DashboardCard from '../components/DashboardCard.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import Pagination from '../components/Pagination.jsx'
import { useAuth } from '../hooks/useAuth.js'
import {
  getInventorySummary,
  listReport,
} from '../services/reportsService.js'
import { getApiError } from '../utils/apiErrors.js'
import { downloadCsv } from '../utils/csvExport.js'
import { formatMoney } from '../utils/formatMoney.js'

const pageSize = 20

function formatDate(value) {
  const parsed = new Date(value)
  return Number.isNaN(parsed.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(parsed)
}

/**
 * Renders permission-filtered, date-bounded report tabs with safe CSV export.
 *
 * @returns {JSX.Element}
 */
export default function Reports() {
  const { hasPermission } = useAuth()
  const canReadSales = hasPermission('sales:read')
  const canReadInventory =
    hasPermission('products:read') && hasPermission('stock:read')
  const canReadPurchases = hasPermission('purchase:read')
  const canReadEmployees = hasPermission('employees:read')
  const tabs = useMemo(
    () => [
      ...(canReadSales ? [{ key: 'sales', label: 'Sales', report: 'sales' }] : []),
      ...(canReadInventory
        ? [{ key: 'inventory', label: 'Inventory', report: 'lowStock' }]
        : []),
      ...(canReadPurchases
        ? [{ key: 'purchases', label: 'Purchases', report: 'purchases' }]
        : []),
      ...(canReadEmployees
        ? [{ key: 'employees', label: 'Employees', report: 'employees' }]
        : []),
    ],
    [canReadEmployees, canReadInventory, canReadPurchases, canReadSales],
  )

  const [activeTab, setActiveTab] = useState('sales')
  const selectedTab = tabs.find((tab) => tab.key === activeTab) ?? tabs[0]
  const [dateFromInput, setDateFromInput] = useState('')
  const [dateToInput, setDateToInput] = useState('')
  const [dateRange, setDateRange] = useState({ date_from: '', date_to: '' })
  const [filterError, setFilterError] = useState('')
  const [page, setPage] = useState(1)
  const [result, setResult] = useState({ key: '', items: [], meta: {} })
  const [inventorySummary, setInventorySummary] = useState({ key: '', value: null })
  const [errorState, setErrorState] = useState({ key: '', message: '' })
  const [summaryErrorState, setSummaryErrorState] = useState({
    key: '',
    message: '',
  })
  const [retryKey, setRetryKey] = useState(0)
  const requestKey = JSON.stringify([
    selectedTab?.key,
    page,
    dateRange,
    retryKey,
  ])
  const loading =
    Boolean(selectedTab) &&
    result.key !== requestKey &&
    errorState.key !== requestKey
  const error = errorState.key === requestKey ? errorState.message : ''
  const summaryError =
    summaryErrorState.key === requestKey ? summaryErrorState.message : ''
  const reportResult =
    result.key === requestKey ? result : { items: [], meta: {} }
  const currentInventorySummary =
    inventorySummary.key === requestKey ? inventorySummary.value : null

  useEffect(() => {
    if (!selectedTab) return undefined
    const controller = new AbortController()
    let active = true
    const params = {
      page,
      page_size: pageSize,
      ...(dateRange.date_from ? { date_from: dateRange.date_from } : {}),
      ...(dateRange.date_to ? { date_to: dateRange.date_to } : {}),
    }

    const load = async () => {
      if (selectedTab.key !== 'inventory') {
        const pageResult = await listReport(
          selectedTab.report,
          params,
          { signal: controller.signal },
        )
        if (active) {
          setResult({ key: requestKey, ...pageResult })
        }
        return
      }

      const [summaryResult, pageResult] = await Promise.allSettled([
        getInventorySummary({ signal: controller.signal }),
        listReport('lowStock', params, { signal: controller.signal }),
      ])
      if (!active) return

      if (summaryResult.status === 'fulfilled') {
        setInventorySummary({ key: requestKey, value: summaryResult.value })
      } else {
        setSummaryErrorState({
          key: requestKey,
          message: getApiError(summaryResult.reason).message,
        })
      }
      if (pageResult.status === 'fulfilled') {
        setResult({ key: requestKey, ...pageResult.value })
      } else {
        throw pageResult.reason
      }
    }

    load()
      .catch((requestError) => {
        if (!active || controller.signal.aborted) return
        setErrorState({
          key: requestKey,
          message: getApiError(requestError).message,
        })
        setResult({ key: requestKey, items: [], meta: {} })
      })

    return () => {
      active = false
      controller.abort()
    }
  }, [dateRange, page, requestKey, retryKey, selectedTab])

  const columns = useMemo(() => {
    if (!selectedTab) return []
    if (selectedTab.key === 'sales') {
      return [
        { key: 'order_number', label: 'Order' },
        {
          key: 'customer_snapshot',
          label: 'Customer',
          render: (row) => row.customer_snapshot?.name ?? '—',
          exportValue: (row) => row.customer_snapshot?.name,
        },
        { key: 'fulfilled_at', label: 'Fulfilled', render: (row) => formatDate(row.fulfilled_at) },
        { key: 'grand_total', label: 'Gross total', render: (row) => formatMoney(row.grand_total) },
        { key: 'returns_total', label: 'Returns', render: (row) => formatMoney(row.returns_total) },
        { key: 'net_total', label: 'Net sales', render: (row) => formatMoney(row.net_total) },
      ]
    }
    if (selectedTab.key === 'inventory') {
      return [
        { key: 'sku', label: 'SKU' },
        { key: 'name', label: 'Product' },
        { key: 'category', label: 'Category' },
        { key: 'quantity_on_hand', label: 'On hand' },
        { key: 'reserved_quantity', label: 'Reserved' },
        { key: 'available_quantity', label: 'Available' },
        { key: 'min_stock_level', label: 'Minimum' },
      ]
    }
    if (selectedTab.key === 'purchases') {
      return [
        { key: 'po_number', label: 'PO number' },
        {
          key: 'supplier_snapshot',
          label: 'Supplier',
          render: (row) => row.supplier_snapshot?.name ?? '—',
          exportValue: (row) => row.supplier_snapshot?.name,
        },
        { key: 'status', label: 'Status', render: (row) => row.status.replaceAll('_', ' ') },
        { key: 'created_at', label: 'Created', render: (row) => formatDate(row.created_at) },
        { key: 'grand_total', label: 'Total', render: (row) => formatMoney(row.grand_total) },
      ]
    }
    return [
      { key: 'employee_code', label: 'Employee code' },
      {
        key: 'full_name',
        label: 'Name',
        render: (row) => `${row.first_name} ${row.last_name}`,
        exportValue: (row) => `${row.first_name} ${row.last_name}`,
      },
      { key: 'department_id', label: 'Department ID' },
      { key: 'designation', label: 'Designation' },
      { key: 'joining_date', label: 'Joined', render: (row) => formatDate(row.joining_date) },
      { key: 'status', label: 'Status' },
    ]
  }, [selectedTab])

  function applyDateFilters() {
    if (dateFromInput && dateToInput && dateFromInput > dateToInput) {
      setFilterError('End date must be on or after the start date.')
      return
    }
    setFilterError('')
    setPage(1)
    setDateRange({ date_from: dateFromInput, date_to: dateToInput })
  }

  function clearDateFilters() {
    setDateFromInput('')
    setDateToInput('')
    setFilterError('')
    setPage(1)
    setDateRange({ date_from: '', date_to: '' })
  }

  if (!selectedTab) {
    return (
      <section>
        <div className="page-heading">
          <p className="text-primary text-uppercase fw-bold small mb-2">Analytics</p>
          <h1>Reports</h1>
        </div>
        <ErrorMessage message="Your account does not have permission to view these reports." />
      </section>
    )
  }

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Analytics</p>
        <h1>Reports</h1>
        <p className="mb-0">Filter report data and export the current result page.</p>
      </div>

      <div aria-label="Report types" className="report-tabs mb-3" role="tablist">
        {tabs.map((tab) => (
          <Button
            aria-selected={selectedTab.key === tab.key}
            aria-controls="report-tab-panel"
            id={`report-tab-${tab.key}`}
            key={tab.key}
            onClick={() => {
              setActiveTab(tab.key)
              setPage(1)
            }}
            role="tab"
            tabIndex={selectedTab.key === tab.key ? 0 : -1}
            variant={selectedTab.key === tab.key ? 'primary' : 'outline-secondary'}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      <div className="row g-3 align-items-end mb-3">
        <div className="col-6 col-lg-3">
          <Form.Label htmlFor="report-date-from">Date from</Form.Label>
          <Form.Control
            id="report-date-from"
            onChange={(event) => setDateFromInput(event.target.value)}
            type="date"
            value={dateFromInput}
          />
        </div>
        <div className="col-6 col-lg-3">
          <Form.Label htmlFor="report-date-to">Date to</Form.Label>
          <Form.Control
            id="report-date-to"
            onChange={(event) => setDateToInput(event.target.value)}
            type="date"
            value={dateToInput}
          />
        </div>
        <div className="col-12 col-lg-6 d-flex flex-wrap gap-2">
          <Button onClick={applyDateFilters} type="button">Apply dates</Button>
          <Button onClick={clearDateFilters} type="button" variant="outline-secondary">
            Clear
          </Button>
          <Button
            className="ms-lg-auto"
            disabled={loading || reportResult.items.length === 0}
              onClick={() =>
                downloadCsv(columns, reportResult.items, selectedTab.key)
              }
            type="button"
            variant="outline-primary"
          >
            Export current page CSV
          </Button>
        </div>
      </div>

      {filterError && <ErrorMessage message={filterError} />}
      {error && (
        <>
          <ErrorMessage message={error} title="Could not load this report" />
          <Button
            className="mb-3"
            onClick={() => setRetryKey((current) => current + 1)}
            size="sm"
            variant="outline-primary"
          >
            Retry report
          </Button>
        </>
      )}

      {selectedTab.key === 'inventory' && (
        <div aria-label="Inventory summary" className="row g-3 mb-3">
          {summaryError ? (
            <div className="col-12">
              <ErrorMessage
                message={summaryError}
                onClose={() => setRetryKey((current) => current + 1)}
                title="Could not load inventory summary"
              />
            </div>
          ) : currentInventorySummary ? (
            <>
              <div className="col-12 col-sm-6 col-xl-3">
                <DashboardCard
                  label="Active products"
                  value={currentInventorySummary.active_products}
                />
              </div>
              <div className="col-12 col-sm-6 col-xl-3">
                <DashboardCard
                  label="Available quantity"
                  value={currentInventorySummary.available_quantity}
                />
              </div>
              <div className="col-12 col-sm-6 col-xl-3">
                <DashboardCard
                  label="Reserved quantity"
                  value={currentInventorySummary.reserved_quantity}
                />
              </div>
              <div className="col-12 col-sm-6 col-xl-3">
                <DashboardCard
                  label="Stock cost value"
                  value={formatMoney(currentInventorySummary.stock_cost_value)}
                />
              </div>
            </>
          ) : (
            <div className="col-12">
              <div aria-label="Loading inventory summary" className="surface-card p-3" role="status">
                <LoadingSpinner label="Loading inventory summary" />
              </div>
            </div>
          )}
        </div>
      )}

      <div
        aria-labelledby={`report-tab-${selectedTab.key}`}
        id="report-tab-panel"
        role="tabpanel"
      >
        <DataTable
          columns={columns}
          data={reportResult.items}
          emptyMessage={`No ${selectedTab.label.toLowerCase()} records match this date range.`}
          loading={loading}
        />
        <Pagination
          onPageChange={setPage}
          page={reportResult.meta.page ?? page}
          pageSize={reportResult.meta.page_size ?? pageSize}
          totalItems={reportResult.meta.total ?? 0}
        />
        <p className="small text-muted mt-2">
          CSV export includes only the rows returned on this page.
        </p>
      </div>
    </section>
  )
}
