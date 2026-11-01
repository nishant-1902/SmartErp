import { useEffect, useState } from 'react'
import Form from 'react-bootstrap/Form'
import ErrorMessage from './ErrorMessage.jsx'
import { listProducts } from '../services/productService.js'
import { getApiError } from '../utils/apiErrors.js'

/**
 * Search active catalogue products and select one for a purchase-order line.
 *
 * @param {{index: number, value: string, label: string, onSelect: (product: object) => void}} props
 */
export default function PurchaseOrderProductPicker({
  index,
  value,
  label,
  onSelect,
}) {
  const [search, setSearch] = useState('')
  const [products, setProducts] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    if (!search.trim()) return undefined

    const controller = new AbortController()
    const timeout = window.setTimeout(() => {
      setLoading(true)
      listProducts(
        { page: 1, page_size: 20, search: search.trim(), is_active: true },
        { signal: controller.signal },
      )
        .then(({ items }) => setProducts(items))
        .catch((requestError) => {
          if (!controller.signal.aborted) {
            setError(getApiError(requestError).message)
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setLoading(false)
        })
    }, 250)

    return () => {
      window.clearTimeout(timeout)
      controller.abort()
    }
  }, [search])

  const selectedProduct = products.find((product) => product.id === value)

  return (
    <div>
      <Form.Label htmlFor={`product-search-${index}`}>Product</Form.Label>
      <Form.Control
        autoComplete="off"
        id={`product-search-${index}`}
        onChange={(event) => {
          setSearch(event.target.value)
          setError('')
          setLoading(Boolean(event.target.value.trim()))
          if (!event.target.value.trim()) setProducts([])
        }}
        placeholder="Search by product name or SKU"
        value={search}
      />
      {loading && <div className="form-text">Searching active products…</div>}
      {error && <ErrorMessage message={error} />}
      {search.trim() && !loading && !error && (
        <Form.Select
          aria-label={`Select product for line ${index + 1}`}
          className="mt-2"
          onChange={(event) => {
            const product = products.find((item) => item.id === event.target.value)
            if (product) {
              onSelect(product)
              setSearch('')
            }
          }}
          value=""
        >
          <option value="">
            {products.length ? 'Choose a product' : 'No active products found'}
          </option>
          {products.map((product) => (
            <option key={product.id} value={product.id}>
              {product.name} ({product.sku})
            </option>
          ))}
        </Form.Select>
      )}
      <div className="form-text" aria-live="polite">
        {selectedProduct
          ? `${selectedProduct.name} (${selectedProduct.sku})`
          : value
            ? label
            : 'No product selected'}
      </div>
    </div>
  )
}
