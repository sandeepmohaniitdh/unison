import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { fixture, renderApp, sentTo } from '../test/fakeApi'

describe('teacher dashboard (Figma 07)', () => {
  it('shows courses, join requests and submission status', async () => {
    renderApp('/dashboard', 'teacher')
    expect(await screen.findByText('Good evening, Dr. Menon')).toBeTruthy()
    expect(await screen.findByText('Submission status')).toBeTruthy()
    expect(screen.getByText('10 of 19 teams submitted')).toBeTruthy()
    expect(screen.getAllByText(/join requests?/i).length).toBeGreaterThan(0)
  })
})

describe('course page for the teacher', () => {
  it('links to "Manage course" and shows review buttons', async () => {
    renderApp('/courses/1', 'teacher')
    expect(await screen.findByText(/Teaching since/)).toBeTruthy()
    expect(screen.getByRole('link', { name: /Manage course/ }).getAttribute('href')).toBe('/courses/1/manage')
    expect((await screen.findAllByRole('link', { name: 'Review' })).length).toBe(3)
  })
})

describe('course management (Figma 08)', () => {
  it('creates a draft assignment with a rubric', async () => {
    const { calls } = renderApp('/courses/1/manage', 'teacher', {
      'POST /courses/1/assignments': (body) => ({ status: 201, body: { id: 99, status: 'draft', ...body } }),
    })
    const title = await screen.findByLabelText('Title')
    fireEvent.change(title, { target: { value: 'Lab 4: Unit tests' } })
    fireEvent.change(screen.getByLabelText('Description'), { target: { value: 'Write tests for the parser.' } })
    fireEvent.change(document.getElementById('deadline'), { target: { value: '2026-11-20T23:59' } })
    fireEvent.change(screen.getByLabelText('Criterion 1'), { target: { value: 'Coverage' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save draft' }))
    expect(await screen.findByText('Draft saved')).toBeTruthy()
    const sent = sentTo(calls, 'POST', '/courses/1/assignments').body
    expect(sent).toMatchObject({ title: 'Lab 4: Unit tests', due_at: '2026-11-20T23:59:59+05:30' })
    expect(sent.rubric[0].title).toBe('Coverage')
  })

  it('opens an assignment to edit it', async () => {
    renderApp('/courses/1/manage', 'teacher')
    const table = (await screen.findByText('All assignments')).closest('section')
    fireEvent.click(within(table).getAllByRole('button', { name: 'Edit' })[0])
    expect(await screen.findByText('Edit: Problem set 1')).toBeTruthy()
  })

  it('shows the course details and the archive card', async () => {
    renderApp('/courses/1/manage?tab=details', 'teacher')
    expect(await screen.findByText('Course details')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: 'Archive CS301' }))
    expect(await screen.findByRole('dialog')).toBeTruthy()
  })

  it('adds a link resource as a draft', async () => {
    const { calls } = renderApp('/courses/1/manage?tab=resources', 'teacher', {
      'POST /courses/1/resources/links': { status: 201, body: { id: 500, kind: 'link', status: 'draft' } },
    })
    fireEvent.click(await screen.findByRole('button', { name: 'Add a link' }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText('Link'), { target: { value: 'https://example.com/notes' } })
    fireEvent.change(within(dialog).getByLabelText('Title'), { target: { value: 'Extra notes' } })
    fireEvent.click(within(dialog).getByRole('button', { name: 'Add as draft' }))
    await waitFor(() =>
      expect(sentTo(calls, 'POST', '/courses/1/resources/links').body).toEqual({
        title: 'Extra notes',
        description: null,
        url: 'https://example.com/notes',
      }),
    )
  })

  it('approves a join request from the members tab', async () => {
    const { calls } = renderApp('/courses/1/manage?tab=members', 'teacher')
    expect(await screen.findByText('Girish Dugal')).toBeTruthy()
    fireEvent.click(screen.getAllByRole('button', { name: 'Approve' })[0])
    await waitFor(() => expect(sentTo(calls, 'PATCH', '/courses/1/join-requests/').body).toEqual({ status: 'approved' }))
  })

  it('lists teams for an assignment', async () => {
    renderApp('/courses/1/manage?tab=teams', 'teacher')
    expect(await screen.findByText('Byte Builders')).toBeTruthy()
    expect(screen.getAllByRole('button', { name: 'Move' }).length).toBeGreaterThan(0)
  })

  it('saves the email rules after a change', async () => {
    const { calls } = renderApp('/courses/1/manage?tab=notifications', 'teacher')
    await screen.findByText('Join request received')
    const save = screen.getByRole('button', { name: 'Save email rules' })
    expect(save.disabled).toBe(true)
    fireEvent.click(screen.getByRole('switch', { name: 'Join request received: email members' }))
    fireEvent.click(save)
    expect(await screen.findByText('Email rules saved')).toBeTruthy()
    expect(sentTo(calls, 'PUT', '/courses/1/notification-rules').body.items.length).toBeGreaterThan(3)
  })
})

describe('join requests', () => {
  it('approves and removes the row', async () => {
    const { calls } = renderApp('/join-requests', 'teacher')
    expect(await screen.findByText('Unnati Garde')).toBeTruthy()
    const row = screen.getByText('Girish Dugal').closest('tr')
    fireEvent.click(within(row).getByRole('button', { name: 'Approve' }))
    await waitFor(() => expect(screen.queryByText('Girish Dugal')).toBeNull())
    expect(sentTo(calls, 'PATCH', '/courses/1/join-requests/').body).toEqual({ status: 'approved' })
  })
})

describe('review (Figma 09)', () => {
  it('shows a released review as read-only', async () => {
    renderApp('/assignments/2/review', 'teacher')
    expect(await screen.findByText(/Marks can no longer change/)).toBeTruthy()
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull()
  })

  it('saves scores of a review that is not released yet', async () => {
    const sheet = { ...fixture('teacher /teams/36/review'), status: 'draft', released_at: null }
    const rows = fixture('teacher /assignments/2/reviews?page=1&size=50')
    rows.items[0] = { ...rows.items[0], review_status: 'draft', state: 'final_submitted' }
    const { calls } = renderApp('/assignments/2/review', 'teacher', {
      'GET /teams/36/review': { status: 200, body: sheet },
      'GET /assignments/2/reviews?page=1&size=50': { status: 200, body: rows },
      'PUT /teams/36/review': { status: 200, body: sheet },
    })
    const score = await screen.findByLabelText('Score for Correctness, out of 10')
    fireEvent.change(score, { target: { value: '9' } })
    fireEvent.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/Review saved/)).toBeTruthy()
    const sent = sentTo(calls, 'PUT', '/teams/36/review').body
    expect(sent.scores.find((s) => s.criterion_id === 4).points).toBe('9')
  })
})
