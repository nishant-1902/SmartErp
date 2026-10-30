import axios from 'axios'

let accessToken = null
let refreshPromise = null
let authFailureHandler = null

const apiClient = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL,
  withCredentials: true,
  headers: {
    Accept: 'application/json',
    'Content-Type': 'application/json',
    'X-Requested-With': 'XMLHttpRequest',
  },
})

export function setAccessToken(token) {
  accessToken = token || null
}

export function getAccessToken() {
  return accessToken
}

export function setAuthFailureHandler(handler) {
  authFailureHandler = handler
}

function isAuthEndpoint(url = '') {
  return /\/auth\/(?:login|refresh)\/?(?:[?#]|$)/.test(url)
}

function refreshAccessToken() {
  if (!refreshPromise) {
    refreshPromise = apiClient
      .post('/auth/refresh/', null, { skipAuthRefresh: true })
      .then(({ data }) => {
        const token = data?.data?.access_token
        if (!token) {
          throw new Error('Refresh response did not contain an access token.')
        }
        setAccessToken(token)
        return token
      })
      .finally(() => {
        refreshPromise = null
      })
  }
  return refreshPromise
}

function handleAuthFailure() {
  setAccessToken(null)
  if (authFailureHandler) {
    authFailureHandler()
  } else if (window.location.pathname !== '/login') {
    window.location.assign('/login')
  }
}

apiClient.interceptors.request.use((config) => {
  config.headers.set('X-Requested-With', 'XMLHttpRequest')
  if (accessToken) {
    config.headers.set('Authorization', `Bearer ${accessToken}`)
  } else {
    config.headers.delete('Authorization')
  }
  return config
})

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const config = error.config
    if (error.response?.status !== 401 || !config) {
      return Promise.reject(error)
    }
    if (isAuthEndpoint(config.url) || config.skipAuthRefresh) {
      return Promise.reject(error)
    }
    if (config._authRetry) {
      handleAuthFailure()
      return Promise.reject(error)
    }

    config._authRetry = true
    try {
      const token = await refreshAccessToken()
      config.headers.set('Authorization', `Bearer ${token}`)
      return apiClient(config)
    } catch (refreshError) {
      handleAuthFailure()
      return Promise.reject(refreshError)
    }
  },
)

export default apiClient
