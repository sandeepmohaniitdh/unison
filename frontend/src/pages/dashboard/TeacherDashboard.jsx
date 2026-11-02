import { useState } from 'react'
import { Link } from 'react-router'
import { api } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Avatar,
  Button,
  Card,
  Empty,
  ErrorMessage,
  Loading,
  PageError,
  ProgressBar,
  StatCard,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDeadline, greeting } from '../../lib/datetime'
import { greetingName, plural } from '../../lib/format'

// Figma 07: the teacher dashboard.
export default function TeacherDashboard() {
  const { user, refreshJoinRequests } = useAuth()
  const toast = useToast()
  const dash = useApi(() => api.get('/dashboards/teacher'), [])
  const courses = dash.data?.courses ?? []
  const withRequests = courses.filter((c) => c.pending_join_requests > 0)
  const requests = useApi(
    async () => {
      const pages = await Promise.all(
        withRequests.map((c) =>
          api.get(`/courses/${c.id}/join-requests`, { size: 3 }).then((p) => p.items.map((r) => ({ ...r, course: c }))),
        ),
      )
      return pages.flat()
    },
    [withRequests.map((c) => c.id).join(',')],
    { enabled: Boolean(dash.data) },
  )
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)

  async function decide(request, status) {
    setBusy(`${request.id}-${status}`)
    setError(null)
    try {
      await api.patch(`/courses/${request.course.id}/join-requests/${request.id}`, { status })
      toast(status === 'approved' ? `${request.user.name} is now enrolled` : 'Join request rejected')
      requests.setData((list) => list.filter((r) => r.id !== request.id))
      dash.reload()
      refreshJoinRequests()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const d = dash.data
  const pendingRequests = courses.reduce((sum, c) => sum + c.pending_join_requests, 0)
  const assignments = d?.assignments ?? []
  // Reviews start after the deadline, so only closed assignments have finals to review.
  const closed = assignments.filter((a) => a.status === 'closed')
  const toReview = closed.reduce((sum, a) => sum + Math.max(0, a.with_final - a.released), 0)
  const firstToReview = closed.find((a) => a.with_final > a.released)
  const students = courses.reduce((sum, c) => sum + c.students, 0)
  const title = `${greeting()}, ${greetingName(user.name)}`
  const subtitle = d ? `${plural(pendingRequests, 'join request')} and ${plural(toReview, 'final')} waiting for review` : ' '
  const firstCourse = courses[0]

  return (
    <AppLayout title={title} subtitle={subtitle}>
      {dash.loading && !d && <Loading />}
      {dash.error && <PageError error={dash.error} />}
      {d && (
        <>
          <div className="stat-grid">
            <StatCard label="My courses" value={courses.length} note={courses.map((c) => c.code).join(', ') || 'None yet'} />
            <StatCard
              label="Students"
              value={students}
              note={courses.length === 2 ? 'across both courses' : `across ${plural(courses.length, 'course')}`}
            />
            <Card className="col gap8 grow">
              <span className="small muted">Finals to review</span>
              <b className="stat-value">{toReview}</b>
              {firstToReview ? (
                <Link to={`/assignments/${firstToReview.id}/review`} className="small link">
                  Open review
                </Link>
              ) : (
                <span className="small muted">All reviewed</span>
              )}
            </Card>
            <StatCard
              label="Join requests"
              value={pendingRequests}
              note={pendingRequests ? 'Waiting for you' : 'None waiting'}
              noteTone={pendingRequests ? 'accent' : 'muted'}
            />
          </div>

          <div className="row gap24 start stack-sm">
            <Card as="section" className="col grow" style={{ minWidth: 0 }} aria-labelledby="status-title">
              <div className="row between">
                <h3 id="status-title">Submission status</h3>
                {firstCourse && (
                  <Button variant="secondary" size="small" icon="plus" to={`/courses/${firstCourse.id}/manage?tab=assignments&new=1`}>
                    New assignment
                  </Button>
                )}
              </div>
              {assignments.length === 0 && <Empty>No published assignments yet.</Empty>}
              {assignments.map((a) => {
                const individual = a.kind === 'individual'
                const unit = individual ? 'students' : 'teams'
                const total = individual ? Math.max(a.teams, courses.find((c) => c.id === a.course.id)?.students ?? 0) : a.teams
                return (
                  <Link
                    key={a.id}
                    to={`/assignments/${a.id}/review`}
                    className="col gap8 list-row"
                    aria-label={`${a.course.code} ${a.title}: ${a.with_final} of ${total} ${unit} submitted`}
                  >
                    <div className="row between gap12">
                      <b>
                        {a.course.code} · {a.title}
                      </b>
                      <span className="small muted">
                        {a.status === 'closed' ? 'Closed' : 'Due'} {formatDeadline(a.due_at)}
                      </span>
                    </div>
                    <div className="row gap12">
                      <ProgressBar className="grow" value={total ? (a.with_final / total) * 100 : 0} label="Submitted" />
                      <span className="small" style={{ width: 170, textAlign: 'right' }}>
                        {a.with_final} of {total} {unit} submitted
                      </span>
                    </div>
                    {a.released > 0 && (
                      <span className="tiny muted">
                        {a.reviewed} reviewed · {a.released} released
                      </span>
                    )}
                  </Link>
                )
              })}
            </Card>

            <div className="col gap24 side-col" style={{ width: 420 }}>
              <Card as="section" className="col" aria-labelledby="requests-title">
                <div className="row between">
                  <h3 id="requests-title">Join requests</h3>
                  <Link to="/join-requests" className="small link">
                    See all
                  </Link>
                </div>
                <ErrorMessage error={error} />
                {requests.loading && <Loading />}
                {requests.data && requests.data.length === 0 && <Empty>No join requests waiting.</Empty>}
                {requests.data?.slice(0, 5).map((r) => (
                  <div key={r.id} className="row gap12" style={{ padding: '10px 0' }}>
                    <Avatar name={r.user.name} size="small" />
                    <div className="grow" style={{ minWidth: 0 }}>
                      <b>{r.user.name}</b>
                      <p className="tiny muted">
                        {r.email} · {r.course.code}
                      </p>
                    </div>
                    <Button variant="secondary" size="small" disabled={Boolean(busy)} onClick={() => decide(r, 'rejected')}>
                      Reject
                    </Button>
                    <Button size="small" disabled={Boolean(busy)} onClick={() => decide(r, 'approved')}>
                      Approve
                    </Button>
                  </div>
                ))}
              </Card>

              <Card as="section" className="col gap12" aria-labelledby="mycourses-title">
                <h3 id="mycourses-title">My courses</h3>
                {courses.length === 0 && <Empty>You do not teach a course yet.</Empty>}
                {courses.map((c) => (
                  <div key={c.id} className="row between gap12">
                    <Link to={`/courses/${c.id}`}>
                      <b>
                        {c.code} {c.title}
                      </b>
                      <p className="tiny muted">
                        {plural(c.students, 'student')}
                        {c.pending_join_requests ? ` · ${plural(c.pending_join_requests, 'join request')}` : ''}
                      </p>
                    </Link>
                    <Button variant="tint" size="small" to={`/courses/${c.id}/manage`}>
                      Manage
                    </Button>
                  </div>
                ))}
              </Card>
            </div>
          </div>
        </>
      )}
    </AppLayout>
  )
}
