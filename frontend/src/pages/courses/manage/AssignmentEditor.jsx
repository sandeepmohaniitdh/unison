import { useState } from 'react'
import { api } from '../../../api/client'
import { Badge, Button, Card, Confirm, ErrorMessage, Icon, NumberBox, TextArea, TextField, Toggle, useToast } from '../../../components'
import { formatDeadlineLong, fromIstInput, toIstInput } from '../../../lib/datetime'

const EMPTY_RUBRIC = [
  { title: 'Design and architecture', max_points: '10' },
  { title: 'Implementation', max_points: '25' },
  { title: 'Testing', max_points: '10' },
  { title: 'Report', max_points: '5' },
]

function initial(a) {
  if (!a) {
    return {
      title: '',
      description: '',
      kind: 'group',
      min_team: '2',
      max_team: '4',
      max_files: '5',
      due_at: '',
      requires_pdf: true,
      rubric: EMPTY_RUBRIC,
    }
  }
  return {
    title: a.title,
    description: a.description ?? '',
    kind: a.kind,
    min_team: String(a.min_team),
    max_team: String(a.max_team),
    max_files: String(a.max_files),
    due_at: toIstInput(a.due_at),
    requires_pdf: a.requires_pdf,
    rubric: a.rubric.map((c) => ({ title: c.title, max_points: String(Number(c.max_points)) })),
  }
}

