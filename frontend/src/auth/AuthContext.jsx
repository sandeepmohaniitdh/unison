import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import { api, setUnauthorizedHandler } from '../api/client'
import { shouldEndSession } from './session'

// Who is logged in, for every page. The session itself is an HttpOnly cookie set by the
// backend; the browser sends it with each request, so the frontend never sees it.
//
//   const { user, login, logout, unread } = useAuth()

const AuthContext = createContext(null)

const POLL_MS = 30000 // the bell polls the unread count every 30 seconds

export function primaryEmail(user) {
  return user?.emails?.find((e) => e.is_primary)?.email ?? user?.emails?.[0]?.email ?? ''
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [status, setStatus] = useState('loading') // loading | in | out
  const [unread, setUnread] = useState(0)
  const [joinRequests, setJoinRequests] = useState(0)
  // True after the user clicked "Log out": the next person to log in starts on their own
  // dashboard, not on the page the previous user was looking at.
  const [signedOut, setSignedOut] = useState(false)
  const statusRef = useRef(status)
  statusRef.current = status

  const refresh = useCallback(async () => {
    try {
      if (shouldEndSession()) await api.post('/auth/logout').catch(() => null)
      const me = await api.get('/users/me')
      setUser(me)
      setStatus('in')
      return me
    } catch {
      setUser(null)
      setStatus('out')
      return null
    }
  }, [])

  useEffect(() => {
    refresh()
  }, [refresh])

  // Any 401 (session ended, logged out elsewhere) shows the app as logged out.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      if (statusRef.current === 'in') {
        setUser(null)
        setStatus('out')
      }
    })
    return () => setUnauthorizedHandler(null)
  }, [])

  const refreshCounts = useCallback(async () => {
    if (statusRef.current !== 'in') return
    try {
      const data = await api.get('/notifications/unread-count')
      setUnread(data.unread)
    } catch {
      // keep the last number
    }
  }, [])

  const refreshJoinRequests = useCallback(async (role) => {
    if (role !== 'teacher' && role !== 'admin') return
    try {
      const dash = await api.get('/dashboards/teacher')
      setJoinRequests(dash.courses.reduce((sum, c) => sum + c.pending_join_requests, 0))
    } catch {
      setJoinRequests(0)
    }
  }, [])

  useEffect(() => {
    if (status !== 'in' || user?.must_change_password) return undefined
    refreshCounts()
    if (user?.role === 'teacher') refreshJoinRequests(user.role)
    const timer = setInterval(() => {
      if (document.visibilityState !== 'hidden') refreshCounts()
    }, POLL_MS)
    return () => clearInterval(timer)
  }, [status, user?.role, user?.must_change_password, refreshCounts, refreshJoinRequests])

  const login = useCallback(async (email, password) => {
    const me = await api.post('/auth/login', { email, password })
    setSignedOut(false)
    setUser(me)
    setStatus('in')
    return me
  }, [])

  const register = useCallback(async (body) => {
    const me = await api.post('/auth/register', body)
    setSignedOut(false)
    setUser(me)
    setStatus('in')
    return me
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.post('/auth/logout')
    } finally {
      setSignedOut(true)
      setUser(null)
      setStatus('out')
      setUnread(0)
      setJoinRequests(0)
    }
  }, [])

  const value = useMemo(
    () => ({
      user,
      status,
      signedOut,
      unread,
      joinRequests,
      setUser,
      refresh,
      refreshCounts,
      refreshJoinRequests: () => refreshJoinRequests(user?.role),
      login,
      register,
      logout,
    }),
    [user, status, signedOut, unread, joinRequests, refresh, refreshCounts, refreshJoinRequests, login, register, logout],
  )
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth() {
  return useContext(AuthContext)
}
