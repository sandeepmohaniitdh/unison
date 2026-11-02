import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fixture, renderApp, sentTo } from '../../test/fakeApi'

describe('catalogue (Figma 01)', () => {
  it('lists this term\'s courses with counts and searches as you type', async () => {
    const { calls } = renderApp('/catalogue')
    expect(await screen.findByText('Software Engineering')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Course catalogue' })).toBeTruthy()
    expect(screen.getAllByText('3 assignments · 4 resources').length).toBeGreaterThan(0)
    expect(screen.getByRole('navigation', { name: 'Pages' })).toBeTruthy()

    fireEvent.change(screen.getByLabelText(/Search courses/), { target: { value: 'CS30' } })
    await waitFor(() => expect(sentTo(calls, 'GET', '/courses?q=CS30')).toBeTruthy(), { timeout: 2000 })
  })

  it('goes to the next page', async () => {
    const { calls } = renderApp('/catalogue')
    await screen.findByText('Software Engineering')
    fireEvent.click(screen.getByRole('button', { name: '2' }))
    await waitFor(() => expect(calls.some((c) => c.path.includes('page=2'))).toBe(true))
  })

  it('opens "/" as the catalogue for visitors', async () => {
    renderApp('/')
    expect(await screen.findByRole('heading', { name: 'Course catalogue' })).toBeTruthy()
  })
})

describe('course preview for visitors', () => {
  it('shows the course and asks to log in to join', async () => {
    renderApp('/courses/1')
    expect(await screen.findByText('About this course')).toBeTruthy()
    expect(screen.getByText('60 students enrolled')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Log in to join' }).getAttribute('href')).toContain('/login')
  })
})

describe('login (Figma 03)', () => {
  it('asks for both fields before sending anything', async () => {
    const { calls } = renderApp('/login')
    fireEvent.click(await screen.findByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Type your institute email and your password.')).toBeTruthy()
    expect(sentTo(calls, 'POST', '/auth/login')).toBeUndefined()
  })

  it('logs in and opens the dashboard', async () => {
    const me = fixture('student /users/me')
    const { calls } = renderApp('/login', 'anon', { 'POST /auth/login': { status: 200, body: me } })
    fireEvent.change(await screen.findByLabelText('Institute email'), { target: { value: 'demo.student@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'unison-demo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    expect(sentTo(calls, 'POST', '/auth/login').body).toEqual({ email: 'demo.student@example.com', password: 'unison-demo' })
    expect(sentTo(calls, 'POST', '/auth/login').headers['X-Unison-Client']).toBe('web')
  })

  it('shows the backend\'s message for a wrong password', async () => {
    renderApp('/login', 'anon', {
      'POST /auth/login': { status: 401, body: { error: { code: 'BAD_CREDENTIALS', message: 'Wrong email or password.' } } },
    })
    fireEvent.change(await screen.findByLabelText('Institute email'), { target: { value: 'a@iitdh.ac.in' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'nope' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText('Wrong email or password.')).toBeTruthy()
    expect(window.location.pathname).toBe('/login')
  })

  it('shows the notices from links', async () => {
    renderApp('/login?reset=done')
    expect(await screen.findByText(/Your password was changed/)).toBeTruthy()
  })
})

describe('sign up', () => {
  it('needs the consent box and a long enough password', async () => {
    const { calls } = renderApp('/signup')
    fireEvent.change(await screen.findByLabelText('Full name'), { target: { value: 'New Student' } })
    fireEvent.change(screen.getByLabelText('Institute email'), { target: { value: 'cs26mt099@iitdh.ac.in' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'short' } })
    fireEvent.click(screen.getByRole('button', { name: 'Sign up' }))
    await waitFor(() => expect(document.querySelector('.field-error, .alert')).toBeTruthy())
    expect(sentTo(calls, 'POST', '/auth/register')).toBeUndefined()
  })
})

describe('other public pages', () => {
  it('shows About and the privacy notice', async () => {
    renderApp('/about')
    expect(await screen.findByText('Group work, handed in together')).toBeTruthy()
    expect(screen.getByRole('heading', { name: 'Privacy' })).toBeTruthy()
  })

  it('shows the forgot and reset password pages', async () => {
    const { calls } = renderApp('/forgot-password')
    const email = await screen.findByLabelText(/email/i)
    fireEvent.change(email, { target: { value: 'cs26mt001@iitdh.ac.in' } })
    fireEvent.submit(email.closest('form'))
    await waitFor(() => expect(sentTo(calls, 'POST', '/auth/password-reset-requests')).toBeTruthy())
  })

  it('shows "not found" for an unknown address', async () => {
    renderApp('/no/such/page')
    expect(await screen.findByText(/not found|does not exist/i)).toBeTruthy()
  })

  it('sends visitors from a private page to the login page', async () => {
    renderApp('/dashboard')
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toContain('next=')
  })
})
