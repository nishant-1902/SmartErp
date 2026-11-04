import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch one immutable invoice snapshot.
 *
 * @param {string} invoiceId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getInvoice(invoiceId, { signal } = {}) {
  const response = await apiClient.get(`/invoices/${invoiceId}/`, { signal })
  return getData(response).invoice
}

/**
 * Fetch a paginated invoice page using validated API filters.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listInvoices(params, { signal } = {}) {
  const response = await apiClient.get('/invoices/', { params, signal })
  return { items: getData(response).invoices, meta: response.data.meta }
}
