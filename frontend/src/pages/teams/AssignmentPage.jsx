import { useState } from 'react'
import { Navigate, useNavigate, useParams } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import { Badge, Button, Card, Empty, ErrorMessage, Loading, PageError, TextField, useToast } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDay, formatDeadline } from '../../lib/datetime'
import { points } from '../../lib/format'

// /assignments/<id> (links in notifications): students go to their team workspace; for a
// group assignment without a team yet, this page lets them create one or answer an
// invitation. Teachers go to the review page.
export default function AssignmentPage() {
  const { assignmentId } = useParams()
  const { user } = useAuth()
  const navigate = useNavigate()
  const toast = useToast()
  const assignment = useApi(() => api.get(`/assignments/${assignmentId}`), [assignmentId])
  const a = assignment.data
  const course = useApi(() => (a ? api.get(`/courses/${a.course_id}`) : Promise.resolve(null)), [a?.course_id], { enabled: Boolean(a) })
  const isTeacher = user.role === 'admin' || course.data?.my_status === 'teacher'
  const myTeam = useApi(
    () =>
      api.get(`/assignments/${assignmentId}/my-team`).catch((err) => {
        if (err.status === 404) return null
        throw err
      }),
    [assignmentId],
    { enabled: Boolean(course.data) && !isTeacher },
  )
  const invitations = useApi(
    async () => (await getAll('/users/me/invitations')).filter((i) => i.kind === 'team' && String(i.team?.assignment_id) === String(assignmentId)),
    [assignmentId],
    { enabled: myTeam.data === null && !myTeam.loading },
  )
  const [name, setName] = useState('')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  if (course.data && isTeacher) return <Navigate to={`/assignments/${assignmentId}/review`} replace />
  if (myTeam.data) return <Navigate to={`/teams/${myTeam.data.id}`} replace />

  async function create(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const team = await api.post(`/assignments/${assignmentId}/teams`, { name: name.trim() })
      toast(`Team ${team.name} created. Invite your classmates.`)
      navigate(`/teams/${team.id}`)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function answer(inv, status) {
    setError(null)
    try {
      const res = await api.patch(`/invitations/${inv.id}`, { status })
      if (status === 'accepted') navigate(`/teams/${res.team_id}`)
      else invitations.reload()
    } catch (err) {
      setError(err)
    }
  }

  const c = course.data
  const loading = assignment.loading || course.loading || myTeam.loading
  return (
    <AppLayout title={a?.title ?? 'Assignment'} subtitle={c ? `${c.code} ${c.title}` : ' '} activeNav="/courses">
      {loading && <Loading />}
      {(assignment.error || course.error || myTeam.error) && <PageError error={assignment.error ?? course.error ?? myTeam.error} />}
      {!loading && a && myTeam.data === null && a.kind === 'individual' && (
        <Card className="col gap8">
          <h3>Nothing to open</h3>
          <p className="small muted">
            {a.status === 'draft' ? 'This assignment is not published yet.' : `The deadline (${formatDeadline(a.due_at)}) passed and you did not upload anything.`}
          </p>
        </Card>
      )}
      {!loading && a && myTeam.data === null && a.kind === 'group' && (
        <div className="row gap24 start stack-sm">
          <div className="col gap24 grow" style={{ minWidth: 0 }}>
            <Card as="section" highlight className="col gap12">
              <h3>You are not in a team yet</h3>
              <p className="small muted">
                This is a group assignment for teams of {a.min_team} to {a.max_team}. Create a team and invite classmates, or accept an
                invitation from a team. Due {formatDeadline(a.due_at)}.
              </p>
              {a.teams_locked ? (
                <p className="small muted">Your teacher locked the teams. Ask them to add you to a team.</p>
              ) : (
                <form className="row gap12 wrap" onSubmit={create}>
                  <TextField
                    className="grow"
                    aria-label="Team name"
                    placeholder="Team name, for example Byte Builders"
                    value={name}
                    onChange={(e) => setName(e.target.value)}
                  />
                  <Button type="submit" disabled={busy || !name.trim()}>
                    {busy ? 'Creating…' : 'Create team'}
                  </Button>
                </form>
              )}
              <ErrorMessage error={error} />
            </Card>
            <Card as="section" className="col gap12">
              <h3>Team invitations for this assignment</h3>
              {invitations.loading && <Loading />}
              {invitations.data?.length === 0 && <Empty>No invitations yet.</Empty>}
              {invitations.data?.map((inv) => (
                <div key={inv.id} className="row gap12">
                  <div className="grow">
                    <b>Team {inv.team.name}</b>
                    <p className="small muted">
                      From {inv.invited_by.name} · {inv.team.members.join(', ')} · expires {formatDay(inv.expires_at)}
                    </p>
                  </div>
                  <Button variant="secondary" size="small" onClick={() => answer(inv, 'declined')}>
                    Decline
                  </Button>
                  <Button size="small" onClick={() => answer(inv, 'accepted')}>
                    Accept
                  </Button>
                </div>
              ))}
            </Card>
          </div>
          <Card as="section" className="col gap12 side-col" style={{ width: 360 }}>
            <h3>About this assignment</h3>
            <div className="row gap8 wrap">
              <Badge tone="purple" icon="users">
                Group · {a.min_team}–{a.max_team}
              </Badge>
              <Badge tone="amber" icon="clock">
                {formatDeadline(a.due_at)}
              </Badge>
            </div>
            <p className="small muted" style={{ whiteSpace: 'pre-wrap' }}>
              {a.description || 'No description.'}
            </p>
            <span className="lbl" style={{ margin: 0 }}>
              Rubric · {points(a.total_points)} points
            </span>
            {a.rubric.map((r) => (
              <div key={r.id} className="row between small">
                <span>{r.title}</span>
                <b>{points(r.max_points)}</b>
              </div>
            ))}
          </Card>
        </div>
      )}
    </AppLayout>
  )
}
