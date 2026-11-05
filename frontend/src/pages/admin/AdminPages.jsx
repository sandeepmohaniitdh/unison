import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Avatar,
  Badge,
  Button,
  Card,
  Confirm,
  Empty,
  ErrorMessage,
  Icon,
  Loading,
  Modal,
  PageError,
  Pagination,
  Select,
  Tabs,
  TextField,
  Toggle,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDate, formatShort } from '../../lib/datetime'
import { capitalise, formatTerm } from '../../lib/format'
import CourseForm from '../courses/CourseForm'
import { describeAudit, RolePicker, StaffInviteDialog, userStatusBadge } from './adminBits'

// The admin pages behind the sidebar of Figma 10 (Users, Courses, Departments, Audit
// log, Settings). Not drawn in Figma; built from the same components.

function useDebounced(value, ms = 300) {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms)
    return () => clearTimeout(t)
  }, [value, ms])
  return v
}

const SIZE = 20

export function AdminUsersPage() {
  const [tab, setTab] = useState('users')
  const [query, setQuery] = useState('')
  const q = useDebounced(query.trim())
  const [role, setRole] = useState('')
  const [status, setStatus] = useState('')
  const [page, setPage] = useState(1)
  const [inviting, setInviting] = useState(false)
  const users = useApi(() => api.get('/admin/users', { q, role, status, page, size: SIZE }), [q, role, status, page])
  const invitations = useApi(() => api.get('/admin/staff-invitations', { size: 50 }), [], { enabled: tab === 'invitations' })

  return (
    <AppLayout
      title="Users"
      subtitle="Search accounts, change roles, suspend or restore"
      headerActions={
        <Button size="small" icon="mail" iconColor="#fff" onClick={() => setInviting(true)}>
          Invite teacher or admin
        </Button>
      }
    >
      <Tabs
        label="Users"
        tabs={[
          { id: 'users', label: 'All users' },
          { id: 'invitations', label: 'Staff invitations' },
        ]}
        value={tab}
        onChange={setTab}
      />
      {tab === 'users' ? (
        <Card as="section" className="col gap12" role="tabpanel" aria-labelledby="tab-users">
          <div className="row gap12 wrap">
            <TextField
              className="grow"
              icon="search"
              aria-label="Search name or email"
              placeholder="Search name or email"
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setPage(1)
              }}
            />
            <Select
              prefix="Role"
              aria-label="Role"
              boxStyle={{ width: 180 }}
              options={[
                { value: '', label: 'All' },
                { value: 'student', label: 'Student' },
                { value: 'teacher', label: 'Teacher' },
                { value: 'admin', label: 'Admin' },
              ]}
              value={role}
              onChange={(v) => {
                setRole(v)
                setPage(1)
              }}
            />
            <Select
              prefix="Status"
              aria-label="Status"
              boxStyle={{ width: 200 }}
              options={[
                { value: '', label: 'All' },
                { value: 'active', label: 'Active' },
                { value: 'suspended', label: 'Suspended' },
                { value: 'deactivated', label: 'Pending deletion' },
                { value: 'deleted', label: 'Deleted' },
              ]}
              value={status}
              onChange={(v) => {
                setStatus(v)
                setPage(1)
              }}
            />
          </div>
          {users.loading && !users.data && <Loading />}
          <ErrorMessage error={users.error} />
          {users.data?.items.length === 0 && <Empty>No users match.</Empty>}
          {users.data?.items.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Name</th>
                    <th scope="col">Email</th>
                    <th scope="col">Role</th>
                    <th scope="col">Status</th>
                    <th scope="col">Joined</th>
                    <th scope="col">
                      <span className="sr-only">Manage</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {users.data.items.map((u) => (
                    <tr key={u.id}>
                      <td>
                        <div className="row gap8">
                          <Avatar name={u.name} size="small" />
                          <b>{u.name}</b>
                        </div>
                      </td>
                      <td className="muted" style={{ maxWidth: 220, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={u.email}>{u.email}</td>
                      <td>
                        <RolePicker user={u} onChanged={() => users.reload()} />
                      </td>
                      <td>{userStatusBadge(u)}</td>
                      <td className="muted">{formatDate(u.created_at)}</td>
                      <td className="small">
                        <Link to={`/admin/users/${u.id}`} className="link">
                          Manage
                        </Link>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          {users.data && <Pagination page={page} size={SIZE} total={users.data.total} onChange={setPage} />}
        </Card>
      ) : (
        <StaffInvitations invitations={invitations} />
      )}
      {inviting && <StaffInviteDialog onClose={() => setInviting(false)} onSent={() => invitations.reload()} />}
    </AppLayout>
  )
}

function StaffInvitations({ invitations }) {
  const toast = useToast()
  const [error, setError] = useState(null)
  async function cancel(inv) {
    try {
      await api.delete(`/invitations/${inv.id}`)
      toast('Invitation cancelled')
      invitations.reload()
    } catch (err) {
      setError(err)
    }
  }
  const tones = { pending: 'amber', accepted: 'green', declined: 'grey', cancelled: 'grey', expired: 'red' }
  return (
    <Card as="section" className="col gap12" role="tabpanel" aria-labelledby="tab-invitations">
      {invitations.loading && <Loading />}
      <ErrorMessage error={error ?? invitations.error} />
      {invitations.data?.items.length === 0 && <Empty>No staff invitations yet.</Empty>}
      {invitations.data?.items.length > 0 && (
        <table>
          <thead>
            <tr>
              <th scope="col">Email</th>
              <th scope="col">Role</th>
              <th scope="col">Status</th>
              <th scope="col">Invited by</th>
              <th scope="col">Expires</th>
              <th scope="col">
                <span className="sr-only">Cancel</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {invitations.data.items.map((inv) => (
              <tr key={inv.id}>
                <td>{inv.email}</td>
                <td>{capitalise(inv.role)}</td>
                <td>
                  <Badge tone={tones[inv.status]}>{capitalise(inv.status)}</Badge>
                </td>
                <td className="muted">{inv.invited_by.name}</td>
                <td className="muted">{formatShort(inv.expires_at)}</td>
                <td>
                  {inv.status === 'pending' && (
                    <button type="button" className="small red" style={{ fontWeight: 600 }} onClick={() => cancel(inv)}>
                      Cancel
                    </button>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </Card>
  )
}

export function AdminUserPage() {
  const { userId } = useParams()
  const { user: me } = useAuth()
  const toast = useToast()
  const detail = useApi(() => api.get(`/admin/users/${userId}`), [userId])
  const [asking, setAsking] = useState(false)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const u = detail.data

  async function setStatus(status) {
    setBusy(true)
    setError(null)
    try {
      await api.patch(`/admin/users/${userId}`, { status })
      toast(status === 'suspended' ? `${u.name} is suspended and logged out everywhere` : `${u.name} is active again`)
      detail.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
      setAsking(false)
    }
  }

  return (
    <AppLayout title={u?.name ?? 'User'} subtitle={u ? `${capitalise(u.role)} · joined ${formatDate(u.created_at)}` : ' '} activeNav="/admin/users">
      {detail.loading && !u && <Loading />}
      {detail.error && <PageError error={detail.error} />}
      {u && (
        <div className="row gap24 start stack-sm">
          <div className="col gap24 grow" style={{ minWidth: 0 }}>
            <Card as="section" className="col gap16">
              <div className="row gap16">
                <Avatar name={u.name} size="large" />
                <div className="grow">
                  <b style={{ fontSize: 18 }}>{u.name}</b>
                  <p className="small muted">{u.email}</p>
                </div>
                {userStatusBadge(u)}
              </div>
              <div className="row gap16 wrap">
                <div>
                  <span className="lbl">Role</span>
                  <RolePicker user={u} onChanged={() => detail.reload()} />
                </div>
                <div className="grow">
                  <span className="lbl">Emails</span>
                  {u.emails.map((e) => (
                    <p key={e.id} className="small">
                      {e.email}{' '}
                      <span className="muted">
                        · {e.is_primary ? 'primary' : 'second'} · {e.verified ? 'verified' : 'not verified'}
                      </span>
                    </p>
                  ))}
                </div>
              </div>
              <p className="tiny muted">A user promoted after joining courses as a student stays a student in those courses.</p>
            </Card>
            <Card as="section" className="col gap12">
              <h3>Courses</h3>
              {u.enrolments.length === 0 && <Empty>Not in any course.</Empty>}
              {u.enrolments.length > 0 && (
                <table>
                  <thead>
                    <tr>
                      <th scope="col">Course</th>
                      <th scope="col">Term</th>
                      <th scope="col">Role</th>
                      <th scope="col">Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {u.enrolments.map((e) => (
                      <tr key={e.course_id}>
                        <td>
                          <Link to={`/courses/${e.course_id}`} className="link">
                            {e.code} {e.title}
                          </Link>
                        </td>
                        <td>{formatTerm(e.term)}</td>
                        <td>{capitalise(e.role)}</td>
                        <td>{capitalise(e.status)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </Card>
          </div>
          <div className="col gap24 side-col" style={{ width: 380 }}>
            <Card as="section" className="col gap12" style={{ borderColor: 'var(--color-danger-border)' }}>
              <h3>{u.status === 'suspended' ? 'Restore account' : 'Suspend account'}</h3>
              <p className="small muted">
                {u.status === 'suspended'
                  ? 'The user can log in again. Their courses and teams are as they were.'
                  : 'The user is logged out everywhere and cannot log in until you restore the account. Every change is in the audit log.'}
              </p>
              <ErrorMessage error={error} />
              {u.status === 'suspended' ? (
                <Button onClick={() => setStatus('active')} disabled={busy}>
                  Restore account
                </Button>
              ) : (
                <Button variant="danger" onClick={() => setAsking(true)} disabled={busy || u.status !== 'active' || u.id === me.id}>
                  Suspend account
                </Button>
              )}
            </Card>
            <Card as="section" className="col gap8">
              <h3>History</h3>
              <Link to={`/admin/audit-log?actor_id=${u.id}`} className="small link">
                Actions by {u.name}
              </Link>
            </Card>
          </div>
          {asking && (
            <Confirm title={`Suspend ${u.name}?`} danger confirmLabel="Suspend" busy={busy} onConfirm={() => setStatus('suspended')} onCancel={() => setAsking(false)}>
              They are logged out at once and cannot log in. You can restore the account at any time.
            </Confirm>
          )}
        </div>
      )}
    </AppLayout>
  )
}

export function AdminCoursesPage() {
  const navigate = useNavigate()
  const [params, setParams] = useSearchParams()
  const without = params.get('without_teacher') === '1'
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const courses = useApi(() => api.get('/admin/courses', { without_teacher: without || undefined, page, size: SIZE }), [without, page])

  return (
    <AppLayout
      title="Courses"
      subtitle="Every course, archived ones included"
      headerActions={
        <Button size="small" icon="plus" onClick={() => setCreating(true)}>
          Create course
        </Button>
      }
    >
      <Card as="section" className="col gap12">
        <div className="row between gap12">
          <h3>{without ? 'Courses with no teacher' : 'All courses'}</h3>
          <div className="row gap8 small">
            <Toggle
              checked={without}
              onChange={(v) => {
                setParams(v ? { without_teacher: '1' } : {})
                setPage(1)
              }}
              label="Only courses with no teacher"
            />
            Only courses with no teacher
          </div>
        </div>
        {courses.loading && !courses.data && <Loading />}
        <ErrorMessage error={courses.error} />
        {courses.data?.items.length === 0 && <Empty>{without ? 'Every course has a teacher.' : 'No courses yet.'}</Empty>}
        {courses.data?.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Course</th>
                  <th scope="col">Department</th>
                  <th scope="col">Term</th>
                  <th scope="col">Teachers</th>
                  <th scope="col">Status</th>
                  <th scope="col">
                    <span className="sr-only">Actions</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {courses.data.items.map((c) => (
                  <tr key={c.id}>
                    <td>
                      <b>
                        {c.code} {c.title}
                      </b>
                    </td>
                    <td className="muted">{c.department.name}</td>
                    <td>{formatTerm(c.term)}</td>
                    <td>{c.teachers.map((t) => t.name).join(', ') || <span className="accent">None</span>}</td>
                    <td>
                      <Badge tone={c.archived ? 'grey' : 'green'}>{c.archived ? 'Archived' : 'Active'}</Badge>
                    </td>
                    <td>
                      <div className="row gap8" style={{ justifyContent: 'flex-end' }}>
                        <Button variant="secondary" size="small" to={`/courses/${c.id}`}>
                          Open
                        </Button>
                        <Button variant="tint" size="small" to={`/courses/${c.id}/manage?tab=members`}>
                          Manage
                        </Button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {courses.data && <Pagination page={page} size={SIZE} total={courses.data.total} onChange={setPage} />}
      </Card>
      {creating && <CourseForm onClose={() => setCreating(false)} onSaved={(c) => navigate(`/courses/${c.id}/manage?tab=members`)} />}
    </AppLayout>
  )
}

export function AdminDepartmentsPage() {
  const toast = useToast()
  const departments = useApi(() => getAll('/departments'), [])
  const [editing, setEditing] = useState(null) // null | {} (new) | department
  return (
    <AppLayout
      title="Departments"
      subtitle="Every course belongs to one department"
      headerActions={
        <Button size="small" icon="plus" onClick={() => setEditing({})}>
          Add department
        </Button>
      }
    >
      <Card as="section" className="col gap12">
        {departments.loading && <Loading />}
        {departments.data?.length === 0 && <Empty>No departments yet.</Empty>}
        {departments.data?.length > 0 && (
          <table>
            <thead>
              <tr>
                <th scope="col">Code</th>
                <th scope="col">Name</th>
                <th scope="col">
                  <span className="sr-only">Edit</span>
                </th>
              </tr>
            </thead>
            <tbody>
              {departments.data.map((d) => (
                <tr key={d.id}>
                  <td>
                    <Badge tone="purple">{d.code}</Badge>
                  </td>
                  <td>{d.name}</td>
                  <td style={{ textAlign: 'right' }}>
                    <Button variant="secondary" size="small" onClick={() => setEditing(d)}>
                      Rename
                    </Button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {editing && (
        <DepartmentDialog
          department={editing.id ? editing : null}
          onClose={() => setEditing(null)}
          onSaved={(d) => {
            toast(`${d.name} saved`)
            setEditing(null)
            departments.reload()
          }}
        />
      )}
    </AppLayout>
  )
}

function DepartmentDialog({ department, onClose, onSaved }) {
  const [code, setCode] = useState(department?.code ?? '')
  const [name, setName] = useState(department?.name ?? '')
  const [error, setError] = useState(null)
  async function save(event) {
    event.preventDefault()
    try {
      const body = { code: code.trim().toUpperCase(), name: name.trim() }
      const d = department ? await api.patch(`/departments/${department.id}`, body) : await api.post('/departments', body)
      onSaved(d)
    } catch (err) {
      setError(err)
    }
  }
  return (
    <Modal title={department ? 'Rename department' : 'Add a department'} onClose={onClose}>
      <form className="col gap16" onSubmit={save}>
        <TextField label="Code" placeholder="CSE" value={code} onChange={(e) => setCode(e.target.value)} required />
        <TextField label="Name" placeholder="Computer Science and Engineering" value={name} onChange={(e) => setName(e.target.value)} required />
        <ErrorMessage error={error} />
        <Button type="submit" disabled={!code || !name}>
          Save
        </Button>
      </form>
    </Modal>
  )
}

export function AdminAuditLogPage() {
  const [params] = useSearchParams()
  const [action, setAction] = useState('')
  const a = useDebounced(action.trim())
  const [page, setPage] = useState(1)
  const actor = params.get('actor_id')
  const log = useApi(() => api.get('/admin/audit-entries', { action: a, actor_id: actor, page, size: SIZE }), [a, actor, page])
  return (
    <AppLayout title="Audit log" subtitle="Every admin action and every role change, newest first">
      <Card as="section" className="col gap12">
        <div className="row gap12 wrap">
          <TextField
            className="grow"
            icon="search"
            aria-label="Filter by action"
            placeholder="Filter by action, for example role_changed"
            value={action}
            onChange={(e) => {
              setAction(e.target.value)
              setPage(1)
            }}
          />
          {actor && (
            <Button variant="secondary" to="/admin/audit-log">
              Show everyone
            </Button>
          )}
        </div>
        {log.loading && !log.data && <Loading />}
        <ErrorMessage error={log.error} />
        {log.data?.items.length === 0 && <Empty>No entries.</Empty>}
        {log.data?.items.map((e) => {
          const d = describeAudit(e)
          return (
            <div key={e.id} className="row gap12 start list-row">
              <Icon name="shield" size={16} color="var(--color-primary)" />
              <div className="grow">
                <p className="small">
                  <b>{e.actor.name}</b> {d.action} {d.target}
                  {d.change && `: ${d.change}`}
                  {e.as_admin && (
                    <Badge tone="purple" style={{ marginLeft: 8 }}>
                      as admin
                    </Badge>
                  )}
                </p>
                <p className="tiny muted">
                  {formatShort(e.created_at)} · {e.target_type} #{e.target_id}
                </p>
              </div>
            </div>
          )
        })}
        {log.data && <Pagination page={page} size={SIZE} total={log.data.total} onChange={setPage} />}
      </Card>
    </AppLayout>
  )
}

export function AdminSettingsPage() {
  const settings = useApi(() => api.get('/admin/settings', { size: 50 }), [])
  return (
    <AppLayout title="Settings" subtitle="Platform-wide limits and rules">
      <Card as="section" className="col gap12">
        {settings.loading && <Loading />}
        <ErrorMessage error={settings.error} />
        {settings.data?.items.map((s) => (
          <SettingRow key={s.key} setting={s} onSaved={() => settings.reload()} />
        ))}
      </Card>
    </AppLayout>
  )
}

// "ai_requests_per_submission" -> "AI requests per submission"
export function settingLabel(key) {
  const words = key.split('_').map((w) => (['ai', 'ip'].includes(w) ? w.toUpperCase() : w))
  const text = words.join(' ')
  return text.charAt(0).toUpperCase() + text.slice(1)
}

function SettingRow({ setting, onSaved }) {
  const toast = useToast()
  const label = settingLabel(setting.key)
  const kind = typeof setting.default
  const [value, setValue] = useState(kind === 'object' ? JSON.stringify(setting.value) : String(setting.value))
  const [error, setError] = useState(null)

  async function save(v = value) {
    setError(null)
    try {
      const parsed = kind === 'number' ? Number(v) : kind === 'boolean' ? v === true || v === 'true' : kind === 'object' ? JSON.parse(v) : v
      await api.put(`/admin/settings/${setting.key}`, { value: parsed })
      toast('Setting saved')
      onSaved()
    } catch (err) {
      setError(err instanceof SyntaxError ? { message: 'This is not valid JSON.' } : err)
    }
  }

  return (
    <div className="row gap16 list-row wrap">
      <div className="grow" style={{ minWidth: 260 }}>
        <b>{label}</b>
        <p className="small muted">{setting.description}</p>
        <p className="tiny muted">
          Default {JSON.stringify(setting.default)}
          {setting.updated_at && ` · changed ${formatShort(setting.updated_at)}`}
        </p>
        {error && <p className="field-error">{error.message}</p>}
      </div>
      {kind === 'boolean' ? (
        <Toggle
          checked={value === 'true'}
          label={label}
          onChange={(v) => {
            setValue(String(v))
            save(String(v))
          }}
        />
      ) : (
        <div className="row gap8">
          <div className="inp" style={{ width: 220 }}>
            <input aria-label={label} value={value} onChange={(e) => setValue(e.target.value)} inputMode={kind === 'number' ? 'decimal' : undefined} />
          </div>
          <Button variant="secondary" size="small" onClick={() => save()}>
            Save
          </Button>
        </div>
      )}
    </div>
  )
}

