import { useState } from 'react'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { useAuth } from '../../auth/AuthContext'
import { Button, Card, Empty, Loading, PageError, Pagination, Tabs, useToast } from '../../components'
import AppLayout from '../../layouts/AppLayout'
import { plural } from '../../lib/format'
import NotificationList from './NotificationList'

const SIZE = 20

// "Notifications" from the sidebar and the bell (not drawn in Figma; rows as in Figma 05).
export default function NotificationsPage() {
  const { unread, refreshCounts } = useAuth()
  const toast = useToast()
  const [filter, setFilter] = useState('all')
  const [page, setPage] = useState(1)
  const list = useApi(() => api.get('/notifications', { unread_only: filter === 'unread' || undefined, page, size: SIZE }), [filter, page])
  const courses = useApi(() => getAll('/users/me/courses'), [])
  const codes = Object.fromEntries((courses.data ?? []).map((c) => [c.id, c.code]))

  async function markAll() {
    const res = await api.patch('/notifications', { read: true })
    toast(res.marked ? `${plural(res.marked, 'notification')} marked as read` : 'Nothing new to mark')
    list.reload()
    refreshCounts()
  }

  return (
    <AppLayout
      title="Notifications"
      subtitle={unread ? `${unread} unread` : 'You are up to date'}
      headerActions={
        <Button variant="secondary" size="small" onClick={markAll} disabled={!unread}>
          Mark all as read
        </Button>
      }
    >
      <Tabs
        label="Which notifications"
        tabs={[
          { id: 'all', label: 'All' },
          { id: 'unread', label: 'Unread' },
        ]}
        value={filter}
        onChange={(v) => {
          setFilter(v)
          setPage(1)
        }}
      />
      <Card as="section" className="col" role="tabpanel" aria-labelledby={`tab-${filter}`}>
        {list.loading && !list.data && <Loading />}
        {list.error && <PageError error={list.error} />}
        {list.data?.items.length === 0 && <Empty>{filter === 'unread' ? 'No unread notifications.' : 'No notifications yet.'}</Empty>}
        {list.data && (
          <NotificationList
            items={list.data.items}
            courseCodes={codes}
            onChange={(n) => list.setData((d) => ({ ...d, items: d.items.map((x) => (x.id === n.id ? n : x)) }))}
          />
        )}
      </Card>
      {list.data && <Pagination page={page} size={SIZE} total={list.data.total} onChange={setPage} />}
      <p className="tiny muted">In-app notifications always appear. Choose which ones also email you on your profile page.</p>
    </AppLayout>
  )
}
