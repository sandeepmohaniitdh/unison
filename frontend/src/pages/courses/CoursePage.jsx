import { useState } from 'react'
import { Link, useLocation, useParams } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import {
  Avatar,
  Badge,
  Button,
  Card,
  Empty,
  ErrorMessage,
  Icon,
  Loading,
  PageError,
  Pagination,
  Tabs,
  useToast,
} from '../../components'
import AppLayout from '../../layouts/AppLayout'
import PublicPage from '../../layouts/PublicNav'
import { formatDayMonth, formatDeadline } from '../../lib/datetime'
import { formatTerm, plural } from '../../lib/format'
import { AssignmentTable, ResourceRow, typeBadge } from './courseBits'

// Figma 02: a course as its members see it. Visitors and non-members see the public
// part (description, teachers, assignment titles) and can ask to join.
export default function CoursePage() {
  const { courseId } = useParams()
  const { user, status } = useAuth()
  const course = useApi(() => api.get(`/courses/${courseId}`), [courseId, status], { enabled: status !== 'loading' })

  if (status === 'loading' || (course.loading && !course.data)) {
    return status === 'in' ? (
      <AppLayout title="Course" activeNav="/courses">
        <Loading />
      </AppLayout>
    ) : (
      <Loading />
    )
  }
  const c = course.data
  const subtitle = c
    ? [c.department.name, c.teachers.map((t) => t.name).join(', '), formatTerm(c.term)].filter(Boolean).join(' · ')
    : ''
  const title = c ? `${c.code} · ${c.title}` : 'Course'
  const member = c && (c.my_status === 'student' || c.my_status === 'teacher' || user?.role === 'admin')

  if (!user) {
    return (
      <PublicPage>
        <main id="main" className="col gap24 page-pad">
          {course.error ? <PageError error={course.error} /> : <CoursePreview course={c} title={title} subtitle={subtitle} reload={course.reload} />}
        </main>
      </PublicPage>
    )
  }
  return (
    <AppLayout
      title={title}
      subtitle={subtitle}
      activeNav="/courses"
      headerActions={
        c && (c.my_status === 'teacher' || user.role === 'admin') ? (
          <Button variant="secondary" size="small" icon="settings" to={`/courses/${c.id}/manage`}>
            Manage course
          </Button>
        ) : null
      }
    >
      {course.error && <PageError error={course.error} />}
      {c && (member ? <MemberView course={c} /> : <CoursePreview course={c} reload={course.reload} inApp />)}
    </AppLayout>
  )
}

const TABS = [
  { id: 'overview', label: 'Overview' },
  { id: 'resources', label: 'Resources' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'members', label: 'Members' },
]

function MemberView({ course }) {
  const location = useLocation()
  const [tab, setTab] = useState(location.hash === '#resources' ? 'resources' : 'overview')
  const isTeacher = course.my_status === 'teacher' || course.my_enrolment?.role === 'teacher'
  const teacherView = isTeacher || course.my_status !== 'student'
  const assignments = useApi(() => getAll(`/courses/${course.id}/assignments`), [course.id])
  const resources = useApi(() => api.get(`/courses/${course.id}/resources`, { status: 'published', size: 50 }), [course.id])

  return (
    <>
      <Tabs label="Course sections" tabs={TABS} value={tab} onChange={setTab} />
      <div role="tabpanel" aria-labelledby={`tab-${tab}`} className="col gap24">
        {tab === 'overview' && (
          <div className="row gap24 start stack-sm">
            <div className="col gap24 grow" style={{ minWidth: 0 }}>
              <AssignmentsCard assignments={assignments} isTeacher={teacherView} />
              <ResourcesCard resources={resources} limit={4} />
            </div>
            <div className="col gap24 side-col" style={{ width: 340 }}>
              <AboutCard course={course} />
              <TeachersCard course={course} />
              <EnrolmentCard course={course} />
            </div>
          </div>
        )}
        {tab === 'resources' && <AllResources courseId={course.id} />}
        {tab === 'assignments' && <AssignmentsCard assignments={assignments} isTeacher={teacherView} />}
        {tab === 'members' && <MembersTab course={course} isTeacher={teacherView} />}
      </div>
    </>
  )
}

function AssignmentsCard({ assignments, isTeacher }) {
  return (
    <Card as="section" className="col gap12" aria-labelledby="assignments-title">
      <div className="row between">
        <h3 id="assignments-title">Assignments</h3>
        <span className="small muted">All deadlines in IST</span>
      </div>
      <ErrorMessage error={assignments.error} />
      {assignments.loading && <Loading />}
      {assignments.data?.length === 0 && <Empty>No assignments yet.</Empty>}
      {assignments.data?.length > 0 && <AssignmentTable assignments={assignments.data} isTeacher={isTeacher} />}
    </Card>
  )
}

