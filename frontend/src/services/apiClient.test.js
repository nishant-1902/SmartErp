import { afterEach, describe, expect, it, vi } from 'vitest'
import apiClient, {
  getAccessToken,
  setAccessToken,
  setAuthFailureHandler,
} from './apiClient.js'

const originalAdapter = apiClient.defaults.adapter

afterEach(() => {
  setAccessToken(null)
  setAuthFailureHandler(null)
  apiClient.defaults.adapter = originalAdapter
})

describe('apiClient authentication', () => {
  it('adds the in-memory bearer token and X-Requested-With header', async () => {
    let requestConfig
    apiClient.defaults.adapter = async (config) => {
      requestConfig = config
      return { status: 200, data: {}, headers: {}, config }
    }
    setAccessToken('memory-token')

    await apiClient.get('/employees/')

    expect(requestConfig.headers.get('Authorization')).toBe('Bearer memory-token')
    expect(requestConfig.headers.get('X-Requested-With')).toBe('XMLHttpRequest')
    expect(apiClient.defaults.withCredentials).toBe(true)
    expect(localStorage.getItem('access_token')).toBeNull()
  })

  it('refreshes once for parallel 401 responses and retries both requests', async () => {
    let refreshCalls = 0
    let unauthorizedCalls = 0
    const originalToken = 'expired-token'
    const failureHandler = vi.fn()

    apiClient.defaults.adapter = async (config) => {
      if (config.url.includes('/auth/refresh/')) {
        refreshCalls += 1
        await new Promise((resolve) => setTimeout(resolve, 5))
        return {
          status: 200,
          data: { success: true, data: { access_token: 'fresh-token' } },
          headers: {},
          config,
        }
      }

      const requestToken = config.headers.get('Authorization')
      if (requestToken === `Bearer ${originalToken}`) {
        unauthorizedCalls += 1
        const error = new Error('Unauthorized')
        error.config = config
        error.response = { status: 401, config, data: {} }
        throw error
      }

      return { status: 200, data: { ok: true }, headers: {}, config }
    }
    setAccessToken(originalToken)
    setAuthFailureHandler(failureHandler)

    const responses = await Promise.all([
      apiClient.get('/employees/'),
      apiClient.get('/departments/'),
    ])

    expect(refreshCalls).toBe(1)
    expect(unauthorizedCalls).toBe(2)
    expect(responses).toHaveLength(2)
    expect(responses.every((response) => response.data.ok)).toBe(true)
    expect(getAccessToken()).toBe('fresh-token')
    expect(failureHandler).not.toHaveBeenCalled()
  })

  it('retries the original request with the refreshed bearer token', async () => {
    const requestTokens = []
    let refreshCalls = 0
    apiClient.defaults.adapter = async (config) => {
      if (config.url.includes('/auth/refresh/')) {
        refreshCalls += 1
        return {
          status: 200,
          data: { success: true, data: { access_token: 'fresh-token' } },
          headers: {},
          config,
        }
      }

      requestTokens.push(config.headers.get('Authorization'))
      if (config.headers.get('Authorization') === 'Bearer expired-token') {
        const error = new Error('Unauthorized')
        error.config = config
        error.response = { status: 401, config, data: {} }
        throw error
      }
      return { status: 200, data: { ok: true }, headers: {}, config }
    }
    setAccessToken('expired-token')

    await expect(apiClient.get('/employees/')).resolves.toMatchObject({
      data: { ok: true },
    })

    expect(requestTokens).toEqual(['Bearer expired-token', 'Bearer fresh-token'])
    expect(refreshCalls).toBe(1)
    expect(getAccessToken()).toBe('fresh-token')
  })

  it.each(['/auth/login/', '/auth/refresh/'])(
    'does not try to refresh after a 401 from %s',
    async (url) => {
      const requestUrls = []
      apiClient.defaults.adapter = async (config) => {
        requestUrls.push(config.url)
        const error = new Error('Unauthorized')
        error.config = config
        error.response = { status: 401, config, data: {} }
        throw error
      }

      await expect(apiClient.post(url)).rejects.toMatchObject({
        response: { status: 401 },
      })

      expect(requestUrls).toEqual([url])
    },
  )

  it('clears the token and notifies the app if refresh fails', async () => {
    const failureHandler = vi.fn()
    apiClient.defaults.adapter = async (config) => {
      const status = config.url.includes('/auth/refresh/') ? 401 : 401
      const error = new Error('Unauthorized')
      error.config = config
      error.response = { status, config, data: {} }
      throw error
    }
    setAccessToken('expired-token')
    setAuthFailureHandler(failureHandler)

    await expect(apiClient.get('/employees/')).rejects.toThrow('Unauthorized')

    expect(getAccessToken()).toBeNull()
    expect(failureHandler).toHaveBeenCalledOnce()
  })

  it('logs out after the single retry also returns 401', async () => {
    const failureHandler = vi.fn()
    apiClient.defaults.adapter = async (config) => {
      if (config.url.includes('/auth/refresh/')) {
        return {
          status: 200,
          data: { success: true, data: { access_token: 'fresh-token' } },
          headers: {},
          config,
        }
      }
      const error = new Error('Unauthorized')
      error.config = config
      error.response = { status: 401, config, data: {} }
      throw error
    }
    setAccessToken('expired-token')
    setAuthFailureHandler(failureHandler)

    await expect(apiClient.get('/employees/')).rejects.toThrow('Unauthorized')

    expect(getAccessToken()).toBeNull()
    expect(failureHandler).toHaveBeenCalledOnce()
  })
})