// Figma 08, left card: create or edit an assignment with its rubric. A draft is not
// visible to students; publishing notifies them. After publishing only the title,
// description and a later deadline can change.
export default function AssignmentEditor({ courseId, assignment, onSaved, onCancel, archived }) {
  const toast = useToast()
  const [form, setForm] = useState(() => initial(assignment))
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(null)
  const [confirming, setConfirming] = useState(false)
  const isDraft = !assignment || assignment.status === 'draft'
  const set = (key) => (value) => setForm((f) => ({ ...f, [key]: value }))
  const total = form.rubric.reduce((sum, c) => sum + (Number(c.max_points) || 0), 0)

  function body() {
    const b = {
      title: form.title.trim(),
      description: form.description.trim() || null,
      due_at: fromIstInput(form.due_at),
    }
    if (isDraft) {
      Object.assign(b, {
        kind: form.kind,
        min_team: form.kind === 'group' ? Number(form.min_team) : 1,
        max_team: form.kind === 'group' ? Number(form.max_team) : 1,
        max_files: Number(form.max_files),
        requires_pdf: form.requires_pdf,
        rubric: form.rubric.filter((c) => c.title.trim()).map((c) => ({ title: c.title.trim(), max_points: c.max_points })),
      })
    }
    return b
  }

  async function save(publish) {
    setBusy(publish ? 'publish' : 'save')
    setError(null)
    try {
      let saved
      if (!assignment) {
        saved = await api.post(`/courses/${courseId}/assignments`, body())
        if (publish) saved = await api.patch(`/assignments/${saved.id}`, { status: 'published' })
      } else {
        const changes = body()
        if (!isDraft && assignment.due_at && fromIstInput(toIstInput(assignment.due_at)) === changes.due_at) delete changes.due_at
        saved = await api.patch(`/assignments/${assignment.id}`, publish ? { ...changes, status: 'published' } : changes)
      }
      toast(publish ? 'Published. Students were notified.' : isDraft ? 'Draft saved' : 'Saved')
      onSaved(saved)
      if (!assignment) setForm(initial(null))
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function remove() {
    setBusy('delete')
    try {
      await api.delete(`/assignments/${assignment.id}`)
      toast('Draft deleted')
      onSaved(null)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
      setConfirming(false)
    }
  }

  function setCriterion(index, key, value) {
    setForm((f) => ({ ...f, rubric: f.rubric.map((c, i) => (i === index ? { ...c, [key]: value } : c)) }))
  }

  const statusBadge = !assignment ? (
    <Badge tone="grey">Draft · not visible to students</Badge>
  ) : assignment.status === 'draft' ? (
    <Badge tone="grey">Draft · not visible to students</Badge>
  ) : (
    <Badge tone="green">{assignment.status === 'closed' ? 'Closed' : 'Published'}</Badge>
  )

  return (
    <Card as="section" className="col gap16 grow" style={{ minWidth: 0 }} aria-labelledby="editor-title">
      <div className="row between">
        <h3 id="editor-title">{assignment ? `Edit: ${assignment.title}` : 'New assignment'}</h3>
        {statusBadge}
      </div>
      <TextField label="Title" placeholder="Group Project: Library Booking App" value={form.title} onChange={(e) => set('title')(e.target.value)} />
      <TextArea label="Description" placeholder="What students must hand in" value={form.description} onChange={(e) => set('description')(e.target.value)} />
      <div className="row gap16 wrap">
        <div className="grow" role="group" aria-labelledby="type-label">
          <span className="lbl" id="type-label">
            Type
          </span>
          <div className="row gap8">
            {['individual', 'group'].map((kind) => (
              <Button
                key={kind}
                variant={form.kind === kind ? 'primary' : 'secondary'}
                className="grow"
                aria-pressed={form.kind === kind}
                disabled={!isDraft}
                onClick={() => set('kind')(kind)}
              >
                {kind === 'group' ? 'Group' : 'Individual'}
              </Button>
            ))}
          </div>
        </div>
        {form.kind === 'group' && (
          <div role="group" aria-labelledby="size-label">
            <span className="lbl" id="size-label">
              Team size
            </span>
            <div className="row gap8">
              <NumberBox value={form.min_team} onChange={set('min_team')} aria-label="Smallest team" disabled={!isDraft} />
              <span className="muted">to</span>
              <NumberBox value={form.max_team} onChange={set('max_team')} aria-label="Largest team" disabled={!isDraft} />
            </div>
          </div>
        )}
        <div>
          <span className="lbl" id="files-label">
            Max files
          </span>
          <NumberBox value={form.max_files} onChange={set('max_files')} aria-labelledby="files-label" disabled={!isDraft} />
        </div>
      </div>
      <div className="row gap16 wrap">
        <div className="grow">
          <label className="lbl" htmlFor="deadline">
            Deadline (IST)
          </label>
          <div className={`inp dt-box${form.due_at ? ' f' : ''}`}>
            <Icon name="clock" size={16} />
            <span className="dt-text" aria-hidden="true">
              {form.due_at ? formatDeadlineLong(fromIstInput(form.due_at)) : 'Choose the date and time'}
            </span>
            <input
              id="deadline"
              type="datetime-local"
              value={form.due_at}
              onChange={(e) => set('due_at')(e.target.value)}
              onClick={(e) => e.currentTarget.showPicker?.()}
              aria-describedby="deadline-hint"
            />
          </div>
          {!isDraft && (
            <p id="deadline-hint" className="tiny muted" style={{ marginTop: 4 }}>
              A later deadline is an extension; the class is notified.
            </p>
          )}
        </div>
        <div className="grow">
          <span className="lbl">Requires a PDF report</span>
          <div className="row gap8" style={{ height: 42 }}>
            <Toggle checked={form.requires_pdf} onChange={set('requires_pdf')} label="Requires a PDF report" disabled={!isDraft} />
            <span className="small muted">Needed for the AI feedback draft</span>
          </div>
        </div>
      </div>
      <div>
        <span className="lbl">Rubric</span>
        <table>
          <thead>
            <tr>
              <th scope="col">Criterion</th>
              <th scope="col" style={{ width: 120 }}>
                Max points
              </th>
              {isDraft && (
                <th scope="col" style={{ width: 40 }}>
                  <span className="sr-only">Remove</span>
                </th>
              )}
            </tr>
          </thead>
          <tbody>
            {form.rubric.map((c, i) => (
              <tr key={i}>
                <td>
                  {isDraft ? (
                    <input
                      className="cell-input"
                      value={c.title}
                      onChange={(e) => setCriterion(i, 'title', e.target.value)}
                      aria-label={`Criterion ${i + 1}`}
                      placeholder="Criterion"
                    />
                  ) : (
                    c.title
                  )}
                </td>
                <td>
                  {isDraft ? (
                    <input
                      className="cell-input"
                      inputMode="decimal"
                      style={{ width: 70 }}
                      value={c.max_points}
                      onChange={(e) => setCriterion(i, 'max_points', e.target.value)}
                      aria-label={`Max points of criterion ${i + 1}`}
                    />
                  ) : (
                    c.max_points
                  )}
                </td>
                {isDraft && (
                  <td>
                    <button
                      type="button"
                      className="row-tools"
                      aria-label={`Remove criterion ${i + 1}`}
                      onClick={() => setForm((f) => ({ ...f, rubric: f.rubric.filter((_, j) => j !== i) }))}
                      disabled={form.rubric.length <= 1}
                    >
                      <Icon name="trash" size={16} color="var(--color-muted)" />
                    </button>
                  </td>
                )}
              </tr>
            ))}
          </tbody>
        </table>
        <div className="row between" style={{ marginTop: 10 }}>
          {isDraft ? (
            <button
              type="button"
              className="small link"
              onClick={() => setForm((f) => ({ ...f, rubric: [...f.rubric, { title: '', max_points: '5' }] }))}
            >
              + Add criterion
            </button>
          ) : (
            <span />
          )}
          <span className="small muted">Total {total} points</span>
        </div>
      </div>
      <ErrorMessage error={error} />
      <div className="row gap12 wrap" style={{ justifyContent: 'flex-end' }}>
        {assignment && isDraft && (
          <Button variant="danger" onClick={() => setConfirming(true)} disabled={Boolean(busy) || archived}>
            Delete draft
          </Button>
        )}
        {assignment && onCancel && (
          <Button variant="secondary" onClick={onCancel}>
            New assignment instead
          </Button>
        )}
        <Button variant="secondary" onClick={() => save(false)} disabled={Boolean(busy) || archived || !form.title || !form.due_at}>
          {busy === 'save' ? 'Saving…' : isDraft ? 'Save draft' : 'Save changes'}
        </Button>
        {isDraft && (
          <Button onClick={() => save(true)} disabled={Boolean(busy) || archived || !form.title || !form.due_at}>
            {busy === 'publish' ? 'Publishing…' : 'Publish and notify students'}
          </Button>
        )}
      </div>
      {confirming && (
        <Confirm
          title="Delete this draft?"
          danger
          confirmLabel="Delete draft"
          busy={busy === 'delete'}
          onConfirm={remove}
          onCancel={() => setConfirming(false)}
        >
          "{assignment.title}" and its rubric are deleted. Students never saw it.
        </Confirm>
      )}
    </Card>
  )
}
