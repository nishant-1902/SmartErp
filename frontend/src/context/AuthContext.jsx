import { useCallback, useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AuthContext } from './authContext.js'
import {
  fetchCurrentUser,
  login as loginRequest,
  logout as logoutRequest,
  refreshSession,
} from '../services/authService.js'
import { setAccessToken, setAuthFailureHandler } from '../services/apiClient.js'

let sessionRestorePromise = null

function restoreSessionOnce() {
  if (!sessionRestorePromise) {
    sessionRestorePromise = (async () => {
      const session = await refreshSession()
      setAccessToken(session.access_token)
      const restoredUser = await fetchCurrentUser()
      return { user: restoredUser, accessToken: session.access_token }
    })().finally(() => {
      sessionRestorePromise = null
    })
  }
  return sessionRestorePromise
}

function normalizeUser(user) {
  if (!user || typeof user.role !== 'string' || !Array.isArray(user.permissions)) {
    throw new Error('The authentication response has an invalid user profile.')
  }
  return {
    ...user,
    permissions: [...user.permissions],
  }
}

export function AuthProvider({ children }) {
  const navigate = useNavigate()
  const [accessToken, setAccessTokenState] = useState(null)
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)

  const clearSession = useCallback(() => {
    setAccessToken(null)
    setAccessTokenState(null)
    setUser(null)
  }, [])

  useEffect(() => {
    let active = true

    setAuthFailureHandler(() => {
      clearSession()
      setLoading(false)
      navigate('/login', { replace: true })
    })

    restoreSessionOnce()
      .then((session) => {
        if (active) {
          setAccessTokenState(session.accessToken)
          setUser(normalizeUser(session.user))
        }
      })
      .catch(() => {
        setAccessToken(null)
        if (active) {
          setAccessTokenState(null)
          setUser(null)
        }
      })
      .finally(() => {
        if (active) {
          setLoading(false)
        }
      })

    return () => {
      active = false
      setAuthFailureHandler(null)
    }
  }, [clearSession, navigate])

  const login = useCallback(async (email, password) => {
    const session = await loginRequest(email, password)
    if (!session.access_token) {
      throw new Error('Login response did not contain an access token.')
    }
    const nextUser = normalizeUser(session.user)
    setAccessToken(session.access_token)
    setAccessTokenState(session.access_token)
    setUser(nextUser)
    setLoading(false)
    return nextUser
  }, [])

  const logout = useCallback(async () => {
    try {
      await logoutRequest()
    } finally {
      clearSession()
      setLoading(false)
      navigate('/login', { replace: true })
    }
  }, [clearSession, navigate])

  const value = useMemo(
    () => ({
      user,
      accessToken,
      role: user?.role ?? null,
      permissions: user?.permissions ?? [],
      loading,
      login,
      logout,
      hasPermission: (permission) => user?.permissions.includes(permission) ?? false,
    }),
    [accessToken, loading, login, logout, user],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}
