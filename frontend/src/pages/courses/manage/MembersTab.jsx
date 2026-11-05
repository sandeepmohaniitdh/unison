import { useState } from 'react'
import { api, getAll } from '../../../api/client'
import useApi from '../../../api/useApi'
import { useAuth } from '../../../auth/AuthContext'
import { Avatar, Badge, Button, Card, Confirm, Empty, ErrorMessage, Loading, Pagination, Select, TextField, useToast } from '../../../components'
import { formatDayMonth, formatShort } from '../../../lib/datetime'
import { capitalise, plural } from '../../../lib/format'
import { InviteStudentsCard } from './SideCards'

const STATUS_TONES = { active: 'green', removed: 'red', left: 'grey', rejected: 'grey' }

// Course management, Members: members, removal and re-enrolment, join requests and
// invitations. Removing a student ends their access at once.
export default function MembersTab({ course, archived }) {
  const { user, refreshJoinRequests } = useAuth()
  const toast = useToast()
  const [status, setStatus] = useState('active')
  const members = useApi(() => getAll(`/courses/${course.id}/members`, { status }), [course.id, status])
  const requests = useApi(() => getAll(`/courses/${course.id}/join-requests`), [course.id])
  const [removing, setRemoving] = useState(null)
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const PER_PAGE = 20
  const needle = search.trim().toLowerCase()
  const filtered = (members.data ?? []).filter((m) => !needle || m.user.name.toLowerCase().includes(needle) || (m.email ?? '').toLowerCase().includes(needle))
  const shown = filtered.slice((page - 1) * PER_PAGE, page * PER_PAGE)

  async function run(key, fn, message) {
    setBusy(key)
    setError(null)
    try {
      await fn()
      toast(message)
      members.reload()
      requests.reload()
      refreshJoinRequests()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  return (
    <div className="row gap24 start stack-sm">
      <div className="col gap24 grow" style={{ minWidth: 0 }}>
        <Card as="section" className="col gap12" aria-labelledby="requests-title">
          <div className="row between">
            <h3 id="requests-title">Join requests</h3>
            <span className="small muted">{course.join_requests_open ? 'Open in the catalogue' : 'Closed: invite only'}</span>
          </div>
          {requests.loading && <Loading />}
          {requests.data?.length === 0 && <Empty>No join requests are waiting.</Empty>}
          {requests.data?.map((r) => (
            <div key={r.id} className="row gap12 wrap">
              <Avatar name={r.user.name} size="small" />
              <div className="grow">
                <b>{r.user.name}</b>
                <p className="tiny muted">
                  {r.email} · asked {r.requested_at ? formatShort(r.requested_at) : ''}
                </p>
              </div>
              <Button
                variant="secondary"
                size="small"
                disabled={Boolean(busy) || archived}
                onClick={() => run(`r${r.id}`, () => api.patch(`/courses/${course.id}/join-requests/${r.id}`, { status: 'rejected' }), 'Join request rejected')}
              >
                Reject
              </Button>
              <Button
                size="small"
                disabled={Boolean(busy) || archived}
                onClick={() => run(`a${r.id}`, () => api.patch(`/courses/${course.id}/join-requests/${r.id}`, { status: 'approved' }), `${r.user.name} is now enrolled`)}
              >
                Approve
              </Button>
            </div>
          ))}
        </Card>

        <Card as="section" className="col gap12" aria-labelledby="members-title">
          <div className="row between gap12 wrap">
            <h3 id="members-title">Members</h3>
            <TextField
              className="grow"
              icon="search"
              iconSize={15}
              boxClassName="small"
              boxStyle={{ height: 36 }}
              aria-label="Search members"
              placeholder="Search name or email"
              value={search}
              onChange={(e) => {
                setSearch(e.target.value)
                setPage(1)
              }}
            />
            <Select
              aria-label="Show members"
              prefix="Show"
              boxStyle={{ width: 200, height: 36 }}
              options={[
                { value: 'active', label: 'Active' },
                { value: 'removed', label: 'Removed' },
                { value: 'left', label: 'Left' },
              ]}
              value={status}
              onChange={(v) => {
                setStatus(v)
                setPage(1)
              }}
            />
          </div>
          <ErrorMessage error={error ?? members.error} />
          {members.loading && <Loading />}
          {members.data?.length === 0 && <Empty>No {status} members.</Empty>}
          {members.data?.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Role</th>
                    <th scope="col">Status</th>
                    <th scope="col">Since</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {shown.map((m) => (
                    <tr key={m.user.id}>
                      <td>
                        <div className="row gap8">
                          <Avatar name={m.user.name} size="small" />
                          <div style={{ minWidth: 0 }}>
                            <b>{m.user.name}</b>
                            <p className="tiny muted">{m.email}</p>
                          </div>
                        </div>
                      </td>
                      <td>{capitalise(m.role)}</td>
                      <td>
                        <Badge tone={STATUS_TONES[m.status] ?? 'grey'}>{capitalise(m.status)}</Badge>
                      </td>
                      <td className="muted">{m.joined_at ? formatDayMonth(m.joined_at) : ''}</td>
                      <td style={{ textAlign: 'right' }}>
                        {m.status === 'active' && m.user.id !== user.id && (m.role === 'student' || user.role === 'admin') && (
                          <Button variant="danger" size="small" disabled={archived} onClick={() => setRemoving(m)}>
                            Remove
                          </Button>
                        )}
                        {m.status === 'removed' && m.role === 'student' && (
                          <Button
                            variant="secondary"
                            size="small"
                            disabled={Boolean(busy) || archived}
                            onClick={() =>
                              run(`e${m.user.id}`, () => api.patch(`/courses/${course.id}/members/${m.user.id}`, { status: 'active' }), `${m.user.name} is enrolled again`)
                            }
                          >
                            Re-enrol
                          </Button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <Pagination page={page} size={PER_PAGE} total={filtered.length} onChange={setPage} />
          {status === 'active' && members.data && (
            <p className="tiny muted">
              {plural(members.data.filter((m) => m.role === 'student').length, 'student')} ·{' '}
              {plural(members.data.filter((m) => m.role === 'teacher').length, 'teacher')}
            </p>
          )}
        </Card>
      </div>
      <div className="col gap24 side-col" style={{ width: 400 }}>
        <InviteStudentsCard courseId={course.id} archived={archived} />
        <InviteStudentsCard courseId={course.id} archived={archived} role="teacher" />
        {user.role === 'admin' && <AssignTeacherCard course={course} onDone={() => members.reload()} archived={archived} />}
      </div>
      {removing && (
        <Confirm
          title={`Remove ${removing.user.name}?`}
          danger
          confirmLabel="Remove"
          busy={busy === 'remove'}
          onCancel={() => setRemoving(null)}
          onConfirm={async () => {
            await run('remove', () => api.delete(`/courses/${course.id}/members/${removing.user.id}`), `${removing.user.name} was removed`)
            setRemoving(null)
          }}
        >
          Their access ends at once and their pending invitations in this course are cancelled. Before their team's first
          final they leave the team; after it they stay on it as "Removed". You can re-enrol them until the course is archived.
        </Confirm>
      )}
    </div>
  )
}

// Admins assign a teacher to the course from the list of teacher accounts.
function AssignTeacherCard({ course, onDone, archived }) {
  const toast = useToast()
  const [q, setQ] = useState('')
  const [error, setError] = useState(null)
  const teachers = useApi(() => api.get('/admin/users', { role: 'teacher', status: 'active', q, size: 6 }), [q])

  async function assign(t) {
    setError(null)
    try {
      await api.post(`/courses/${course.id}/teachers`, { user_id: t.id })
      toast(`${t.name} now teaches ${course.code}`)
      onDone()
    } catch (err) {
      setError(err)
    }
  }

  const current = new Set(course.teachers.map((t) => t.id))
  return (
    <Card as="section" className="col gap12">
      <h3>Assign a teacher</h3>
      <TextField icon="search" aria-label="Search teachers" placeholder="Search teacher name or email" value={q} onChange={(e) => setQ(e.target.value)} />
      <ErrorMessage error={error} />
      {teachers.data?.items.map((t) => (
        <div key={t.id} className="row gap12">
          <Avatar name={t.name} size="small" />
          <div className="grow" style={{ minWidth: 0 }}>
            <b>{t.name}</b>
            <p className="tiny muted">{t.email}</p>
          </div>
          {current.has(t.id) ? (
            <Badge tone="green">Teaching</Badge>
          ) : (
            <Button size="small" variant="secondary" onClick={() => assign(t)} disabled={archived}>
              Assign
            </Button>
          )}
        </div>
      ))}
    </Card>
  )
}
