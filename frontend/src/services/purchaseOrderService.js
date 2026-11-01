import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated purchase-order list with supported server filters.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listPurchaseOrders(params, { signal } = {}) {
  const response = await apiClient.get('/purchase-orders/', { params, signal })
  return {
    items: getData(response).purchase_orders,
    meta: response.data.meta,
  }
}

/**
 * Fetch one purchase order.
 *
 * @param {string} purchaseOrderId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getPurchaseOrder(purchaseOrderId, { signal } = {}) {
  const response = await apiClient.get(`/purchase-orders/${purchaseOrderId}/`, {
    signal,
  })
  return getData(response).purchase_order
}

/**
 * Create a purchase order; all final totals are calculated by the server.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createPurchaseOrder(values) {
  const response = await apiClient.post('/purchase-orders/', values)
  return getData(response).purchase_order
}

/**
 * Update a Draft purchase order.
 *
 * @param {string} purchaseOrderId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updatePurchaseOrder(purchaseOrderId, values) {
  const response = await apiClient.patch(
    `/purchase-orders/${purchaseOrderId}/`,
    values,
  )
  return getData(response).purchase_order
}

/**
 * Run a state transition on a purchase order.
 *
 * @param {string} purchaseOrderId
 * @param {'submit'|'approve'|'reject'|'cancel'} action
 * @param {object} [values]
 * @returns {Promise<object>}
 */
export async function transitionPurchaseOrder(
  purchaseOrderId,
  action,
  values = {},
) {
  const response = await apiClient.post(
    `/purchase-orders/${purchaseOrderId}/${action}/`,
    values,
  )
  return getData(response).purchase_order
}

/**
 * Record a receipt with its idempotency key.
 *
 * @param {string} purchaseOrderId
 * @param {object} values
 * @param {string} idempotencyKey
 * @returns {Promise<object>}
 */
export async function receivePurchaseOrder(
  purchaseOrderId,
  values,
  idempotencyKey,
) {
  const response = await apiClient.post(
    `/purchase-orders/${purchaseOrderId}/receive/`,
    values,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return getData(response).purchase_receipt
}
