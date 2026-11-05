// The one API client every page uses. It talks to the backend through nginx at
// /api/v1 (same origin, so the session cookie is sent and no CORS is needed).
//
//   import { api } from '../api/client'
//   const page = await api.get('/courses', { page: 1, size: 20 })
//   await api.post('/teams/7/submission/finals', { version_id: 3, expected_final_id: 2 }, { headers: { 'Idempotency-Key': key } })
//
// Errors arrive as ApiError with the backend's code, e.g. error.code === 'FINAL_CHANGED'.

const BASE = '/api/v1'

// Requests that change something and use the session cookie must send this header
// (the backend's CSRF check, see docs/api/README.md).
export const CSRF_HEADER = 'X-Unison-Client'

export class ApiError extends Error {
  constructor({ status, code, message, details = null, requestId = null }) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
    this.details = details
    this.requestId = requestId
  }
}

export function apiUrl(path, query) {
  const url = new URL(BASE + path, window.location.origin)
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== undefined && value !== null && value !== '') url.searchParams.set(key, value)
  }
  return url
}

// Called with every 401, so the app can send the user back to the login page.
let onUnauthorized = null
export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

export async function request(path, { method = 'GET', query, body, headers = {}, signal } = {}) {
  const init = {
    method,
    signal,
    credentials: 'same-origin',
    headers: { Accept: 'application/json', ...headers },
  }
  if (method !== 'GET' && method !== 'HEAD') init.headers[CSRF_HEADER] = 'web'
  if (body instanceof FormData) {
    init.body = body // the browser sets the multipart Content-Type itself
  } else if (body !== undefined) {
    init.headers['Content-Type'] = 'application/json'
    init.body = JSON.stringify(body)
  }

  let response
  try {
    response = await fetch(apiUrl(path, query), init)
  } catch (error) {
    if (error.name === 'AbortError') throw error
    throw new ApiError({
      status: 0,
      code: 'NETWORK_ERROR',
      message: 'Unison could not be reached. Check your connection and try again.',
    })
  }

  if (response.status === 204) return null
  const data = await response.json().catch(() => null)
  if (!response.ok) {
    const error = data?.error ?? {}
    const apiError = new ApiError({
      status: response.status,
      code: error.code ?? `HTTP_${response.status}`,
      message: error.message ?? response.statusText,
      details: error.details ?? null,
      requestId: error.request_id ?? response.headers.get('X-Request-ID'),
    })
    if (response.status === 401) onUnauthorized?.(apiError)
    throw apiError
  }
  return data
}

export const api = {
  get: (path, query, options) => request(path, { ...options, query }),
  post: (path, body, options) => request(path, { ...options, method: 'POST', body }),
  put: (path, body, options) => request(path, { ...options, method: 'PUT', body }),
  patch: (path, body, options) => request(path, { ...options, method: 'PATCH', body }),
  delete: (path, options) => request(path, { ...options, method: 'DELETE' }),
}

// Every list endpoint returns at most 50 items per page. This reads all pages of a short
// list (rubric-sized things such as a team's drafts or a course's members) in order.
export async function getAll(path, query = {}, { limit = 500 } = {}) {
  const items = []
  for (let page = 1; ; page += 1) {
    const data = await api.get(path, { ...query, page, size: 50 })
    items.push(...data.items)
    if (items.length >= data.total || data.items.length === 0 || items.length >= limit) return items
  }
}

// A new random key for each click of an upload or "Submit as final" button, so a repeated
// request (double click, retry after a timeout) does not create a second draft or final.
export function newIdempotencyKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  return `${Date.now()}-${Math.random().toString(16).slice(2)}-${Math.random().toString(16).slice(2)}`
}

// Downloads go through the browser so the session cookie is sent; the server answers
// with Content-Disposition: attachment.
export function download(path) {
  const link = document.createElement('a')
  link.href = apiUrl(path).toString()
  link.rel = 'noopener'
  document.body.appendChild(link)
  link.click()
  link.remove()
}
