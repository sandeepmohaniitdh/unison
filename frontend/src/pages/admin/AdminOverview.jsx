import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router'
import { api } from '../../api/client'
import useApi from '../../api/useApi'
import { Alert, Avatar, Button, Card, Empty, Icon, Loading, PageError, PieChart, StatCard, TextField } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatShort } from '../../lib/datetime'
import { plural } from '../../lib/format'
import CourseForm from '../courses/CourseForm'
import { describeAudit, RolePicker, StaffInviteDialog, userStatusBadge } from './adminBits'

// Figma 10: the admin dashboard, simplified: four numbers, users by role as a pie chart,
// the latest admin actions and the user list.
export default function AdminOverview() {
  const navigate = useNavigate()
  const stats = useApi(() => api.get('/admin/stats'), [])
  const audit = useApi(() => api.get('/admin/audit-entries', { size: 5 }), [])
  const [query, setQuery] = useState('')
  const [q, setQ] = useState('')
  const users = useApi(() => api.get('/admin/users', { q, size: 5 }), [q])
  const [inviting, setInviting] = useState(false)
  const [creating, setCreating] = useState(false)

  useEffect(() => {
    const t = setTimeout(() => setQ(query.trim()), 300)
    return () => clearTimeout(t)
  }, [query])

  const s = stats.data
  const total = s ? s.users.students + s.users.teachers + s.users.admins : 0
  const change = s && s.finals_last_week ? Math.round(((s.finals_this_week - s.finals_last_week) / s.finals_last_week) * 100) : null

  return (
    <AppLayout title="Platform overview" subtitle="Everything on Unison, with every admin action recorded">
      <div className="row gap12 wrap">
        <Button icon="mail" iconColor="#fff" onClick={() => setInviting(true)}>
          Invite teacher or admin
        </Button>
        <Button variant="secondary" icon="plus" onClick={() => setCreating(true)}>
          Create course
        </Button>
        <Button variant="secondary" icon="book" to="/admin/departments">
          Departments
        </Button>
      </div>
      {stats.loading && <Loading />}
      {stats.error && <PageError error={stats.error} />}
      {s && (
        <>
          <div className="stat-grid">
            <StatCard label="Users" value={total} note="Students, teachers and admins" />
            <StatCard label="Active courses" value={s.active_courses} note={`in ${plural(s.departments, 'department')}`} />
            <StatCard
              label="Finals this week"
              value={s.finals_this_week}
              note={change == null ? `${s.finals} in total` : `${change >= 0 ? '+' : ''}${change}% on last week`}
            />
            <StatCard
              label="Failed emails"
              value={s.failed_emails_24h}
              note="last 24 hours"
              noteTone={s.failed_emails_24h > 0 ? 'accent' : 'muted'}
            />
          </div>
          {s.courses_without_teacher > 0 && (
            <Alert tone="note">
              {plural(s.courses_without_teacher, 'course has', 'courses have')} no teacher.{' '}
              <Link to="/admin/courses?without_teacher=1" className="link">
                Assign a teacher
              </Link>
            </Alert>
          )}
        </>
      )}
      <div className="admin-grid">
        <Card as="section" className="col gap16" aria-labelledby="roles-title">
          <div className="row between">
            <h3 id="roles-title">Users by role</h3>
            <Link to="/admin/users" className="small link">
              Manage users
            </Link>
          </div>
          {s && (
            <PieChart
              label="Users by role"
              centerLabel="users"
              data={[
                { label: 'Students', value: s.users.students },
                { label: 'Teachers', value: s.users.teachers },
                { label: 'Admins', value: s.users.admins },
              ]}
            />
          )}
        </Card>
        <Card as="section" className="col" aria-labelledby="audit-title">
          <div className="row between">
            <h3 id="audit-title">Audit log</h3>
            <Link to="/admin/audit-log" className="small link">
              View all
            </Link>
          </div>
          {audit.loading && <Loading />}
          {audit.data?.items.length === 0 && <Empty>No admin actions yet.</Empty>}
          {audit.data?.items.map((e) => {
            const d = describeAudit(e)
            return (
              <div key={e.id} className="row gap12 start" style={{ padding: '10px 0', borderBottom: '1px solid var(--color-row-divider)' }}>
                <Icon name="shield" size={16} color="var(--color-primary)" />
                <div style={{ minWidth: 0 }}>
                  <p className="small">
                    <b>{e.actor.name}</b> {d.action} {d.target}
                    {d.change && `: ${d.change}`}
                  </p>
                  <p className="tiny muted">{formatShort(e.created_at)}</p>
                </div>
              </div>
            )
          })}
        </Card>
      </div>
      <Card as="section" className="col gap12" style={{ minWidth: 0 }} aria-labelledby="users-title">
        <div className="row between gap12 wrap">
          <h3 id="users-title">Users</h3>
          <TextField
            icon="search"
            iconSize={15}
            boxClassName="small"
            boxStyle={{ width: 260, maxWidth: '100%', height: 36 }}
            aria-label="Search name or email"
            placeholder="Search name or email"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        {users.loading && !users.data && <Loading />}
        {users.data?.items.length === 0 && <Empty>No users match.</Empty>}
        {users.data && users.data.items.length > 0 && (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th scope="col">Name</th>
                  <th scope="col">Email</th>
                  <th scope="col">Role</th>
                  <th scope="col">Status</th>
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
                    <td className="muted">{u.email}</td>
                    <td>
                      <RolePicker user={u} onChanged={() => users.reload()} />
                    </td>
                    <td>{userStatusBadge(u)}</td>
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
        <Link to="/admin/users" className="small link">
          All {plural(users.data?.total ?? 0, 'user')}
        </Link>
      </Card>
      {inviting && <StaffInviteDialog onClose={() => setInviting(false)} />}
      {creating && <CourseForm onClose={() => setCreating(false)} onSaved={(c) => navigate(`/courses/${c.id}/manage?tab=members`)} />}
    </AppLayout>
  )
}
