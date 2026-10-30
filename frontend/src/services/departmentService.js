import apiClient from './apiClient.js'

function getData(response) {
  return response.data.data
}

/**
 * Fetch a paginated department directory page.
 *
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listDepartments(params, { signal } = {}) {
  const response = await apiClient.get('/departments/', { params, signal })
  return {
    items: getData(response).departments,
    meta: response.data.meta,
  }
}

/**
 * Fetch one department by its MongoDB ObjectId.
 *
 * @param {string} departmentId
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function getDepartment(departmentId, { signal } = {}) {
  const response = await apiClient.get(`/departments/${departmentId}/`, {
    signal,
  })
  return getData(response).department
}

/**
 * Create a department.
 *
 * @param {object} values
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function createDepartment(values, { signal } = {}) {
  const response = await apiClient.post('/departments/', values, { signal })
  return getData(response).department
}

/**
 * Partially update a department.
 *
 * @param {string} departmentId
 * @param {object} values
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<object>}
 */
export async function updateDepartment(
  departmentId,
  values,
  { signal } = {},
) {
  const response = await apiClient.patch(
    `/departments/${departmentId}/`,
    values,
    { signal },
  )
  return getData(response).department
}

/**
 * Fetch one page of employees assigned to a department.
 *
 * @param {string} departmentId
 * @param {object} params
 * @param {{signal?: AbortSignal}} options
 * @returns {Promise<{items: object[], meta: object}>}
 */
export async function listDepartmentEmployees(
  departmentId,
  params,
  { signal } = {},
) {
  const response = await apiClient.get(
    `/departments/${departmentId}/employees/`,
    { params, signal },
  )
  return {
    items: getData(response).employees,
    meta: response.data.meta,
  }
}
