import { describe, expect, it, vi } from 'vitest'
import { api, ApiError, apiUrl, download, getAll, newIdempotencyKey, request, setUnauthorizedHandler } from './client'

function reply(status, body) {
  return { ok: status < 300, status, statusText: 'x', headers: new Headers({ 'X-Request-ID': 'req-1' }), json: async () => body }
}

describe('apiUrl', () => {
  it('adds the /api/v1 prefix and skips empty query values', () => {
    const url = apiUrl('/courses', { q: 'CS301', department_id: '', term: null, page: 2 })
    expect(url.pathname).toBe('/api/v1/courses')
    expect(url.search).toBe('?q=CS301&page=2')
  })
})

describe('request', () => {
  it('sends JSON and the CSRF header on changes, not on reads', async () => {
    const fetch = vi.fn(async () => reply(200, { ok: true }))
    vi.stubGlobal('fetch', fetch)
    await api.get('/users/me')
    await api.post('/auth/login', { email: 'a@iitdh.ac.in' })
    const [, getInit] = fetch.mock.calls[0]
    const [, postInit] = fetch.mock.calls[1]
    expect(getInit.headers['X-Unison-Client']).toBeUndefined()
    expect(postInit.headers['X-Unison-Client']).toBe('web')
    expect(postInit.headers['Content-Type']).toBe('application/json')
    expect(JSON.parse(postInit.body)).toEqual({ email: 'a@iitdh.ac.in' })
    expect(postInit.credentials).toBe('same-origin')
  })

  it('leaves FormData for the browser to encode', async () => {
    const fetch = vi.fn(async () => reply(201, {}))
    vi.stubGlobal('fetch', fetch)
    const form = new FormData()
    form.append('title', 'Slides')
    await api.post('/courses/1/resources/files', form)
    const [, init] = fetch.mock.calls[0]
    expect(init.body).toBe(form)
    expect(init.headers['Content-Type']).toBeUndefined()
  })

  it('returns null for 204 and uses every method', async () => {
    const fetch = vi.fn(async () => reply(204))
    vi.stubGlobal('fetch', fetch)
    expect(await api.delete('/invitations/3')).toBeNull()
    await api.put('/x', {})
    await api.patch('/x', {})
    expect(fetch.mock.calls.map(([, i]) => i.method)).toEqual(['DELETE', 'PUT', 'PATCH'])
  })

  it('turns the backend error body into an ApiError', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => reply(409, { error: { code: 'FINAL_CHANGED', message: 'Someone else submitted', details: { id: 4 } } })),
    )
    const error = await api.post('/teams/1/submission/finals', {}).catch((e) => e)
    expect(error).toBeInstanceOf(ApiError)
    expect(error).toMatchObject({ status: 409, code: 'FINAL_CHANGED', details: { id: 4 }, requestId: 'req-1' })
  })

  it('uses HTTP_<status> when the body has no error code', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => reply(502, null)))
    const error = await request('/health').catch((e) => e)
    expect(error.code).toBe('HTTP_502')
  })

  it('tells the app about a 401', async () => {
    const handler = vi.fn()
    setUnauthorizedHandler(handler)
    vi.stubGlobal('fetch', vi.fn(async () => reply(401, { error: { code: 'NOT_AUTHENTICATED', message: 'Log in' } })))
    await api.get('/users/me').catch(() => null)
    expect(handler).toHaveBeenCalledOnce()
    setUnauthorizedHandler(null)
  })

  it('reports a network failure in plain words', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(new TypeError('Failed to fetch'))))
    const error = await api.get('/courses').catch((e) => e)
    expect(error.code).toBe('NETWORK_ERROR')
    expect(error.message).toMatch(/could not be reached/)
  })

  it('passes an abort through unchanged', async () => {
    const abort = Object.assign(new Error('aborted'), { name: 'AbortError' })
    vi.stubGlobal('fetch', vi.fn(async () => Promise.reject(abort)))
    await expect(api.get('/courses')).rejects.toBe(abort)
  })
})

describe('getAll', () => {
  it('reads every page of a list', async () => {
    const pages = { 1: [1, 2], 2: [3] }
    vi.stubGlobal(
      'fetch',
      vi.fn(async (url) => {
        const page = Number(new URL(url).searchParams.get('page'))
        return reply(200, { items: pages[page] ?? [], page, size: 50, total: 3 })
      }),
    )
    expect(await getAll('/courses/1/members', { status: 'active' })).toEqual([1, 2, 3])
  })
})

describe('helpers', () => {
  it('makes a different idempotency key each time', () => {
    expect(newIdempotencyKey()).not.toBe(newIdempotencyKey())
  })

  it('downloads through a temporary link', () => {
    const click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
    download('/resources/4/content')
    expect(click).toHaveBeenCalledOnce()
    expect(document.querySelector('a[href*="/resources/4/content"]')).toBeNull()
    click.mockRestore()
  })
})
