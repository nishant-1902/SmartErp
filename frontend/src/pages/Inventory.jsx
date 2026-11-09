import { Link, useSearchParams } from 'react-router-dom'
import { useEffect, useState } from 'react'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import StockAdjustmentModal from '../components/StockAdjustmentModal.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import {
  adjustStock,
  listProducts,
} from '../services/productService.js'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Show on-hand, reserved, and available inventory with low-stock warnings.
 *
 * @returns {JSX.Element}
 */
export default function Inventory() {
  const { hasPermission } = useAuth()
  const canAdjust = hasPermission('stock:adjust')
  const { showToast } = useToast()
  const list = usePaginatedList(listProducts)
  const { setFilter } = list
  const [searchParams] = useSearchParams()
  const [adjustingProduct, setAdjustingProduct] = useState(null)

  useEffect(() => {
    const lowStock = searchParams.get('low_stock')
    if (lowStock === 'true') setFilter('low_stock', 'true')
  }, [searchParams, setFilter])

  async function submitAdjustment(values, key) {
    await adjustStock(values, key)
    showToast('Stock adjustment applied.')
    setAdjustingProduct(null)
    list.refresh()
  }

  const columns = [
    {
      key: 'sku',
      label: 'SKU',
      render: (product) => (
        <Link to={`/products/${product.id}`}>{product.sku}</Link>
      ),
    },
    { key: 'name', label: 'Product' },
    { key: 'category', label: 'Category' },
    { key: 'quantity_on_hand', label: 'On hand' },
    { key: 'reserved_quantity', label: 'Reserved' },
    {
      key: 'available',
      label: 'Available',
      render: (product) => product.quantity_on_hand - product.reserved_quantity,
    },
    { key: 'min_stock_level', label: 'Minimum' },
    {
      key: 'stock_status',
      label: 'Stock status',
      render: (product) => {
        const available = product.quantity_on_hand - product.reserved_quantity
        const lowStock = available <= product.min_stock_level
        return (
          <span
            className={`badge ${lowStock ? 'text-bg-warning' : 'text-bg-success'}`}
          >
            {lowStock ? 'Low stock' : 'In stock'}
          </span>
        )
      },
    },
    ...(canAdjust
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (product) => (
              <Button
                aria-label={`Adjust stock for ${product.name}`}
                onClick={() => setAdjustingProduct(product)}
                size="sm"
                variant="outline-primary"
              >
                Adjust
              </Button>
            ),
          },
        ]
      : []),
  ]

  return (
    <section>
      <div className="page-heading">
        <p className="text-primary text-uppercase fw-bold small mb-2">Inventory</p>
        <h1>Inventory</h1>
        <p className="mb-0">
          Review on-hand, reserved, and available stock. Low stock uses available units.
        </p>
      </div>
      <div className="row g-3 mb-3">
        <div className="col-12 col-md-5">
          <Form.Select
            aria-label="Filter inventory by stock level"
            onChange={(event) => list.setFilter('low_stock', event.target.value)}
            value={list.filters.low_stock ?? ''}
          >
            <option value="">All stock levels</option>
            <option value="true">Low stock only</option>
          </Form.Select>
        </div>
      </div>
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No products match this inventory filter."
        loading={list.loading}
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />
      <StockAdjustmentModal
        onHide={() => setAdjustingProduct(null)}
        onSubmit={submitAdjustment}
        product={adjustingProduct}
        show={Boolean(adjustingProduct)}
      />
    </section>
  )
}
