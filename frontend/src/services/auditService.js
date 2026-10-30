import apiClient from './apiClient.js'

function responseData(response) {
  return response.data.data
}

function asDateTime(value, endOfDay = false) {
  if (!value) return undefined
  const time = endOfDay ? '23:59:59.999' : '00:00:00.000'
  return `${value}T${time}Z`
}

/**
 * Fetch a filtered, paginated page of audit events.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listAuditLogs(params, { signal } = {}) {
  const query = {
    ...params,
    ...(params.start_date
      ? { start_date: asDateTime(params.start_date) }
      : {}),
    ...(params.end_date
      ? { end_date: asDateTime(params.end_date, true) }
      : {}),
  }
  const response = await apiClient.get('/audit-logs/', { params: query, signal })
  return { items: responseData(response).audit_logs, meta: response.data.meta }
}
