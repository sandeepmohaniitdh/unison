import { useState } from 'react'
import { useNavigate } from 'react-router'
import { api } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import { Badge, Button, Card, Empty, Icon, Loading, PageError, Pagination } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatTerm, plural } from '../../lib/format'
import CourseForm from './CourseForm'

const SIZE = 12

// "My courses" from the sidebar (not drawn in Figma): course cards like the catalogue's.
export default function MyCoursesPage() {
  const { user } = useAuth()
  const navigate = useNavigate()
  const [page, setPage] = useState(1)
  const [creating, setCreating] = useState(false)
  const courses = useApi(() => api.get('/users/me/courses', { page, size: SIZE }), [page])
  const canCreate = user.role === 'teacher' || user.role === 'admin'

  return (
    <AppLayout
      title="My courses"
      subtitle={user.role === 'teacher' ? 'Courses you teach' : 'Courses you are enrolled in'}
      headerActions={
        canCreate ? (
          <Button size="small" icon="plus" onClick={() => setCreating(true)}>
            Create course
          </Button>
        ) : (
          <Button variant="secondary" size="small" icon="search" to="/catalogue">
            Find more courses
          </Button>
        )
      }
    >
      {courses.loading && !courses.data && <Loading />}
      {courses.error && <PageError error={courses.error} />}
      {courses.data?.items.length === 0 && (
        <Card className="col gap12">
          <h3>No courses yet</h3>
          <Empty>
            {user.role === 'student'
              ? 'Ask to join a course from the catalogue, or accept an invitation from a teacher.'
              : 'Create a course, or ask an administrator to assign you to one.'}
          </Empty>
          {user.role === 'student' && (
            <Button to="/catalogue" style={{ alignSelf: 'flex-start' }}>
              Browse the catalogue
            </Button>
          )}
        </Card>
      )}
      <div className="row wrap gap24 start">
        {courses.data?.items.map((c) => (
          <Card key={c.id} as="article" className="col gap12" style={{ width: 400, maxWidth: '100%' }}>
            <div className="row between">
              <Badge tone="purple">{c.code}</Badge>
              {c.archived ? (
                <Badge tone="grey">Archived</Badge>
              ) : (
                <Badge tone={c.my_status === 'teacher' ? 'purple' : 'green'}>{c.my_status === 'teacher' ? 'Teaching' : 'Enrolled'}</Badge>
              )}
            </div>
            <div>
              <h2 style={{ fontSize: 18, fontWeight: 600 }}>{c.title}</h2>
              <p className="muted small">{c.department.name}</p>
            </div>
            <div className="row gap8 muted small">
              <Icon name="user" size={15} />
              {c.teachers.map((t) => t.name).join(', ') || 'No teacher yet'} &nbsp;·&nbsp; {formatTerm(c.term)}
            </div>
            <div className="row between" style={{ marginTop: 4 }}>
              <span className="small muted">
                {plural(c.assignment_count ?? 0, 'assignment')} · {plural(c.resource_count ?? 0, 'resource')}
              </span>
              <div className="row gap8">
                {c.my_status === 'teacher' && (
                  <Button variant="tint" size="small" to={`/courses/${c.id}/manage`}>
                    Manage
                  </Button>
                )}
                <Button variant="secondary" size="small" to={`/courses/${c.id}`}>
                  Open course
                </Button>
              </div>
            </div>
          </Card>
        ))}
      </div>
      {courses.data && <Pagination page={page} size={SIZE} total={courses.data.total} onChange={setPage} />}
      {creating && <CourseForm onClose={() => setCreating(false)} onSaved={(c) => navigate(`/courses/${c.id}/manage`)} />}
    </AppLayout>
  )
}
