import { useEffect, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import Button from 'react-bootstrap/Button'
import Form from 'react-bootstrap/Form'
import ConfirmDialog from '../components/ConfirmDialog.jsx'
import DataTable from '../components/DataTable.jsx'
import ErrorMessage from '../components/ErrorMessage.jsx'
import Pagination from '../components/Pagination.jsx'
import ProductFormModal from '../components/ProductFormModal.jsx'
import SearchBar from '../components/SearchBar.jsx'
import { useAuth } from '../hooks/useAuth.js'
import { usePaginatedList } from '../hooks/usePaginatedList.js'
import { useToast } from '../hooks/useToast.js'
import {
  createProduct,
  listProductCategories,
  listProducts,
  updateProduct,
} from '../services/productService.js'
import { getApiError } from '../utils/apiErrors.js'
import { formatMoney } from '../utils/formatMoney.js'

/**
 * Search and manage the product catalogue.
 *
 * @returns {JSX.Element}
 */
export default function Products() {
  const { hasPermission } = useAuth()
  const canWrite = hasPermission('products:write')
  const { showToast } = useToast()
  const list = usePaginatedList(listProducts)
  const { setFilter } = list
  const [searchParams] = useSearchParams()
  const [categories, setCategories] = useState([])
  const [categoriesError, setCategoriesError] = useState(null)
  const [editingProduct, setEditingProduct] = useState(null)
  const [formOpen, setFormOpen] = useState(false)
  const [statusProduct, setStatusProduct] = useState(null)
  const [statusBusy, setStatusBusy] = useState(false)

  useEffect(() => {
    const category = searchParams.get('category')
    if (category) setFilter('category', category)
  }, [searchParams, setFilter])

  useEffect(() => {
    const controller = new AbortController()
    listProductCategories({ signal: controller.signal })
      .then(setCategories)
      .catch((error) => {
        if (!controller.signal.aborted) setCategoriesError(error)
      })
    return () => controller.abort()
  }, [])

  function closeForm() {
    setFormOpen(false)
    setEditingProduct(null)
  }

  async function saveProduct(values) {
    if (editingProduct) {
      await updateProduct(editingProduct.id, values)
      showToast('Product updated successfully.')
    } else {
      await createProduct(values)
      showToast('Product created successfully.')
    }
    closeForm()
    list.refresh()
  }

  async function toggleActive() {
    if (!statusProduct) return
    setStatusBusy(true)
    const nextActive = !statusProduct.is_active
    try {
      await updateProduct(statusProduct.id, { is_active: nextActive })
      showToast(
        `${statusProduct.name} ${nextActive ? 'activated' : 'deactivated'}.`,
      )
      setStatusProduct(null)
      list.refresh()
    } catch (error) {
      showToast(getApiError(error).message, 'danger', 'Unable to update product')
    } finally {
      setStatusBusy(false)
    }
  }

  const columns = [
    {
      key: 'sku',
      label: 'SKU',
      sortable: true,
      render: (product) => (
        <Link to={`/products/${product.id}`}>{product.sku}</Link>
      ),
    },
    { key: 'name', label: 'Product', sortable: true },
    { key: 'category', label: 'Category', sortable: true },
    { key: 'unit', label: 'Unit', sortable: true },
    {
      key: 'selling_price',
      label: 'Selling price',
      render: (product) => formatMoney(product.selling_price),
    },
    {
      key: 'stock',
      label: 'On hand / reserved / available',
      render: (product) => (
        <span>
          {product.quantity_on_hand} / {product.reserved_quantity} /{' '}
          {product.quantity_on_hand - product.reserved_quantity}
        </span>
      ),
    },
    {
      key: 'is_active',
      label: 'Status',
      render: (product) => (
        <span
          className={`badge ${
            product.is_active ? 'text-bg-success' : 'text-bg-secondary'
          }`}
        >
          {product.is_active ? 'Active' : 'Inactive'}
        </span>
      ),
    },
    ...(canWrite
      ? [
          {
            key: 'actions',
            label: 'Actions',
            render: (product) => (
              <div className="d-flex flex-wrap gap-2">
                <Button
                  aria-label={`Edit ${product.name}`}
                  onClick={() => {
                    setEditingProduct(product)
                    setFormOpen(true)
                  }}
                  size="sm"
                  variant="outline-primary"
                >
                  Edit
                </Button>
                <Button
                  aria-label={`${product.is_active ? 'Deactivate' : 'Activate'} ${product.name}`}
                  onClick={() => setStatusProduct(product)}
                  size="sm"
                  variant="outline-secondary"
                >
                  {product.is_active ? 'Deactivate' : 'Activate'}
                </Button>
              </div>
            ),
          },
        ]
      : []),
  ]

  return (
    <section>
      <div className="page-heading d-flex flex-wrap align-items-end justify-content-between gap-3">
        <div>
          <p className="text-primary text-uppercase fw-bold small mb-2">Inventory</p>
          <h1>Products</h1>
          <p className="mb-0">Search and manage product details and status.</p>
        </div>
        {canWrite && (
          <Button
            onClick={() => {
              setEditingProduct(null)
              setFormOpen(true)
            }}
          >
            Add product
          </Button>
        )}
      </div>
      <div className="row g-3 align-items-center mb-3">
        <div className="col-12 col-lg-7">
          <SearchBar
            label="Search products"
            onSearch={list.setSearchInput}
            placeholder="Search product name or SKU"
          />
        </div>
        <div className="col-12 col-sm-6 col-lg-3">
          <Form.Select
            aria-label="Filter products by category"
            onChange={(event) => list.setFilter('category', event.target.value)}
            value={list.filters.category ?? ''}
          >
            <option value="">All categories</option>
            {categories.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </Form.Select>
        </div>
        <div className="col-12 col-sm-6 col-lg-2">
          <Form.Select
            aria-label="Filter products by status"
            onChange={(event) =>
              list.setFilter(
                'is_active',
                event.target.value === '' ? '' : event.target.value === 'true',
              )
            }
            value={
              list.filters.is_active === undefined
                ? ''
                : String(list.filters.is_active)
            }
          >
            <option value="">All statuses</option>
            <option value="true">Active</option>
            <option value="false">Inactive</option>
          </Form.Select>
        </div>
      </div>
      {categoriesError && (
        <ErrorMessage message={getApiError(categoriesError).message} />
      )}
      {list.error && <ErrorMessage message={getApiError(list.error).message} />}
      <DataTable
        columns={columns}
        data={list.items}
        emptyMessage="No products match your search and filters."
        loading={list.loading}
        onSort={list.setSorting}
        serverSideSorting
      />
      <Pagination
        onPageChange={list.setPage}
        page={list.meta.page ?? list.page}
        pageSize={list.meta.page_size ?? list.pageSize}
        totalItems={list.meta.total ?? 0}
      />
      {canWrite && formOpen && (
        <ProductFormModal
          onHide={closeForm}
          onSave={saveProduct}
          product={editingProduct}
          show
        />
      )}
      <ConfirmDialog
        busy={statusBusy}
        confirmLabel={statusProduct?.is_active ? 'Deactivate product' : 'Activate product'}
        confirmVariant={statusProduct?.is_active ? 'danger' : 'primary'}
        message={
          statusProduct?.is_active
            ? `Deactivate ${statusProduct.name}? It cannot be used on new orders.`
            : `Activate ${statusProduct?.name}?`
        }
        onCancel={() => setStatusProduct(null)}
        onConfirm={toggleActive}
        show={Boolean(statusProduct)}
        title="Change product status"
      />
    </section>
  )
}
