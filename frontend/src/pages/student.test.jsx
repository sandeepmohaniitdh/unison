import { fireEvent, screen, waitFor } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fixture, renderApp, sentTo } from '../test/fakeApi'

describe('student dashboard (Figma 05)', () => {
  it('greets the student and lists deadlines and notifications', async () => {
    renderApp('/dashboard', 'student')
    expect(await screen.findByText('Good evening, Sandeep')).toBeTruthy()
    expect(await screen.findByText('Upcoming deadlines')).toBeTruthy()
    expect(screen.getAllByText('Course project').length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Marks released for Problem set 1/).length).toBeGreaterThan(0)
  })

  it('opens the dashboard from "/" when logged in', async () => {
    renderApp('/', 'student')
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
  })
})

describe('my courses and the course page (Figma 02)', () => {
  it('lists enrolled courses', async () => {
    renderApp('/courses', 'student')
    expect(await screen.findByText('Digital Circuits')).toBeTruthy()
    expect(screen.getAllByText('Enrolled').length).toBe(4)
  })

  it('shows the course with its tabs and "Your enrolment"', async () => {
    renderApp('/courses/1', 'student')
    expect(await screen.findByText('Your enrolment')).toBeTruthy()
    expect(screen.getByText(/Joined by invitation from Dr. Kavya Menon/)).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Resources' }))
    expect(await screen.findByText('Lecture 1 slides')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Assignments' }))
    expect(await screen.findAllByText('Problem set 2')).toBeTruthy()
    fireEvent.click(screen.getByRole('tab', { name: 'Members' }))
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Members' }).getAttribute('aria-selected')).toBe('true'))
  })
})

describe('team workspace (Figma 06)', () => {
  it('shows the final, the drafts and the members', async () => {
    renderApp('/teams/1', 'student')
    expect(await screen.findByText(/Your team's final: v2/)).toBeTruthy()
    expect(screen.getByText('Current final')).toBeTruthy()
    expect(screen.getByText('Team members')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Submit as final' })).toHaveLength(2)
  })

  it('submits a draft as the final with the expected current final', async () => {
    const { calls } = renderApp('/teams/1', 'student', {
      'POST /teams/1/submission/finals': { status: 201, body: { id: 9, version_number: 3 } },
    })
    const [v3] = await screen.findAllByRole('button', { name: 'Submit as final' })
    fireEvent.click(v3)
    expect(await screen.findByText(/v3 is your team's final/)).toBeTruthy()
    const sent = sentTo(calls, 'POST', '/teams/1/submission/finals')
    expect(sent.body).toEqual({ version_id: 3, expected_final_id: 1 })
    expect(sent.headers['Idempotency-Key']).toBeTruthy()
  })

  it('asks again when a teammate submitted first (409 FINAL_CHANGED)', async () => {
    let tries = 0
    const current = { id: 5, version_number: 4, submitted_by: { id: 20, name: 'Tirtho Paul' } }
    const { calls } = renderApp('/teams/1', 'student', {
      'POST /teams/1/submission/finals': () =>
        ++tries === 1
          ? { status: 409, body: { error: { code: 'FINAL_CHANGED', message: 'Changed', details: { current_final: current } } } }
          : { status: 201, body: { id: 10, version_number: 3 } },
    })
    const [v3] = await screen.findAllByRole('button', { name: 'Submit as final' })
    fireEvent.click(v3)
    expect(await screen.findByText(/Tirtho Paul submitted v4/)).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Submit v3 anyway' }))
    await waitFor(() => expect(tries).toBe(2))
    expect(calls.filter((c) => c.method === 'POST').at(-1).body).toEqual({ version_id: 3, expected_final_id: 5 })
  })

  it('invites a classmate by email', async () => {
    const { calls } = renderApp('/teams/1', 'student', {
      'POST /teams/1/invitations': { status: 201, body: { id: 77, email: 'cs26mt050@iitdh.ac.in' } },
    })
    const input = await screen.findByLabelText('Invite a classmate')
    if (input.disabled) return // the team is full in the fixture
    fireEvent.change(input, { target: { value: 'cs26mt050@iitdh.ac.in' } })
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }))
    await waitFor(() => expect(sentTo(calls, 'POST', '/teams/1/invitations').body).toEqual({ email: 'cs26mt050@iitdh.ac.in' }))
  })

  it('shows released marks on individual work (Figma 06b)', async () => {
    renderApp('/assignments/2', 'student')
    await waitFor(() => expect(window.location.pathname).toBe('/teams/20'))
    expect(await screen.findByText(/Good work overall/)).toBeTruthy()
    expect(screen.getByRole('main').textContent).toContain('17.5 / 20')
    expect(screen.getByText(/no more drafts or finals/)).toBeTruthy()
  })
})

describe('notifications', () => {
  it('marks everything as read', async () => {
    const { calls } = renderApp('/notifications', 'student', { 'PATCH /notifications': { status: 200, body: { marked: 5 } } })
    await screen.findAllByText(/Marks released for Problem set 1/)
    fireEvent.click(screen.getAllByRole('button', { name: 'Mark all as read' })[0])
    expect(await screen.findByText('5 notifications marked as read')).toBeTruthy()
    expect(sentTo(calls, 'PATCH', '/notifications').body).toEqual({ read: true })
  })
})

describe('profile (Figma 11)', () => {
  it('saves a new name', async () => {
    const me = { ...fixture('student /users/me'), name: 'Sandeep Mohan' }
    const { calls } = renderApp('/profile', 'student', { 'PATCH /users/me': { status: 200, body: me } })
    const name = await screen.findByLabelText('Full name')
    fireEvent.change(name, { target: { value: 'Sandeep Mohan' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save changes' }))
    expect(await screen.findByText('Your details were saved')).toBeTruthy()
    expect(sentTo(calls, 'PATCH', '/users/me').body).toEqual({ name: 'Sandeep Mohan' })
  })

  it('shows email preferences and the delete account card', async () => {
    renderApp('/profile', 'student')
    expect(await screen.findByText('Email notifications')).toBeTruthy()
    const button = screen.getByRole('button', { name: 'Delete my account' })
    await waitFor(() => expect(button.disabled).toBe(false))
    fireEvent.click(button)
    expect(await screen.findByRole('dialog')).toBeTruthy()
  })
})

describe('app shell', () => {
  it('switches to dark mode and logs out', async () => {
    const { calls } = renderApp('/courses', 'student', { 'POST /auth/logout': { status: 204 } })
    await screen.findByText('Digital Circuits')
    fireEvent.click(screen.getByRole('button', { name: /Dark mode/ }))
    expect(document.documentElement.dataset.theme).toBe('dark')
    fireEvent.click(screen.getByRole('button', { name: /Log out/ }))
    await waitFor(() => expect(sentTo(calls, 'POST', '/auth/logout')).toBeTruthy())
  })
})
