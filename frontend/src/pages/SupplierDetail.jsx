import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import LoadingSpinner from '../components/LoadingSpinner.jsx'
import Pagination from '../components/Pagination.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { getSupplier, listSupplierPurchaseOrders } from '../services/supplierService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, { dateStyle: 'medium' }).format(date)
}

/**
 * Show supplier details, complete purchase history, and outstanding orders.
 *
 * @returns {JSX.Element}
 */
export default function SupplierDetail() {
  const { supplierId } = useParams()
  const { hasPermission } = useAuth()
  const canReadPurchases = hasPermission('purchase:read')
  const [supplierState, setSupplierState] = useState({
    id: null,
    supplier: null,
    error: '',
  })
  const [outstanding, setOutstanding] = useState([])

  const fetchHistory = useCallback(
    async (params, options) => {
      if (!canReadPurchases) return { items: [], outstanding: [], meta: {} }
      const result = await listSupplierPurchaseOrders(
        supplierId,
        params,
        options,
      )
      setOutstanding(result.outstanding)
      return result
    },
    [canReadPurchases, supplierId],
  )
  const history = usePaginatedList(fetchHistory)

  useEffect(() => {
    const controller = new AbortController()
    getSupplier(supplierId, { signal: controller.signal })
      .then((supplier) =>
        setSupplierState({ id: supplierId, supplier, error: '' }),
      )
      .catch((error) => {
        if (!controller.signal.aborted) {
          setSupplierState({
            id: supplierId,
            supplier: null,
            error: getApiError(error).message,
          })
        }
      })
    return () => controller.abort()
  }, [supplierId])

  const supplierLoading = supplierState.id !== supplierId
  const supplier = supplierLoading ? null : supplierState.supplier
  const supplierError = supplierLoading ? '' : supplierState.error
  const outstandingError = history.error
    ? getApiError(history.error).message
    : ''
  const purchaseMeta = history.meta?.purchase_orders ?? history.meta

  const historyColumns = [
    {
      key: 'po_number',
      label: 'PO number',
      render: (order) => (
        <Link to={`/purchase-orders/${order.id}`}>{order.po_number}</Link>
      ),
    },
    { key: 'created_at', label: 'Created', render: (order) => formatDate(order.created_at) },
    { key: 'status', label: 'Status', render: (order) => order.status.replaceAll('_', ' ') },
    { key: 'grand_total', label: 'Total', render: (order) => formatMoney(order.grand_total) },
  ]

  if (supplierLoading) return <LoadingSpinner label="Loading supplier" />
  if (supplierError) return <ErrorMessage message={supplierError} />
  if (!supplier) return <ErrorMessage message="Supplier was not found." />

  return (
    <section>
      <div className="page-heading">
        <Link className="small" to="/suppliers">← Suppliers</Link>
        <div className="d-flex flex-wrap justify-content-between align-items-start gap-3 mt-2">
          <div>
            <p className="text-primary text-uppercase fw-bold small mb-2">
              Supplier · {supplier.code}
            </p>
            <h1>{supplier.name}</h1>
            <p className="mb-0">{supplier.contact_person || 'No contact person'} · {supplier.email || 'No email'} · {supplier.phone || 'No phone'}</p>
          </div>
          <span className={`badge ${supplier.status === 'active' ? 'text-bg-success' : 'text-bg-secondary'}`}>
            {supplier.status}
          </span>
        </div>
      </div>
      {supplier.payment_terms && (
        <p><strong>Payment terms:</strong> {supplier.payment_terms}</p>
      )}
      {supplier.address && (
        <address className="mb-3">
          {supplier.address.line1}
          {supplier.address.line2 && <><br />{supplier.address.line2}</>}
          <br />
          {[supplier.address.city, supplier.address.region, supplier.address.postal_code]
            .filter(Boolean)
            .join(', ')}
          <br />
          {supplier.address.country}
        </address>
      )}
      {!canReadPurchases ? (
        <ErrorMessage message="You do not have permission to view this supplier's purchase history." />
      ) : (
        <>
          <h2 className="h4 mt-4">Outstanding orders</h2>
          <ErrorMessage message={outstandingError} />
          {history.loading ? (
            <LoadingSpinner label="Loading outstanding orders" />
          ) : outstanding.length ? (
            <DataTable
              columns={historyColumns}
              data={outstanding}
              emptyMessage="No outstanding orders."
            />
          ) : !outstandingError ? (
            <p className="text-muted">No outstanding orders for this supplier.</p>
          ) : null}
          <h2 className="h4 mt-4">Purchase history</h2>
          <DataTable
            columns={historyColumns}
            data={history.items}
            emptyMessage="No purchase orders for this supplier."
            loading={history.loading}
          />
          <Pagination
            onPageChange={history.setPage}
            page={purchaseMeta?.page ?? history.page}
            pageSize={purchaseMeta?.page_size ?? history.pageSize}
            totalItems={purchaseMeta?.total ?? 0}
          />
        </>
      )}
    </section>
  )
}
