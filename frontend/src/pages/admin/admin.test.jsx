import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { renderApp, sentTo } from '../../test/fakeApi'
import { settingLabel } from './AdminPages'
import { describeAudit } from './adminBits'

describe('admin overview (Figma 10)', () => {
  it('shows the platform numbers, users and the audit log', async () => {
    renderApp('/admin', 'admin')
    expect(await screen.findByText('Finals this week')).toBeTruthy()
    expect(screen.getByText('+29% on last week')).toBeTruthy()
    const pie = screen.getByRole('img', { name: 'Users by role: Students 300, Teachers 15, Admins 2' })
    expect(pie.textContent).toContain('317')
    const legend = pie.parentElement.querySelector('.pie-legend')
    expect(legend.textContent).toContain('Admins20.6%')
    expect(await screen.findByText('Aachal Brar')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'All 317 users' })).toBeTruthy()
  })

  it('changes a role from the users table', async () => {
    const { calls } = renderApp('/admin', 'admin', {
      'PATCH /admin/users/': { status: 200, body: {} },
    })
    const picker = await screen.findByLabelText('Role of Aachal Brar')
    fireEvent.change(picker, { target: { value: 'teacher' } })
    expect(await screen.findByText('Aachal Brar is now a teacher')).toBeTruthy()
    expect(calls.find((c) => c.method === 'PATCH').body).toEqual({ role: 'teacher' })
  })

  it('sends a staff invitation', async () => {
    const { calls } = renderApp('/admin', 'admin', { 'POST /admin/staff-invitations': { status: 201, body: { id: 1 } } })
    fireEvent.click(await screen.findByRole('button', { name: 'Invite teacher or admin' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Email'), { target: { value: 'new.teacher@iitdh.ac.in' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Send invitation' }))
    await waitFor(() =>
      expect(sentTo(calls, 'POST', '/admin/staff-invitations').body).toEqual({ email: 'new.teacher@iitdh.ac.in', role: 'teacher' }),
    )
  })
})

describe('admin pages', () => {
  it('lists users with filters', async () => {
    renderApp('/admin/users', 'admin')
    expect(await screen.findByText('Abdul Chander')).toBeTruthy()
    expect(screen.getByRole('tab', { name: 'Staff invitations' })).toBeTruthy()
  })

  it('shows one user and asks before suspending', async () => {
    renderApp('/admin/users/4', 'admin')
    expect(await screen.findByText('CS302 Database Systems')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Suspend account' }))
    expect(await screen.findByRole('dialog')).toBeTruthy()
  })

  it('lists courses', async () => {
    renderApp('/admin/courses', 'admin')
    expect(await screen.findByText('CS305 Computer Networks')).toBeTruthy()
  })

  it('adds a department', async () => {
    const { calls } = renderApp('/admin/departments', 'admin', {
      'POST /departments': { status: 201, body: { id: 9, code: 'CH', name: 'Chemistry' } },
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Add department' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Code'), { target: { value: 'ch' } })
    fireEvent.change(within(dialog).getByLabelText('Name'), { target: { value: 'Chemistry' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(sentTo(calls, 'POST', '/departments').body).toEqual({ code: 'CH', name: 'Chemistry' }))
  })

  it('shows the audit log', async () => {
    renderApp('/admin/audit-log', 'admin')
    expect(await screen.findByText(/first admin created/)).toBeTruthy()
  })

  it('saves a setting', async () => {
    const { calls } = renderApp('/admin/settings', 'admin')
    const input = await screen.findByLabelText('Join requests per day')
    fireEvent.change(input, { target: { value: '12' } })
    const row = input.closest('.list-row')
    fireEvent.click(within(row).getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Setting saved')).toBeTruthy()
    expect(sentTo(calls, 'PUT', '/admin/settings/join_requests_per_day').body).toEqual({ value: 12 })
  })
})

describe('admin helpers', () => {
  it('names settings in plain words', () => {
    expect(settingLabel('ai_requests_per_submission')).toBe('AI requests per submission')
    expect(settingLabel('signups_per_ip_per_hour')).toBe('Signups per IP per hour')
  })

  it('describes audit entries', () => {
    const e = {
      action: 'role_changed',
      target_type: 'users',
      target_id: 4,
      before: { name: 'Dr. Rohan Kulkarni', role: 'student' },
      after: { name: 'Dr. Rohan Kulkarni', role: 'teacher' },
    }
    expect(describeAudit(e)).toEqual({ action: 'role changed', target: 'Dr. Rohan Kulkarni', change: 'role: Student → Teacher' })
    expect(describeAudit({ action: 'setting_changed', target_type: 'platform_settings', target_id: 2, before: null, after: null }).target).toBe(
      'platform_setting #2',
    )
  })
})
