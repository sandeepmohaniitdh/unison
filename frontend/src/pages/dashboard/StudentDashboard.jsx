import { useState } from 'react'
import { Link } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Avatar,
  Badge,
  Button,
  Card,
  DateTile,
  Empty,
  ErrorMessage,
  Icon,
  Loading,
  PageError,
  ProgressBar,
  StatCard,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { dateTile, formatDay, formatDeadline, formatTime, greeting, isWithinDays } from '../../lib/datetime'
import { deadlineBadge, formatTerm, greetingName, plural } from '../../lib/format'
import NotificationList from '../notifications/NotificationList'

// Figma 05: the student dashboard.
export default function StudentDashboard() {
  const { user, refreshCounts } = useAuth()
  const toast = useToast()
  const dash = useApi(() => api.get('/dashboards/student'), [])
  const invites = useApi(() => getAll('/users/me/invitations'), [])
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  const d = dash.data
  const title = `${greeting()}, ${greetingName(user.name)}`
  const dueThisWeek = d ? d.upcoming_deadlines.filter((x) => isWithinDays(x.due_at, 7)) : []
  const subtitle = d
    ? `You have ${plural(d.pending_invitations.length, 'invitation')} and ${plural(dueThisWeek.length, 'deadline')} this week`
    : ' '

  async function answer(invitation, status) {
    setBusy(`${invitation.id}-${status}`)
    setError(null)
    try {
      await api.patch(`/invitations/${invitation.id}`, { status })
      toast(status === 'accepted' ? 'Invitation accepted' : 'Invitation declined')
      dash.reload()
      invites.reload()
      refreshCounts()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  async function markAllRead() {
    try {
      const res = await api.patch('/notifications', { read: true })
      toast(res.marked ? `${plural(res.marked, 'notification')} marked as read` : 'Nothing new to mark')
      dash.setData((old) => ({ ...old, unread_notifications: 0, notifications: old.notifications.map((n) => ({ ...n, read: true })) }))
      refreshCounts()
    } catch (err) {
      setError(err)
    }
  }

  return (
    <AppLayout title={title} subtitle={subtitle}>
      {dash.loading && !d && <Loading />}
      {dash.error && <PageError error={dash.error} />}
      {d && (
        <StudentDashboardBody
          d={d}
          invitations={invites.data ?? []}
          dueThisWeek={dueThisWeek}
          busy={busy}
          error={error}
          onAnswer={answer}
          onMarkAllRead={markAllRead}
          onNotificationRead={(n) =>
            dash.setData((old) => ({ ...old, notifications: old.notifications.map((x) => (x.id === n.id ? n : x)) }))
          }
        />
      )}
    </AppLayout>
  )
}

function StudentDashboardBody({ d, invitations, dueThisWeek, busy, error, onAnswer, onMarkAllRead, onNotificationRead }) {
  const codes = Object.fromEntries(d.courses.map((c) => [c.id, c.code]))
  const open = d.upcoming_deadlines
  const withFinal = open.filter((x) => ['final_submitted', 'submitted_at_deadline', 'marks_released'].includes(x.state)).length
  const next = dueThisWeek[0] ?? open[0]
  const draftsOnly = open.filter((x) => x.state === 'drafts')
  const noTeam = open.filter((x) => x.state === 'no_team')
  const actions = invitations.length + draftsOnly.length + noTeam.length
  const terms = [...new Set(d.courses.map((c) => formatTerm(c.term)))].join(', ')

  return (
    <>
      <div className="stat-grid">
        <StatCard label="Courses" value={d.courses.length} note={terms || 'No courses yet'} />
        <StatCard
          label="Due this week"
          value={dueThisWeek.length}
          note={next ? `Next: ${formatDeadline(next.due_at)}` : 'Nothing due'}
          noteTone={next ? 'accent' : 'muted'}
        />
        <StatCard label="Finals submitted" value={`${withFinal} / ${open.length}`}>
          <ProgressBar value={open.length ? (withFinal / open.length) * 100 : 0} label="Finals submitted for open assignments" />
        </StatCard>
        <Card className="col gap8 grow">
          <span className="small muted">Marks released</span>
          <b className="stat-value">{d.released_marks.length}</b>
          {d.released_marks.length > 0 ? (
            <Link to={`/teams/${d.released_marks[0].team_id}/marks`} className="small link">
              View results
            </Link>
          ) : (
            <span className="small muted">None yet</span>
          )}
        </Card>
      </div>

      <div className="row gap24 start stack-sm">
        <div className="col gap24 grow" style={{ minWidth: 0 }}>
          <Card as="section" highlight className="col gap12" aria-labelledby="needs-action">
            <div className="row between">
              <h3 id="needs-action">Needs your action</h3>
              <Badge tone="amber">{actions}</Badge>
            </div>
            <ErrorMessage error={error} />
            {actions === 0 && <Empty>Nothing needs you right now.</Empty>}
            {invitations.map((inv) => (
              <div key={inv.id} className="row gap12">
                <Avatar initials={invitationInitials(inv)} size="small" />
                <div className="grow">
                  <Link to={`/invitations?id=${inv.id}`}>
                    <b>{invitationTitle(inv)}</b>
                  </Link>
                  <p className="small muted">
                    From {inv.invited_by.name}
                    {inv.team ? ` for ${inv.team.assignment_title}` : ''} · expires {formatDay(inv.expires_at)}
                  </p>
                </div>
                <Button variant="secondary" size="small" disabled={Boolean(busy)} onClick={() => onAnswer(inv, 'declined')}>
                  Decline
                </Button>
                <Button size="small" disabled={Boolean(busy)} onClick={() => onAnswer(inv, 'accepted')}>
                  Accept
                </Button>
              </div>
            ))}
            {draftsOnly.map((x) => (
              <div key={`draft-${x.assignment_id}`} className="row gap12">
                <Avatar initials={shortCode(x.title)} size="small" />
                <div className="grow">
                  <b>{x.title} has a draft but no final</b>
                  <p className="small muted">
                    {x.course.code} · due {formatDeadline(x.due_at)}
                  </p>
                </div>
                <Button variant="secondary" size="small" to={x.team_id ? `/teams/${x.team_id}` : `/assignments/${x.assignment_id}`}>
                  Open
                </Button>
              </div>
            ))}
            {noTeam.map((x) => (
              <div key={`team-${x.assignment_id}`} className="row gap12">
                <Avatar initials={shortCode(x.title)} size="small" />
                <div className="grow">
                  <b>{x.title} needs a team</b>
                  <p className="small muted">
                    {x.course.code} · due {formatDeadline(x.due_at)}
                  </p>
                </div>
                <Button variant="secondary" size="small" to={`/assignments/${x.assignment_id}`}>
                  Open
                </Button>
              </div>
            ))}
          </Card>

          <Card as="section" className="col" aria-labelledby="notifications-title">
            <div className="row between">
              <h3 id="notifications-title">Notifications</h3>
              <button type="button" className="small link" onClick={onMarkAllRead}>
                Mark all as read
              </button>
            </div>
            {d.notifications.length === 0 && <Empty>No notifications yet.</Empty>}
            <NotificationList items={d.notifications} courseCodes={codes} onChange={onNotificationRead} />
            {d.notifications.length > 0 && (
              <Link to="/notifications" className="small link" style={{ marginTop: 12 }}>
                See all notifications
              </Link>
            )}
          </Card>
        </div>

        <div className="col gap24 side-col" style={{ width: 380 }}>
          <Card as="section" className="col gap12" aria-labelledby="deadlines-title">
            <h3 id="deadlines-title">Upcoming deadlines</h3>
            {open.length === 0 && <Empty>No upcoming deadlines.</Empty>}
            {open.slice(0, 5).map((x) => {
              const tile = dateTile(x.due_at)
              const [text, tone] = deadlineBadge(x.state)
              return (
                <Link
                  key={x.assignment_id}
                  to={x.team_id ? `/teams/${x.team_id}` : `/assignments/${x.assignment_id}`}
                  className="row gap12"
                >
                  <DateTile day={tile.day} month={tile.month} />
                  <div className="grow">
                    <b>{x.title}</b>
                    <p className="small muted">
                      {x.course.code} · {formatTime(x.due_at)}
                    </p>
                  </div>
                  <Badge tone={tone}>{text}</Badge>
                </Link>
              )
            })}
          </Card>

          <Card as="section" className="col gap12" aria-labelledby="courses-title">
            <h3 id="courses-title">My courses</h3>
            {d.courses.length === 0 && (
              <Empty>
                You are not in any course yet. <Link to="/catalogue" className="link">Browse the catalogue</Link>.
              </Empty>
            )}
            {d.courses.map((c) => (
              <Link key={c.id} to={`/courses/${c.id}`} className="row between">
                <span>
                  {c.code} {c.title}
                </span>
                <Icon name="chevronDown" size={16} />
              </Link>
            ))}
          </Card>
        </div>
      </div>
    </>
  )
}

// "Lab 4: Unit testing" -> "L4", "Course project" -> "CP"
function shortCode(title) {
  const words = title.replace(/[^A-Za-z0-9 ]/g, ' ').split(/\s+/).filter(Boolean)
  const number = title.match(/\d+/)
  if (number) return `${words[0][0]}${number[0]}`.toUpperCase().slice(0, 2)
  return words.slice(0, 2).map((w) => w[0]).join('').toUpperCase()
}

function invitationTitle(inv) {
  if (inv.kind === 'course') return `Course invitation · ${inv.course.code} ${inv.course.title}`
  if (inv.kind === 'team') return `Team invitation · ${inv.team.name}`
  return `Staff invitation · join as ${inv.role}`
}

function invitationInitials(inv) {
  if (inv.kind === 'course') return inv.course.code.slice(0, 2)
  if (inv.kind === 'team') return inv.team.name.slice(0, 2)
  return 'ST'
}
