import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import PieChart from '../components/PieChart'
import { fixture, renderApp, sentTo } from '../test/fakeApi'

describe('log out, then someone else logs in', () => {
  it('sends the next user to their own dashboard, not the last page', async () => {
    const teacher = fixture('teacher /users/me')
    let me = fixture('student /users/me')
    const { calls } = renderApp('/profile', 'student', {
      'GET /users/me': () => (me ? { status: 200, body: me } : { status: 401, body: { error: { code: 'NOT_AUTHENTICATED', message: 'Log in' } } }),
      'POST /auth/logout': () => {
        me = null
        return { status: 204 }
      },
      'POST /auth/login': () => {
        me = teacher
        return { status: 200, body: teacher }
      },
    })
    await screen.findByText('Profile and account')
    fireEvent.click(screen.getAllByRole('button', { name: /Log out/ })[0])
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toBe('')

    fireEvent.change(await screen.findByLabelText('Institute email'), { target: { value: 'demo.teacher@example.com' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'unison-demo' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
    expect(sentTo(calls, 'POST', '/auth/login')).toBeTruthy()
  })

  it('still brings a visitor back to the page they asked for', async () => {
    renderApp('/profile')
    await waitFor(() => expect(window.location.pathname).toBe('/login'))
    expect(window.location.search).toBe('?next=%2Fprofile')
  })
})

describe('menu on tablets and phones', () => {
  it('opens the sidebar as a drawer and closes it with Escape or a link', async () => {
    renderApp('/courses', 'student')
    await screen.findByText('Digital Circuits')
    const open = screen.getByRole('button', { name: 'Menu' })
    const drawer = document.getElementById('app-menu')
    expect(drawer.classList.contains('open')).toBe(false)
    fireEvent.click(open)
    expect(drawer.classList.contains('open')).toBe(true)
    expect(open.getAttribute('aria-expanded')).toBe('true')
    fireEvent.keyDown(document, { key: 'Escape' })
    expect(drawer.classList.contains('open')).toBe(false)
    fireEvent.click(open)
    fireEvent.click(within(drawer).getByRole('link', { name: /Notifications/ }))
    await waitFor(() => expect(window.location.pathname).toBe('/notifications'))
    expect(drawer.classList.contains('open')).toBe(false)
  })
})

describe('pie chart', () => {
  it('draws one slice per part with a legend of numbers and shares', () => {
    const { container } = render(
      <PieChart
        label="Users by role"
        data={[
          { label: 'Students', value: 300 },
          { label: 'Teachers', value: 15 },
          { label: 'Admins', value: 2 },
        ]}
      />,
    )
    expect(container.querySelectorAll('path')).toHaveLength(3)
    expect(screen.getByRole('img').getAttribute('aria-label')).toBe('Users by role: Students 300, Teachers 15, Admins 2')
    const rows = screen.getAllByRole('listitem').map((li) => li.textContent)
    expect(rows).toEqual(['Students30095%', 'Teachers155%', 'Admins20.6%'])
  })

  it('handles one part and no data', () => {
    const { container, unmount } = render(<PieChart label="x" data={[{ label: 'Students', value: 5 }, { label: 'Admins', value: 0 }]} />)
    expect(container.querySelectorAll('path')).toHaveLength(1)
    unmount()
    const empty = render(<PieChart label="x" data={[{ label: 'Students', value: 0 }]} />)
    expect(empty.container.querySelectorAll('path')).toHaveLength(0)
    expect(empty.container.querySelector('circle')).toBeTruthy()
  })
})

describe('admin dashboard', () => {
  it('points to courses that have no teacher', async () => {
    const stats = { ...fixture('admin /admin/stats'), courses_without_teacher: 2 }
    renderApp('/admin', 'admin', { 'GET /admin/stats': { status: 200, body: stats } })
    expect(await screen.findByText(/2 courses have no teacher/)).toBeTruthy()
    expect(screen.getByRole('link', { name: 'Assign a teacher' }).getAttribute('href')).toBe('/admin/courses?without_teacher=1')
  })
})

describe('backend not running', () => {
  it('shows the message the dev server sends', async () => {
    const down = { status: 502, body: { error: { code: 'BACKEND_DOWN', message: 'The backend is not answering on http://127.0.0.1:8000.' } } }
    renderApp('/login', 'anon', { 'POST /auth/login': down })
    fireEvent.change(await screen.findByLabelText('Institute email'), { target: { value: 'a@iitdh.ac.in' } })
    fireEvent.change(screen.getByLabelText('Password'), { target: { value: 'x' } })
    fireEvent.click(screen.getByRole('button', { name: 'Log in' }))
    expect(await screen.findByText(/The backend is not answering/)).toBeTruthy()
  })
})
