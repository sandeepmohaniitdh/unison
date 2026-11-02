import { useState } from 'react'
import { api } from '../../../api/client'
import useApi from '../../../api/useApi'
import { Badge, Button, Card, Confirm, ErrorMessage, Loading, Toggle, useToast } from '../../../components'
import { formatDate } from '../../../lib/datetime'
import { formatTerm, plural } from '../../../lib/format'
import CourseForm from '../CourseForm'

// Course management, Details: the course's details, join requests on or off, archiving.
export function DetailsTab({ course, onChanged }) {
  const toast = useToast()
  const [editing, setEditing] = useState(false)
  const [archiving, setArchiving] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const archived = course.archived

  async function patch(body, message) {
    setBusy(true)
    setError(null)
    try {
      const saved = await api.patch(`/courses/${course.id}`, body)
      toast(message)
      onChanged(saved)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
      setArchiving(false)
    }
  }

  const rows = [
    ['Code', course.code],
    ['Title', course.title],
    ['Department', course.department.name],
    ['Term', formatTerm(course.term)],
    ['Teachers', course.teachers.map((t) => t.name).join(', ') || 'None'],
    ['Students', plural(course.student_count, 'student')],
    ['Created', formatDate(course.created_at)],
  ]
  return (
    <div className="row gap24 start stack-sm">
      <Card as="section" className="col gap16 grow" style={{ minWidth: 0 }}>
        <div className="row between">
          <h3>Course details</h3>
          <Button variant="secondary" size="small" onClick={() => setEditing(true)} disabled={archived}>
            Edit details
          </Button>
        </div>
        <table>
          <tbody>
            {rows.map(([label, value]) => (
              <tr key={label}>
                <th scope="row" style={{ width: 180 }}>
                  {label}
                </th>
                <td>{value}</td>
              </tr>
            ))}
            <tr>
              <th scope="row">Description</th>
              <td className="muted">{course.description || 'No description yet.'}</td>
            </tr>
          </tbody>
        </table>
        <ErrorMessage error={error} />
      </Card>
      <div className="col gap24 side-col" style={{ width: 400 }}>
        <Card as="section" className="col gap12">
          <h3>Joining</h3>
          <div className="row between small gap12">
            <span>Students can ask to join from the catalogue</span>
            <Toggle
              checked={course.join_requests_open}
              onChange={(v) => patch({ join_requests_open: v }, v ? 'Join requests are open' : 'Join requests are closed')}
              label="Students can ask to join"
              disabled={busy || archived}
            />
          </div>
          <p className="tiny muted">At most 10 join requests per student per day. Invitations always work.</p>
        </Card>
        <Card as="section" className="col gap12" style={{ borderColor: 'var(--color-danger-border)' }}>
          <h3 className="red">Archive course</h3>
          {archived ? (
            <>
              <Badge tone="grey" style={{ alignSelf: 'flex-start' }}>
                Archived
              </Badge>
              <p className="small muted">This course is read-only. Archiving cannot be undone.</p>
            </>
          ) : (
            <>
              <p className="small muted">At the end of term, archive the course: it becomes read-only for everyone. This cannot be undone.</p>
              <Button variant="danger" onClick={() => setArchiving(true)} style={{ alignSelf: 'flex-start' }}>
                Archive {course.code}
              </Button>
            </>
          )}
        </Card>
      </div>
      {editing && (
        <CourseForm
          course={course}
          onClose={() => setEditing(false)}
          onSaved={(saved) => {
            setEditing(false)
            toast('Course details saved')
            onChanged(saved)
          }}
        />
      )}
      {archiving && (
        <Confirm
          title={`Archive ${course.code}?`}
          danger
          confirmLabel="Archive course"
          busy={busy}
          onCancel={() => setArchiving(false)}
          onConfirm={() => patch({ archived: true }, 'Course archived')}
        >
          Nobody can upload, submit, review or change anything in this course afterwards. This cannot be undone.
        </Confirm>
      )}
    </div>
  )
}

// Course management, Notifications: which events email members and teachers.
export function NotificationsTab({ courseId, archived }) {
  const toast = useToast()
  const rules = useApi(() => api.get(`/courses/${courseId}/notification-rules`, { size: 50 }), [courseId])
  const [error, setError] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [busy, setBusy] = useState(false)

  function flip(eventType, field, value) {
    rules.setData((d) => ({ ...d, items: d.items.map((r) => (r.event_type === eventType ? { ...r, [field]: value } : r)) }))
    setDirty(true)
  }

  async function save() {
    setBusy(true)
    setError(null)
    try {
      await api.put(`/courses/${courseId}/notification-rules`, {
        items: rules.data.items.map(({ event_type, email_members, email_teachers }) => ({ event_type, email_members, email_teachers })),
      })
      toast('Email rules saved')
      setDirty(false)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card as="section" className="col gap12">
      <div className="row between">
        <h3>Email notifications</h3>
        <span className="small muted">In-app notifications are always on</span>
      </div>
      {rules.loading && <Loading />}
      <ErrorMessage error={error ?? rules.error} />
      {rules.data && (
        <table>
          <thead>
            <tr>
              <th scope="col">Event</th>
              <th scope="col" style={{ width: 160 }}>
                Email members
              </th>
              <th scope="col" style={{ width: 160 }}>
                Email teachers
              </th>
            </tr>
          </thead>
          <tbody>
            {rules.data.items.map((r) => (
              <tr key={r.event_type}>
                <td>{r.label}</td>
                <td>
                  <Toggle checked={r.email_members} onChange={(v) => flip(r.event_type, 'email_members', v)} label={`${r.label}: email members`} disabled={archived} />
                </td>
                <td>
                  <Toggle checked={r.email_teachers} onChange={(v) => flip(r.event_type, 'email_teachers', v)} label={`${r.label}: email teachers`} disabled={archived} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <p className="tiny muted">Students and teachers can also turn emails off for themselves on their profile.</p>
      <div className="row" style={{ justifyContent: 'flex-end' }}>
        <Button onClick={save} disabled={!dirty || busy || archived}>
          {busy ? 'Saving…' : 'Save email rules'}
        </Button>
      </div>
    </Card>
  )
}
