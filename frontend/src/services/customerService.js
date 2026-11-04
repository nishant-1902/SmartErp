import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated customer directory.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listCustomers(params, { signal } = {}) {
  const response = await apiClient.get('/customers/', { params, signal })
  return { items: getData(response).customers, meta: response.data.meta }
}

/**
 * Fetch one customer record.
 *
 * @param {string} customerId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getCustomer(customerId, { signal } = {}) {
  const response = await apiClient.get(`/customers/${customerId}/`, { signal })
  return getData(response).customer
}

/**
 * Create a customer.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createCustomer(values) {
  const response = await apiClient.post('/customers/', values)
  return getData(response).customer
}

/**
 * Update an existing customer.
 *
 * @param {string} customerId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updateCustomer(customerId, values) {
  const response = await apiClient.patch(`/customers/${customerId}/`, values)
  return getData(response).customer
}

/**
 * Fetch a customer's paginated sales-order history.
 *
 * @param {string} customerId
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listCustomerSalesOrders(
  customerId,
  params,
  { signal } = {},
) {
  const response = await apiClient.get(
    `/customers/${customerId}/sales-orders/`,
    { params, signal },
  )
  return { items: getData(response).sales_orders, meta: response.data.meta }
}
