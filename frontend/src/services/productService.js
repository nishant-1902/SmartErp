import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated product catalogue page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listProducts(params, { signal } = {}) {
  const response = await apiClient.get('/products/', { params, signal })
  return { items: getData(response).products, meta: response.data.meta }
}

/**
 * Fetch one product by its MongoDB ObjectId.
 *
 * @param {string} productId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getProduct(productId, { signal } = {}) {
  const response = await apiClient.get(`/products/${productId}/`, { signal })
  return getData(response).product
}

/**
 * Create a product with validated catalogue fields.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createProduct(values) {
  const response = await apiClient.post('/products/', values)
  return getData(response).product
}

/**
 * Partially update a product; stock quantities and SKU are not accepted here.
 *
 * @param {string} productId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updateProduct(productId, values) {
  const response = await apiClient.patch(`/products/${productId}/`, values)
  return getData(response).product
}

/**
 * Return the backend's distinct product categories.
 *
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<string[]>}
 */
export async function listProductCategories({ signal } = {}) {
  const response = await apiClient.get('/products/categories/', { signal })
  return getData(response).categories
}

/**
 * Return the low-stock product page with optional validated filters.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listLowStockProducts(params = {}, { signal } = {}) {
  const response = await apiClient.get('/products/low-stock/', { params, signal })
  return { items: getData(response).products, meta: response.data.meta }
}

/**
 * Apply a stock adjustment using a caller-generated idempotency key.
 *
 * @param {{product_id: string, quantity_change: number, reason: string}} values
 * @param {string} idempotencyKey
 * @returns {Promise<object>}
 */
export async function adjustStock(values, idempotencyKey) {
  const response = await apiClient.post('/stock-adjustments/', values, {
    headers: { 'Idempotency-Key': idempotencyKey },
  })
  return getData(response).stock_movement
}

/**
 * Fetch a filtered, paginated stock movement page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listStockMovements(params, { signal } = {}) {
  const response = await apiClient.get('/stock-movements/', { params, signal })
  return {
    items: getData(response).stock_movements,
    meta: response.data.meta,
  }
}
