import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a filtered sales-order page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listSalesOrders(params, { signal } = {}) {
  const response = await apiClient.get('/sales-orders/', { params, signal })
  return { items: getData(response).sales_orders, meta: response.data.meta }
}

/**
 * Fetch one sales order.
 *
 * @param {string} salesOrderId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getSalesOrder(salesOrderId, { signal } = {}) {
  const response = await apiClient.get(`/sales-orders/${salesOrderId}/`, {
    signal,
  })
  return getData(response).sales_order
}

/**
 * Create a sales-order draft.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createSalesOrder(values) {
  const response = await apiClient.post('/sales-orders/', values)
  return getData(response).sales_order
}

/**
 * Update a draft sales order.
 *
 * @param {string} salesOrderId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updateSalesOrder(salesOrderId, values) {
  const response = await apiClient.patch(
    `/sales-orders/${salesOrderId}/`,
    values,
  )
  return getData(response).sales_order
}

/**
 * Run a sales-order state transition.
 *
 * @param {string} salesOrderId
 * @param {'confirm'|'cancel'} action
 * @returns {Promise<object>}
 */
export async function transitionSalesOrder(salesOrderId, action) {
  const response = await apiClient.post(
    `/sales-orders/${salesOrderId}/${action}/`,
    {},
  )
  return getData(response).sales_order
}

/**
 * Fulfil an order with a caller-provided idempotency key.
 *
 * @param {string} salesOrderId
 * @param {string} idempotencyKey
 * @returns {Promise<{sales_order: object, invoice: object}>}
 */
export async function fulfilSalesOrder(salesOrderId, idempotencyKey) {
  const response = await apiClient.post(
    `/sales-orders/${salesOrderId}/fulfill/`,
    {},
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return getData(response)
}

/**
 * Record a payment with a caller-provided idempotency key.
 *
 * @param {string} salesOrderId
 * @param {object} values
 * @param {string} idempotencyKey
 * @returns {Promise<{payment: object, sales_order: object}>}
 */
export async function recordSalesOrderPayment(
  salesOrderId,
  values,
  idempotencyKey,
) {
  const response = await apiClient.post(
    `/sales-orders/${salesOrderId}/payments/`,
    values,
    { headers: { 'Idempotency-Key': idempotencyKey } },
  )
  return getData(response)
}

/**
 * Record a return for a fulfilled order.
 *
 * @param {string} salesOrderId
 * @param {object} values
 * @returns {Promise<{sales_return: object, sales_order: object}>}
 */
export async function returnSalesOrderItems(salesOrderId, values) {
  const response = await apiClient.post(
    `/sales-orders/${salesOrderId}/returns/`,
    values,
  )
  return getData(response)
}
