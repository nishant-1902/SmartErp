import apiClient from './apiClient.js'

const reportPaths = {
  sales: '/reports/sales/',
  inventory: '/reports/inventory/',
  lowStock: '/reports/low-stock/',
  purchases: '/reports/purchases/',
  employees: '/reports/employees/',
}

const listKeys = {
  sales: 'sales',
  lowStock: 'low_stock',
  purchases: 'purchases',
  employees: 'employees',
}

function getData(response) {
  return response.data.data
}

/**
 * Fetch dashboard widgets filtered by the current user's report permissions.
 *
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getDashboard({ signal } = {}) {
  const response = await apiClient.get('/reports/dashboard/', { signal })
  return getData(response).dashboard
}

/**
 * Fetch one allowlisted report page.
 *
 * @param {'sales'|'lowStock'|'purchases'|'employees'} report
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listReport(report, params, { signal } = {}) {
  const path = reportPaths[report]
  const key = listKeys[report]
  if (!path || !key) {
    throw new TypeError('Unsupported report type.')
  }
  const response = await apiClient.get(path, { params, signal })
  return { items: getData(response)[key], meta: response.data.meta }
}

/**
 * Fetch current inventory summary values.
 *
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getInventorySummary({ signal } = {}) {
  const response = await apiClient.get(reportPaths.inventory, { signal })
  return getData(response).inventory
}
