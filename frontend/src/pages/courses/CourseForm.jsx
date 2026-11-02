import { useState } from 'react'
import { api, getAll } from '../../api/client'
import useApi from '../../api/useApi'
import { Button, Checkbox, ErrorMessage, Modal, TextArea, TextField } from '../../components'

// Create a course (teachers and admins) or edit its details. Teachers who create a course
// teach it; admins can pick teachers afterwards on the course's Members tab.
export default function CourseForm({ course, onSaved, onClose }) {
  const departments = useApi(() => getAll('/departments'), [])
  const [form, setForm] = useState({
    department_id: course?.department.id ?? '',
    code: course?.code ?? '',
    title: course?.title ?? '',
    term: course?.term ?? defaultTerm(),
    description: course?.description ?? '',
    join_requests_open: course?.join_requests_open ?? true,
  })
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const set = (key) => (e) => setForm((f) => ({ ...f, [key]: e.target.value }))

  async function save(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      const body = {
        department_id: Number(form.department_id),
        title: form.title.trim(),
        term: form.term.trim(),
        description: form.description.trim() || null,
        join_requests_open: form.join_requests_open,
      }
      const saved = course
        ? await api.patch(`/courses/${course.id}`, body)
        : await api.post('/courses', { ...body, code: form.code.trim().toUpperCase() })
      onSaved(saved)
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={course ? 'Edit course details' : 'Create a course'} onClose={onClose}>
      <form className="col gap16" onSubmit={save}>
        <div>
          <label className="lbl" htmlFor="course-dept">
            Department
          </label>
          <select id="course-dept" className="inp" style={{ width: '100%' }} value={form.department_id} onChange={set('department_id')} required>
            <option value="">Choose a department</option>
            {(departments.data ?? []).map((d) => (
              <option key={d.id} value={d.id}>
                {d.name}
              </option>
            ))}
          </select>
        </div>
        <div className="row gap16 stack-sm">
          <TextField
            className="grow"
            label="Course code"
            placeholder="CS301"
            value={form.code}
            onChange={set('code')}
            readOnly={Boolean(course)}
            required
          />
          <TextField className="grow" label="Term" placeholder="Jul-Nov 2026" value={form.term} onChange={set('term')} required />
        </div>
        <TextField label="Title" placeholder="Software Engineering" value={form.title} onChange={set('title')} required />
        <TextArea label="Description" placeholder="What the course covers" value={form.description} onChange={set('description')} />
        <Checkbox checked={form.join_requests_open} onChange={(v) => setForm((f) => ({ ...f, join_requests_open: v }))}>
          Students can ask to join from the catalogue
        </Checkbox>
        <ErrorMessage error={error} />
        <div className="row gap12" style={{ justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy || !form.department_id || !form.code || !form.title || !form.term}>
            {busy ? 'Saving…' : course ? 'Save changes' : 'Create course'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function defaultTerm(now = new Date()) {
  const year = now.getFullYear()
  return now.getMonth() >= 6 ? `Jul-Nov ${year}` : `Jan-May ${year}`
}