function ResourcesCard({ resources, limit }) {
  const items = resources.data?.items ?? []
  return (
    <Card as="section" className="col" aria-labelledby="resources-title">
      <div className="row between" style={{ marginBottom: 4 }}>
        <h3 id="resources-title">Resources</h3>
        <span className="small muted">{resources.data ? `${resources.data.total} published` : ''}</span>
      </div>
      <ErrorMessage error={resources.error} />
      {resources.loading && <Loading />}
      {resources.data && items.length === 0 && <Empty>No resources published yet.</Empty>}
      {(limit ? items.slice(0, limit) : items).map((r) => (
        <ResourceRow key={r.id} resource={r} />
      ))}
    </Card>
  )
}

function AllResources({ courseId }) {
  const [page, setPage] = useState(1)
  const resources = useApi(() => api.get(`/courses/${courseId}/resources`, { status: 'published', page, size: 20 }), [courseId, page])
  return (
    <>
      <ResourcesCard resources={resources} />
      {resources.data && <Pagination page={page} size={20} total={resources.data.total} onChange={setPage} />}
    </>
  )
}

function AboutCard({ course }) {
  return (
    <Card as="section" className="col gap8">
      <h3>About this course</h3>
      <p className="muted">{course.description || 'No description yet.'}</p>
    </Card>
  )
}

function TeachersCard({ course }) {
  return (
    <Card as="section" className="col gap12">
      <h3>Teachers</h3>
      {course.teachers.length === 0 && <Empty>No teacher assigned yet.</Empty>}
      {course.teachers.map((t) => (
        <div key={t.id} className="row gap12">
          <Avatar name={t.name} />
          <div>
            <b>{t.name}</b>
            <p className="small muted">Course teacher</p>
          </div>
        </div>
      ))}
    </Card>
  )
}

function EnrolmentCard({ course }) {
  const e = course.my_enrolment
  if (!e) {
    return (
      <Card as="section" className="col gap8">
        <h3>Your access</h3>
        <Badge tone="purple" style={{ alignSelf: 'flex-start' }}>
          Administrator
        </Badge>
        <p className="small muted">You can open every course as an administrator. Your actions are recorded.</p>
      </Card>
    )
  }
  const how =
    e.via === 'join_request'
      ? `Your join request was approved${e.decided_by ? ` by ${e.decided_by.name}` : ''}.`
      : e.via === 'invitation'
        ? `Joined by invitation from ${e.decided_by.name}.`
        : e.role === 'teacher'
          ? 'You teach this course.'
          : 'You were added to this course.'
  return (
    <Card as="section" className="col gap8">
      <h3>Your enrolment</h3>
      <Badge tone="green" icon="check" style={{ alignSelf: 'flex-start' }}>
        {e.role === 'teacher' ? 'Teaching' : 'Enrolled'} since {formatDayMonth(e.joined_at)}
      </Badge>
      <p className="small muted">{how}</p>
      {course.archived && <p className="small muted">This course is archived and read-only.</p>}
    </Card>
  )
}

