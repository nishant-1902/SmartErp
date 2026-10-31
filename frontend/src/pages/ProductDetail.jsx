import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import Alert from 'react-bootstrap/Alert'
import Button from 'react-bootstrap/Button'
import Card from 'react-bootstrap/Card'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import StockAdjustmentModal from '../components/StockAdjustmentModal.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import {
  adjustStock,
  getProduct,
  listStockMovements,
} from '../services/productService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

function formatDate(value) {
  const date = new Date(value)
  return Number.isNaN(date.getTime())
    ? '—'
    : new Intl.DateTimeFormat(undefined, {
        dateStyle: 'medium',
        timeStyle: 'short',
      }).format(date)
}

/**
 * Show product information, stock totals, and its movement history.
 *
 * @returns {JSX.Element}
 */
export default function ProductDetail() {
  const { productId } = useParams()
  const { hasPermission } = useAuth()
  const canAdjust = hasPermission('stock:adjust')
  const { showToast } = useToast()
  const [refreshKey, setRefreshKey] = useState(0)
  const [productResult, setProductResult] = useState({
    key: null,
    product: null,
    error: null,
  })
  const [adjustmentOpen, setAdjustmentOpen] = useState(false)
  const productRequestKey = `${productId}:${refreshKey}`
  const fetchMovements = useCallback(
    (params, options) =>
      listStockMovements({ ...params, product: productId }, options),
    [productId],
  )
  const movements = usePaginatedList(fetchMovements, { scopeKey: productId })

  useEffect(() => {
    const controller = new AbortController()
    getProduct(productId, { signal: controller.signal })
      .then((product) => {
        if (!controller.signal.aborted) {
          setProductResult({ key: productRequestKey, product, error: null })
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setProductResult({ key: productRequestKey, product: null, error })
        }
      })
    return () => controller.abort()
  }, [productId, productRequestKey])

  async function submitAdjustment(values, key) {
    await adjustStock(values, key)
    showToast('Stock adjustment applied.')
    setRefreshKey((current) => current + 1)
    movements.refresh()
  }

  const columns = [
    { key: 'created_at', label: 'Date', render: (row) => formatDate(row.created_at) },
    { key: 'movement_type', label: 'Type' },
    { key: 'quantity_change', label: 'Quantity change' },
    { key: 'quantity_before', label: 'Before' },
    { key: 'quantity_after', label: 'After' },
    { key: 'reason', label: 'Reason' },
    { key: 'performed_by', label: 'Performed by' },
  ]

  const productLoading = productResult.key !== productRequestKey
  const productError = productLoading ? null : productResult.error
  const product = productLoading ? null : productResult.product

  if (productLoading) return <p role="status">Loading product…</p>
  if (productError) {
    return (
      <section>
        <ErrorMessage message={getApiError(productError).message} />
        <Link to="/products">Back to products</Link>
      </section>
    )
  }
  if (!product) return null

  const available = product.quantity_on_hand - product.reserved_quantity
  const lowStock = available <= product.min_stock_level

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">
            <Link to="/products">Products</Link> / {product.sku}
          </p>
          <h1>{product.name}</h1>
          <p className="mb-0">{product.description || 'No description provided.'}</p>
          <p className="small text-muted mt-2 mb-0">
            Product ID: <code>{product.id}</code> · Category: {product.category}
          </p>
        </div>
        {canAdjust && (
          <Button onClick={() => setAdjustmentOpen(true)}>
            Adjust stock
          </Button>
        )}
      </div>
      {lowStock && (
        <Alert className="mt-3" variant="warning">
          Available stock is at or below the minimum stock level.
        </Alert>
      )}
      <div className="row g-3 my-2">
        <div className="col-12 col-md-6 col-xl-3">
          <Card className="h-100">
            <Card.Body>
              <Card.Subtitle className="mb-2 text-muted">On hand</Card.Subtitle>
              <Card.Title>{product.quantity_on_hand} {product.unit}</Card.Title>
            </Card.Body>
          </Card>
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <Card className="h-100">
            <Card.Body>
              <Card.Subtitle className="mb-2 text-muted">Reserved</Card.Subtitle>
              <Card.Title>{product.reserved_quantity} {product.unit}</Card.Title>
            </Card.Body>
          </Card>
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <Card className="h-100">
            <Card.Body>
              <Card.Subtitle className="mb-2 text-muted">Available</Card.Subtitle>
              <Card.Title>{available} {product.unit}</Card.Title>
            </Card.Body>
          </Card>
        </div>
        <div className="col-12 col-md-6 col-xl-3">
          <Card className="h-100">
            <Card.Body>
              <Card.Subtitle className="mb-2 text-muted">Selling price</Card.Subtitle>
              <Card.Title>{formatMoney(product.selling_price)}</Card.Title>
            </Card.Body>
          </Card>
        </div>
      </div>
      <h2 className="h4 mt-4">Stock movement history</h2>
      {movements.error && (
        <ErrorMessage message={getApiError(movements.error).message} />
      )}
      <DataTable
        columns={columns}
        data={movements.items}
        emptyMessage="No stock movements have been recorded for this product."
        loading={movements.loading}
      />
      <Pagination
        onPageChange={movements.setPage}
        page={movements.meta.page ?? movements.page}
        pageSize={movements.meta.page_size ?? movements.pageSize}
        totalItems={movements.meta.total ?? 0}
      />
      <StockAdjustmentModal
        onHide={() => setAdjustmentOpen(false)}
        onSubmit={submitAdjustment}
        product={product}
        show={adjustmentOpen}
      />
    </section>
  )
}
