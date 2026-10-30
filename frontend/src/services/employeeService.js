import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated employee directory page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listEmployees(params, { signal } = {}) {
  const response = await apiClient.get('/employees/', { params, signal })
  return {
    items: getData(response).employees,
    meta: response.data.meta,
  }
}

/**
 * Fetch the employee record identified by its MongoDB ObjectId.
 *
 * @param {string} employeeId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getEmployee(employeeId, { signal } = {}) {
  const response = await apiClient.get(`/employees/${employeeId}/`, { signal })
  return getData(response).employee
}

/**
 * Create an employee using the validated API request fields.
 *
 * @param {object} values
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function createEmployee(values, { signal } = {}) {
  const response = await apiClient.post('/employees/', values, { signal })
  return getData(response).employee
}

/**
 * Partially update an employee.
 *
 * @param {string} employeeId
 * @param {object} values
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function updateEmployee(employeeId, values, { signal } = {}) {
  const response = await apiClient.patch(`/employees/${employeeId}/`, values, {
    signal,
  })
  return getData(response).employee
}

/**
 * Deactivate an employee without deleting its record.
 *
 * @param {string} employeeId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function deactivateEmployee(employeeId, { signal } = {}) {
  const response = await apiClient.delete(`/employees/${employeeId}/`, {
    signal,
  })
  return getData(response).employee
}

/**
 * Return the backend's current designation options.
 *
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<string[]>}
 */
export async function listDesignations({ signal } = {}) {
  const response = await apiClient.get('/employees/designations/', { signal })
  return getData(response).designations
}