function MembersTab({ course, isTeacher }) {
  const [page, setPage] = useState(1)
  const members = useApi(() => (isTeacher ? getAll(`/courses/${course.id}/members`, { status: 'active' }) : Promise.resolve(null)), [course.id, isTeacher])
  if (!isTeacher) {
    return (
      <div className="row gap24 start stack-sm">
        <div className="grow">
          <TeachersCard course={course} />
        </div>
        <Card className="col gap8 side-col" style={{ width: 340 }}>
          <h3>Students</h3>
          <p className="muted">{plural(course.student_count, 'student')} enrolled.</p>
          <p className="small muted">Only teachers see the full member list. Your team members are on each team page.</p>
        </Card>
      </div>
    )
  }
  return (
    <Card as="section" className="col gap12">
      <div className="row between">
        <h3>Members</h3>
        <Link to={`/courses/${course.id}/manage?tab=members`} className="small link">
          Manage members
        </Link>
      </div>
      {members.loading && <Loading />}
      <ErrorMessage error={members.error} />
      {members.data && (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th scope="col">Name</th>
                <th scope="col">Email</th>
                <th scope="col">Role</th>
                <th scope="col">Since</th>
              </tr>
            </thead>
            <tbody>
              {members.data.slice((page - 1) * 20, page * 20).map((m) => (
                <tr key={m.user.id}>
                  <td>
                    <div className="row gap8">
                      <Avatar name={m.user.name} size="small" />
                      <b>{m.user.name}</b>
                    </div>
                  </td>
                  <td className="muted">{m.email}</td>
                  <td>
                    <Badge tone={m.role === 'teacher' ? 'purple' : 'grey'}>{m.role === 'teacher' ? 'Teacher' : 'Student'}</Badge>
                  </td>
                  <td className="muted">{m.joined_at ? formatDayMonth(m.joined_at) : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      {members.data && <Pagination page={page} size={20} total={members.data.length} onChange={setPage} />}
    </Card>
  )
}

// What visitors and non-members see, with the join request button.
function CoursePreview({ course, title, subtitle, reload, inApp = false }) {
  const { user } = useAuth()
  const toast = useToast()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)

  async function act(fn, message) {
    setBusy(true)
    setError(null)
    try {
      await fn()
      toast(message)
      reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  let action
  if (!user) {
    action = (
      <>
        <p className="small muted">Log in with your @iitdh.ac.in account to ask to join.</p>
        <Button to={`/login?next=${encodeURIComponent(`/courses/${course.id}`)}`} full>
          Log in to join
        </Button>
      </>
    )
  } else if (course.archived) {
    action = <p className="small muted">This course is archived.</p>
  } else if (course.my_status === 'requested') {
    action = (
      <>
        <Badge tone="amber" style={{ alignSelf: 'flex-start' }}>
          Join request sent
        </Badge>
        <p className="small muted">The teachers will approve or reject it. You will be notified.</p>
        <Button variant="secondary" full disabled={busy} onClick={() => act(() => api.delete(`/courses/${course.id}/join-requests/mine`), 'Join request cancelled')}>
          Cancel my request
        </Button>
      </>
    )
  } else if (course.my_status === 'removed') {
    action = <p className="small muted">You were removed from this course. Ask a teacher if this is a mistake.</p>
  } else if (user.role !== 'student') {
    action = <p className="small muted">Only students ask to join. Teachers are assigned by an administrator.</p>
  } else if (!course.join_requests_open) {
    action = <p className="small muted">This course is invite only. Ask the teacher for an invitation.</p>
  } else {
    action = (
      <>
        {course.my_status === 'rejected' && <p className="small muted">Your last request was rejected. You may ask again.</p>}
        {course.my_status === 'left' && <p className="small muted">You left this course. You may ask to join again.</p>}
        <Button full disabled={busy} onClick={() => act(() => api.post(`/courses/${course.id}/join-requests`), 'Join request sent')}>
          {busy ? 'Sending…' : 'Ask to join'}
        </Button>
      </>
    )
  }

  return (
    <>
      {!inApp && (
        <div>
          <div className="eyebrow">{course.department.name}</div>
          <h1 style={{ marginTop: 6 }}>{title}</h1>
          <p className="muted" style={{ marginTop: 6 }}>
            {subtitle}
          </p>
        </div>
      )}
      <div className="row gap24 start stack-sm">
        <div className="col gap24 grow" style={{ minWidth: 0 }}>
          <AboutCard course={course} />
          <Card as="section" className="col gap12">
            <div className="row between">
              <h3>Assignments</h3>
              <span className="small muted">All deadlines in IST</span>
            </div>
            {course.assignments.length === 0 && <Empty>No assignments published yet.</Empty>}
            {course.assignments.length > 0 && (
              <table>
                <thead>
                  <tr>
                    <th scope="col">Assignment</th>
                    <th scope="col">Type</th>
                    <th scope="col">Deadline</th>
                  </tr>
                </thead>
                <tbody>
                  {course.assignments.map((a) => (
                    <tr key={a.id}>
                      <td>
                        <b>{a.title}</b>
                      </td>
                      <td>{a.kind === 'group' ? <Badge tone="purple">Group</Badge> : typeBadge(a)}</td>
                      <td>{formatDeadline(a.due_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </Card>
        </div>
        <div className="col gap24 side-col" style={{ width: 340 }}>
          <Card as="section" className="col gap12">
            <h3>Join this course</h3>
            <div className="row gap8 small muted">
              <Icon name="users" size={15} />
              {plural(course.student_count, 'student')} enrolled
            </div>
            <ErrorMessage error={error} />
            {action}
          </Card>
          <TeachersCard course={course} />
        </div>
      </div>
    </>
  )
}
