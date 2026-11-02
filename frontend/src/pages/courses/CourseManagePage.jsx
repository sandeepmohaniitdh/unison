import { useState } from 'react'
import { useParams, useSearchParams } from 'react-router'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import { Alert, Badge, Button, Card, Empty, Loading, PageError, Tabs } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatDeadline } from '../../lib/datetime'
import { formatTerm } from '../../lib/format'
import { typeBadge } from './courseBits'
import AssignmentEditor from './manage/AssignmentEditor'
import MembersTab from './manage/MembersTab'
import { DetailsTab, NotificationsTab } from './manage/OtherTabs'
import ResourcesTab from './manage/ResourcesTab'
import { EmailRulesCard, InviteStudentsCard, TeamsLockCard } from './manage/SideCards'
import TeamsTab from './manage/TeamsTab'

const TABS = [
  { id: 'details', label: 'Details' },
  { id: 'resources', label: 'Resources' },
  { id: 'assignments', label: 'Assignments' },
  { id: 'members', label: 'Members' },
  { id: 'teams', label: 'Teams' },
  { id: 'notifications', label: 'Notifications' },
]

// Figma 08: course management for the course's teachers and admins.
export default function CourseManagePage() {
  const { courseId } = useParams()
  const { user } = useAuth()
  const [params, setParams] = useSearchParams()
  const tab = { requests: 'members' }[params.get('tab')] ?? params.get('tab') ?? 'assignments'
  const course = useApi(() => api.get(`/courses/${courseId}`), [courseId])
  const assignments = useApi(() => getAll(`/courses/${courseId}/assignments`), [courseId])
  const c = course.data

  function setTab(id) {
    setParams({ tab: id }, { replace: true })
  }

  const allowed = c && (c.my_status === 'teacher' || user.role === 'admin')
  return (
    <AppLayout
      title={c ? `Manage ${c.code} · ${c.title}` : 'Manage course'}
      subtitle={c ? `${c.department.name} · ${formatTerm(c.term)}` : ' '}
      activeNav="/courses"
      headerActions={
        c && (
          <Button variant="secondary" size="small" to={`/courses/${c.id}`}>
            View as student
          </Button>
        )
      }
    >
      {course.loading && !c && <Loading />}
      {course.error && <PageError error={course.error} />}
      {c && !allowed && <PageError error={{ message: 'Only the teachers of this course can manage it.' }} />}
      {c && allowed && (
        <>
          <Tabs label="Course management" tabs={TABS} value={tab} onChange={setTab} />
          {c.archived && <Alert tone="info">This course is archived. Everything is read-only.</Alert>}
          <div role="tabpanel" aria-labelledby={`tab-${tab}`} className="col gap24">
            {tab === 'details' && <DetailsTab course={c} onChanged={(saved) => course.setData(saved)} />}
            {tab === 'resources' && <ResourcesTab courseId={c.id} archived={c.archived} />}
            {tab === 'assignments' && (
              <AssignmentsTab
                course={c}
                assignments={assignments}
                startNew={params.get('new') === '1'}
                onShowRules={() => setTab('notifications')}
              />
            )}
            {tab === 'members' && <MembersTab course={c} archived={c.archived} />}
            {tab === 'teams' &&
              (assignments.data ? (
                <TeamsTab assignments={assignments.data} archived={c.archived} onAssignmentChanged={() => assignments.reload()} />
              ) : (
                <Loading />
              ))}
            {tab === 'notifications' && <NotificationsTab courseId={c.id} archived={c.archived} />}
          </div>
        </>
      )}
    </AppLayout>
  )
}

function AssignmentsTab({ course, assignments, startNew, onShowRules }) {
  const [editingId, setEditingId] = useState(startNew ? null : undefined)
  const list = assignments.data ?? []
  // By default edit the first draft, or start a new assignment.
  const chosenId = editingId === undefined ? (list.find((a) => a.status === 'draft')?.id ?? null) : editingId
  const detail = useApi(() => (chosenId ? api.get(`/assignments/${chosenId}`) : Promise.resolve(null)), [chosenId])

  function saved(a) {
    assignments.reload()
    setEditingId(a ? a.id : null)
    if (a) detail.setData(a)
  }

  return (
    <div className="row gap24 start stack-sm">
      <div className="col gap24 grow" style={{ minWidth: 0 }}>
        {chosenId && detail.loading ? (
          <Loading />
        ) : (
          <AssignmentEditor
            key={chosenId ?? 'new'}
            courseId={course.id}
            assignment={chosenId ? detail.data : null}
            archived={course.archived}
            onSaved={saved}
            onCancel={chosenId ? () => setEditingId(null) : null}
          />
        )}
        <Card as="section" className="col gap12" aria-labelledby="all-assignments">
          <div className="row between">
            <h3 id="all-assignments">All assignments</h3>
            <Button variant="secondary" size="small" icon="plus" onClick={() => setEditingId(null)} disabled={course.archived}>
              New assignment
            </Button>
          </div>
          {assignments.loading && <Loading />}
          {assignments.data && list.length === 0 && <Empty>No assignments yet. Fill in the form above.</Empty>}
          {list.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Assignment</th>
                    <th scope="col">Type</th>
                    <th scope="col">Deadline</th>
                    <th scope="col">Status</th>
                    <th scope="col">
                      <span className="sr-only">Actions</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((a) => (
                    <tr key={a.id} style={a.id === chosenId ? { background: 'var(--color-surface-tint)' } : undefined}>
                      <td>
                        <b>{a.title}</b>
                        {a.teams_locked && <p className="tiny muted">Teams locked</p>}
                      </td>
                      <td>{typeBadge(a)}</td>
                      <td>{formatDeadline(a.due_at)}</td>
                      <td>
                        <Badge tone={a.status === 'draft' ? 'grey' : a.status === 'closed' ? 'amber' : 'green'}>
                          {a.status === 'draft' ? 'Draft' : a.status === 'closed' ? 'Closed' : 'Published'}
                        </Badge>
                      </td>
                      <td>
                        <div className="row gap8" style={{ justifyContent: 'flex-end' }}>
                          <Button variant="secondary" size="small" onClick={() => setEditingId(a.id)}>
                            Edit
                          </Button>
                          {a.status !== 'draft' && (
                            <Button variant="tint" size="small" to={`/assignments/${a.id}/review`}>
                              Review
                            </Button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
      <div className="col gap24 side-col" style={{ width: 400 }}>
        <InviteStudentsCard courseId={course.id} archived={course.archived} />
        <EmailRulesCard courseId={course.id} archived={course.archived} onShowAll={onShowRules} />
        <TeamsLockCard
          assignment={chosenId ? detail.data : null}
          archived={course.archived}
          onChanged={(a) => {
            detail.setData(a)
            assignments.reload()
          }}
        />
      </div>
    </div>
  )
}
