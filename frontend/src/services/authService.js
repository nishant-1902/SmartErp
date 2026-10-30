import apiClient from './apiClient.js'

function responseData(response) {
  return response.data.data
}

export async function login(email, password) {
  const response = await apiClient.post('/auth/login/', { email, password })
  return responseData(response)
}

export async function refreshSession() {
  const response = await apiClient.post('/auth/refresh/', null, {
    skipAuthRefresh: true,
  })
  return responseData(response)
}

export async function fetchCurrentUser() {
  const response = await apiClient.get('/auth/me/', {
    skipAuthRefresh: true,
  })
  return responseData(response).user
}

export async function logout() {
  const response = await apiClient.post('/auth/logout/')
  return responseData(response)
}
