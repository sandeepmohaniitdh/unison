import { useEffect, useState } from 'react'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { Badge, Button, Card, Empty, ErrorMessage, Icon, Loading, Pagination, Select, TextField } from '../../components'
import PublicPage from '../../layouts/PublicNav'
import { formatTerm, plural } from '../../lib/format'

const PAGE_SIZE = 6

// The current term, as the backend writes it: "Jul-Nov 2026" or "Jan-May 2027".
function currentTerm(now = new Date()) {
  const year = now.getFullYear()
  return now.getMonth() >= 6 ? `Jul-Nov ${year}` : `Jan-May ${year}`
}

// Figma 01: the public course catalogue.
export default function CataloguePage() {
  const [query, setQuery] = useState('')
  const [search, setSearch] = useState('')
  const [department, setDepartment] = useState('')
  const [term, setTerm] = useState(currentTerm())
  const [page, setPage] = useState(1)

  // Search after the user stops typing for a moment.
  useEffect(() => {
    const timer = setTimeout(() => {
      setSearch(query.trim())
      setPage(1)
    }, 300)
    return () => clearTimeout(timer)
  }, [query])

  const departments = useApi(() => getAll('/departments'), [])
  const courses = useApi(
    () => api.get('/courses', { q: search, department_id: department, term, page, size: PAGE_SIZE }),
    [search, department, term, page],
  )

  const thisTerm = currentTerm()
  const terms = [
    { value: thisTerm, label: formatTerm(thisTerm) },
    { value: '', label: 'All' },
  ]
  const departmentOptions = [
    { value: '', label: 'All' },
    ...(departments.data ?? []).map((d) => ({ value: d.id, label: d.name })),
  ]

  return (
    <PublicPage>
      <main id="main" className="col gap24 page-pad">
        <div>
          <div className="eyebrow">Indian Institute of Technology Dharwad</div>
          <h1 style={{ marginTop: 6 }}>Course catalogue</h1>
          <p className="muted" style={{ marginTop: 6 }}>
            Browse this term's courses. Sign in with your @iitdh.ac.in account to request to join.
          </p>
        </div>
        <div className="row gap12 wrap" role="search">
          <TextField
            className="grow"
            icon="search"
            iconSize={18}
            type="search"
            placeholder="Search by code, title or teacher"
            aria-label="Search courses by code, title or teacher"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <Select
            prefix="Department"
            aria-label="Department"
            options={departmentOptions}
            value={department}
            onChange={(v) => {
              setDepartment(v)
              setPage(1)
            }}
            boxStyle={{ width: 280 }}
          />
          <Select
            prefix="Term"
            aria-label="Term"
            options={terms}
            value={term}
            onChange={(v) => {
              setTerm(v)
              setPage(1)
            }}
            boxStyle={{ width: 200 }}
          />
        </div>

        <ErrorMessage error={courses.error} />
        {courses.loading && !courses.data && <Loading />}
        {courses.data && courses.data.items.length === 0 && <Empty>No courses match your search.</Empty>}
        <div className="row wrap gap24 start">
          {courses.data?.items.map((course) => (
            <CourseCard key={course.id} course={course} />
          ))}
        </div>
        {courses.data && (
          <Pagination page={page} size={PAGE_SIZE} total={courses.data.total} onChange={setPage} />
        )}
      </main>
    </PublicPage>
  )
}

function CourseCard({ course }) {
  const teachers = course.teachers.map((t) => t.name).join(', ') || 'No teacher yet'
  return (
    <Card as="article" className="col gap12" style={{ width: 400, maxWidth: '100%' }}>
      <div className="row between">
        <Badge tone="purple">{course.code}</Badge>
        {course.archived ? (
          <Badge tone="grey">Archived</Badge>
        ) : course.join_requests_open ? (
          <Badge tone="green">Join requests open</Badge>
        ) : (
          <Badge tone="grey">Invite only</Badge>
        )}
      </div>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 600 }}>{course.title}</h2>
        <p className="muted small">{course.department.name}</p>
      </div>
      <div className="row gap8 muted small">
        <Icon name="user" size={15} />
        <span>
          {teachers} &nbsp;·&nbsp; {formatTerm(course.term)}
        </span>
      </div>
      <div className="row between" style={{ marginTop: 4 }}>
        <span className="small muted">
          {plural(course.assignment_count ?? 0, 'assignment')} · {plural(course.resource_count ?? 0, 'resource')}
        </span>
        <Button variant="secondary" size="small" to={`/courses/${course.id}`} aria-label={`View course ${course.code}`}>
          View course
        </Button>
      </div>
    </Card>
  )
}
