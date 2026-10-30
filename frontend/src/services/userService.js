import apiClient from './apiClient.js'

function responseData(response) {
  return response.data.data
}

/**
 * Fetch a paginated, filtered list of user accounts.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listUsers(params, { signal } = {}) {
  const response = await apiClient.get('/users/', { params, signal })
  return { items: responseData(response).users, meta: response.data.meta }
}

/**
 * Create an account with the validated user-management fields.
 *
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function createUser(values) {
  const response = await apiClient.post('/users/', values)
  return responseData(response).user
}

/**
 * Update an account's profile, role, or employee link.
 *
 * @param {string} userId
 * @param {object} values
 * @returns {Promise<object>}
 */
export async function updateUser(userId, values) {
  const response = await apiClient.patch(`/users/${userId}/`, values)
  return responseData(response).user
}

/**
 * Activate a previously inactive account.
 *
 * @param {string} userId
 * @returns {Promise<object>}
 */
export async function activateUser(userId) {
  const response = await apiClient.post(`/users/${userId}/activate/`, {})
  return responseData(response).user
}

/**
 * Deactivate an account without deleting it.
 *
 * @param {string} userId
 * @returns {Promise<object>}
 */
export async function deactivateUser(userId) {
  const response = await apiClient.post(`/users/${userId}/deactivate/`, {})
  return responseData(response).user
}

/**
 * Start the administrator-initiated password-reset flow for an account.
 *
 * @param {string} userId
 * @returns {Promise<object>}
 */
export async function resetUserPassword(userId) {
  const response = await apiClient.post(`/users/${userId}/reset-password/`, {})
  return responseData(response)
}
