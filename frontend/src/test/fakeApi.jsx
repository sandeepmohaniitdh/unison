import { render } from '@testing-library/react'
import { vi } from 'vitest'
import App from '../App'
import fixtures from './fixtures.json'

// A fake backend for page tests. fixtures.json holds real answers recorded from the seeded
// demo backend, keyed by who asked and the request: "student /teams/1", "anon /courses?...".
// Tests can add or override answers with `routes`:
//   { 'POST /teams/1/submission/finals': (body) => ({ status: 201, body: {...} }) }
export function fakeApi(who = 'anon', routes = {}) {
  const calls = []
  const fetchMock = vi.fn(async (url, init = {}) => {
    const u = new URL(url)
    const path = u.pathname.replace('/api/v1', '') + u.search
    const method = init.method ?? 'GET'
    let body = init.body
    if (typeof body === 'string') body = JSON.parse(body)
    calls.push({ method, path, body, headers: init.headers })

    const route = routes[`${method} ${path}`] ?? routes[`${method} ${u.pathname.replace('/api/v1', '')}`]
    let answer
    if (route) answer = typeof route === 'function' ? route(body) : route
    else if (method === 'GET') answer = lookup(who, path, u.pathname.replace('/api/v1', ''))
    else answer = { status: 200, body: {} }
    return respond(answer ?? { status: 404, body: { error: { code: 'NOT_FOUND', message: 'Not found' } } })
  })
  vi.stubGlobal('fetch', fetchMock)
  return { calls, fetchMock }
}

function lookup(who, path, pathname) {
  const exact = fixtures[`${who} ${path}`]
  if (exact) return exact
  // Same endpoint with other query values (a different term, page or filter).
  const prefix = `${who} ${pathname}`
  const key = Object.keys(fixtures).find((k) => k === prefix || k.startsWith(`${prefix}?`))
  return key ? fixtures[key] : null
}

function respond({ status = 200, body = {} }) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: String(status),
    headers: new Headers(),
    json: async () => body,
  }
}

// Open a page of the whole app, as a user would.
export function renderApp(path, who = 'anon', routes = {}) {
  const api = fakeApi(who, routes)
  window.history.pushState({}, '', path)
  const view = render(<App />)
  return { ...view, ...api }
}

// One recorded answer's body, e.g. fixture('student /users/me').
export function fixture(key) {
  return structuredClone(fixtures[key].body)
}

// Wait until the fake backend received a request (method and path start).
export function sentTo(calls, method, pathStart) {
  return calls.find((c) => c.method === method && c.path.startsWith(pathStart))
}
