import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated supplier directory page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listSuppliers(params, { signal } = {}) {
  const response = await apiClient.get('/suppliers/', { params, signal })
  return { items: getData(response).suppliers, meta: response.data.meta }
}

/**
 * Fetch one supplier.
 *
 * @param {string} supplierId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getSupplier(supplierId, { signal } = {}) {
  const response = await apiClient.get(`/suppliers/${supplierId}/`, { signal })
  return getData(response).supplier
}

/**
 * Create a supplier.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createSupplier(values) {
  const response = await apiClient.post('/suppliers/', values)
  return getData(response).supplier
}

/**
 * Update supplier information or status.
 *
 * @param {string} supplierId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updateSupplier(supplierId, values) {
  const response = await apiClient.patch(`/suppliers/${supplierId}/`, values)
  return getData(response).supplier
}

/**
 * Fetch purchase history and outstanding orders for a supplier.
 *
 * @param {string} supplierId
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], outstanding: object[], meta: object}>}
 */
export async function listSupplierPurchaseOrders(
  supplierId,
  params,
  { signal } = {},
) {
  const response = await apiClient.get(
    `/suppliers/${supplierId}/purchase-orders/`,
    { params, signal },
  )
  const data = getData(response)
  return {
    items: data.purchase_orders,
    outstanding: data.outstanding_purchase_orders,
    meta: response.data.meta,
  }
}
