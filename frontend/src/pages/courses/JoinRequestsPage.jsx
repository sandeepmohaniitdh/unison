import { useState } from 'react'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import { Avatar, Button, Card, Empty, ErrorMessage, Loading, PageError, useToast } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { formatShort } from '../../lib/datetime'
import { plural } from '../../lib/format'

// "Join requests" in the teacher's sidebar (Figma 07 shows the first three): every
// pending request in the courses the teacher teaches.
export default function JoinRequestsPage() {
  const { refreshJoinRequests } = useAuth()
  const toast = useToast()
  const [busy, setBusy] = useState(null)
  const [error, setError] = useState(null)
  const requests = useApi(async () => {
    const courses = (await getAll('/users/me/courses')).filter((c) => c.my_status === 'teacher' && !c.archived)
    const lists = await Promise.all(
      courses.map((c) => getAll(`/courses/${c.id}/join-requests`).then((items) => items.map((r) => ({ ...r, course: c })))),
    )
    return lists.flat().sort((a, b) => (a.requested_at ?? '').localeCompare(b.requested_at ?? ''))
  }, [])

  async function decide(r, status) {
    setBusy(r.id)
    setError(null)
    try {
      await api.patch(`/courses/${r.course.id}/join-requests/${r.id}`, { status })
      toast(status === 'approved' ? `${r.user.name} is now enrolled in ${r.course.code}` : 'Join request rejected')
      requests.setData((list) => list.filter((x) => x.id !== r.id))
      refreshJoinRequests()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(null)
    }
  }

  const list = requests.data ?? []
  return (
    <AppLayout
      title="Join requests"
      subtitle={requests.data ? `${plural(list.length, 'student')} waiting to join your courses` : ' '}
    >
      {requests.loading && <Loading />}
      {requests.error && <PageError error={requests.error} />}
      {requests.data && (
        <Card as="section" className="col gap12">
          <div className="row between">
            <h3>Waiting for you</h3>
            <span className="small muted">The student is notified either way</span>
          </div>
          <ErrorMessage error={error} />
          {list.length === 0 && <Empty>No join requests are waiting.</Empty>}
          {list.length > 0 && (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th scope="col">Student</th>
                    <th scope="col">Email</th>
                    <th scope="col">Course</th>
                    <th scope="col">Requested</th>
                    <th scope="col">
                      <span className="sr-only">Decision</span>
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {list.map((r) => (
                    <tr key={r.id}>
                      <td>
                        <div className="row gap8">
                          <Avatar name={r.user.name} size="small" />
                          <b>{r.user.name}</b>
                        </div>
                      </td>
                      <td className="muted">{r.email}</td>
                      <td>
                        {r.course.code} {r.course.title}
                      </td>
                      <td className="muted">{r.requested_at ? formatShort(r.requested_at) : ''}</td>
                      <td>
                        <div className="row gap8" style={{ justifyContent: 'flex-end' }}>
                          <Button variant="secondary" size="small" disabled={busy === r.id} onClick={() => decide(r, 'rejected')}>
                            Reject
                          </Button>
                          <Button size="small" disabled={busy === r.id} onClick={() => decide(r, 'approved')}>
                            Approve
                          </Button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      )}
    </AppLayout>
  )
}
