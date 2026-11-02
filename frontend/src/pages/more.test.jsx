import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fixture, renderApp, sentTo } from '../test/fakeApi'

const teamInvitation = {
  id: 41,
  kind: 'team',
  role: 'student',
  status: 'pending',
  email: 'demo.student@example.com',
  invited_by: { id: 19, name: 'Km Shristi Singh' },
  course: { id: 1, code: 'CS301', title: 'Software Engineering', term: 'Jul-Nov 2026' },
  team: {
    id: 7,
    name: 'Comet Makers',
    assignment_id: 1,
    assignment_title: 'Course project',
    due_at: '2026-11-09T23:59:59+05:30',
    members: ['Km Shristi Singh', 'Tirtho Paul'],
    max_team: 4,
  },
  expires_at: '2026-11-05T10:00:00+05:30',
  can_accept: true,
  problem: null,
}

describe('invitation page (Figma 04)', () => {
  it('accepts a team invitation and opens the team', async () => {
    const { calls } = renderApp('/invitations/abc123', 'student', {
      'GET /invitation-links/abc123': { status: 200, body: teamInvitation },
      'PATCH /invitation-links/abc123': { status: 200, body: { status: 'accepted', kind: 'team', course_id: 1, team_id: 7, role: 'student' } },
    })
    expect(await screen.findByText(/Comet Makers/)).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button').find((b) => /^(Join|Accept)/.test(b.textContent)))
    await waitFor(() => expect(window.location.pathname).toBe('/teams/7'))
    expect(sentTo(calls, 'PATCH', '/invitation-links/abc123').body).toEqual({ status: 'accepted' })
  })

  it('declines and goes back to the dashboard', async () => {
    renderApp('/invitations/abc123', 'student', {
      'GET /invitation-links/abc123': { status: 200, body: teamInvitation },
      'PATCH /invitation-links/abc123': { status: 200, body: { status: 'declined', kind: 'team', course_id: 1, team_id: 7, role: 'student' } },
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Decline' }))
    await waitFor(() => expect(window.location.pathname).toBe('/dashboard'))
  })

  it('asks a visitor to log in first', async () => {
    renderApp('/invitations/abc123', 'anon', {
      'GET /invitation-links/abc123': {
        status: 200,
        body: { ...teamInvitation, kind: 'course', team: null, can_accept: false, problem: 'log_in' },
      },
    })
    expect((await screen.findAllByRole('link', { name: /Log in/ })).length).toBeGreaterThan(0)
  })

  it('explains an expired invitation', async () => {
    renderApp('/invitations/abc123', 'student', {
      'GET /invitation-links/abc123': { status: 200, body: { ...teamInvitation, status: 'expired', can_accept: false, problem: 'expired' } },
    })
    expect(await screen.findByRole('status')).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Decline' })).toBeNull()
  })

  it('finds an invitation by id for a logged-in user', async () => {
    renderApp('/invitations?id=41', 'student', {
      'GET /users/me/invitations?page=1&size=50': { status: 200, body: { items: [teamInvitation], page: 1, size: 50, total: 1 } },
    })
    expect(await screen.findByText(/Comet Makers/)).toBeTruthy()
  })
})

describe('account pages', () => {
  it('makes the first admin choose a new password', async () => {
    const me = { ...fixture('admin /users/me'), must_change_password: true }
    const { calls } = renderApp('/admin', 'admin', {
      'GET /users/me': { status: 200, body: me },
      'PUT /users/me/password': { status: 204 },
    })
    await waitFor(() => expect(window.location.pathname).toBe('/change-password'))
    fireEvent.change(await screen.findByLabelText('Current password'), { target: { value: 'unison-admin' } })
    fireEvent.change(screen.getByLabelText('New password'), { target: { value: 'a much longer secret' } })
    fireEvent.change(screen.getByLabelText('Type it again'), { target: { value: 'a much longer secret' } })
    fireEvent.submit(screen.getByLabelText('New password').closest('form'))
    await waitFor(() =>
      expect(sentTo(calls, 'PUT', '/users/me/password').body).toEqual({
        current_password: 'unison-admin',
        new_password: 'a much longer secret',
      }),
    )
  })

  it('warns when the two new passwords differ', async () => {
    renderApp('/reset-password?token=t1', 'anon')
    fireEvent.change(await screen.findByLabelText('New password'), { target: { value: 'first password' } })
    fireEvent.change(screen.getByLabelText('Type it again'), { target: { value: 'second password' } })
    expect(screen.getByText('The two passwords are different.')).toBeTruthy()
  })

  it('sets a new password from a reset link', async () => {
    const { calls } = renderApp('/reset-password?token=t1', 'anon', { 'POST /auth/password-resets': { status: 204 } })
    fireEvent.change(await screen.findByLabelText('New password'), { target: { value: 'brand new secret' } })
    fireEvent.change(screen.getByLabelText('Type it again'), { target: { value: 'brand new secret' } })
    fireEvent.submit(screen.getByLabelText('New password').closest('form'))
    await waitFor(() => expect(sentTo(calls, 'POST', '/auth/password-resets').body).toEqual({ token: 't1', new_password: 'brand new secret' }))
  })

  it('confirms an email from its link', async () => {
    renderApp('/verify-email?token=v1', 'anon', {
      'POST /auth/email-verifications': { status: 200, body: { message: 'Your email is confirmed.' } },
    })
    expect(await screen.findByText('Your email is confirmed.')).toBeTruthy()
  })

  it('says when a confirm link is incomplete', async () => {
    renderApp('/verify-email', 'anon')
    expect(await screen.findByText(/This link is incomplete/)).toBeTruthy()
  })
})

describe('teacher tools', () => {
  it('creates a course from My courses', async () => {
    const { calls } = renderApp('/courses', 'teacher', {
      'GET /departments?page=1&size=50': { status: 200, body: fixture('admin /departments?page=1&size=50') },
      'POST /courses': (body) => ({ status: 201, body: { id: 30, ...body } }),
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Create course' }))
    const dialog = await screen.findByRole('dialog')
    await within(dialog).findByText('Computer Science and Engineering')
    fireEvent.change(within(dialog).getByLabelText('Department'), { target: { value: '1' } })
    fireEvent.change(within(dialog).getByLabelText('Course code'), { target: { value: 'cs399' } })
    fireEvent.change(within(dialog).getByLabelText('Term'), { target: { value: 'Jul-Nov 2026' } })
    fireEvent.change(within(dialog).getByLabelText('Title'), { target: { value: 'Compilers' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Create course' }))
    await waitFor(() => expect(window.location.pathname).toBe('/courses/30/manage'))
    expect(sentTo(calls, 'POST', '/courses').body).toMatchObject({ code: 'CS399', title: 'Compilers', term: 'Jul-Nov 2026' })
  })

  it('invites students by email from course management', async () => {
    const { calls } = renderApp('/courses/1/manage', 'teacher', {
      'POST /courses/1/invitations': {
        status: 201,
        body: { created: [{ id: 1 }], skipped: [{ email: 'old@iitdh.ac.in', reason: 'already_a_member' }] },
      },
    })
    fireEvent.change(await screen.findByLabelText('Emails to invite'), { target: { value: 'new@iitdh.ac.in\nold@iitdh.ac.in' } })
    fireEvent.click(screen.getByRole('button', { name: 'Send 2 invitations' }))
    expect(await screen.findByText(/Skipped: old@iitdh.ac.in \(already a member\)/)).toBeTruthy()
    expect(sentTo(calls, 'POST', '/courses/1/invitations').body).toEqual({ emails: ['new@iitdh.ac.in', 'old@iitdh.ac.in'], role: 'student' })
  })

  it('moves a student to another team', async () => {
    const { calls } = renderApp('/courses/1/manage?tab=teams', 'teacher', {
      'PATCH /teams/1/members/18': { status: 200, body: {} },
    })
    await screen.findByText('Byte Builders')
    fireEvent.click(screen.getAllByRole('button', { name: 'Move' })[0])
    const dialog = await screen.findByRole('dialog')
    const select = within(dialog).getByLabelText('New team')
    const option = [...select.options].find((o) => o.value && o.value !== select.value)
    fireEvent.change(select, { target: { value: option.value } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Move' }))
    await waitFor(() => expect(calls.some((c) => c.method === 'PATCH' && c.path.startsWith('/teams/'))).toBe(true))
  })

  it('publishes a draft resource', async () => {
    const { calls } = renderApp('/courses/1/manage?tab=resources', 'teacher', {
      'POST /courses/1/resource-publications': { status: 200, body: [] },
    })
    fireEvent.click(await screen.findByRole('checkbox', { name: 'Select Reading list' }))
    fireEvent.click(screen.getByRole('button', { name: 'Publish 1 resource' }))
    await waitFor(() => expect(sentTo(calls, 'POST', '/courses/1/resource-publications').body.resource_ids).toHaveLength(1))
  })
})

describe('header and notifications', () => {
  it('opens the user menu and filters unread notifications', async () => {
    const { calls } = renderApp('/notifications', 'student')
    fireEvent.click(await screen.findByRole('button', { name: /Sandeep/ }))
    expect(await screen.findByRole('menu')).toBeTruthy()
    fireEvent.keyDown(document, { key: 'Escape' })
    fireEvent.click(screen.getByRole('tab', { name: 'Unread' }))
    await waitFor(() => expect(sentTo(calls, 'GET', '/notifications?unread_only=true')).toBeTruthy())
  })
})
