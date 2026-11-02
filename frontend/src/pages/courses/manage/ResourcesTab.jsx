import { useRef, useState } from 'react'
import { api, getAll } from '../../../api/client'
import useApi from '../../../api/useApi'
import {
  Button,
  Card,
  Checkbox,
  Confirm,
  Empty,
  ErrorMessage,
  Loading,
  Modal,
  TextArea,
  TextField,
  Toggle,
  useToast,
} from '../../../components'
import { plural } from '../../../lib/format'
import { ResourceRow } from '../courseBits'

const ACCEPT = '.pdf,.doc,.docx,.ppt,.pptx,.xls,.xlsx,.txt,.png,.jpg,.jpeg,.zip'

// Course management, Resources: drafts until published. Several published together give
// one notification (and one bundled email).
export default function ResourcesTab({ courseId, archived }) {
  const toast = useToast()
  const resources = useApi(() => getAll(`/courses/${courseId}/resources`), [courseId])
  const [selected, setSelected] = useState([])
  const [notify, setNotify] = useState(true)
  const [adding, setAdding] = useState(null) // 'file' | 'link'
  const [editing, setEditing] = useState(null)
  const [deleting, setDeleting] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  const list = resources.data ?? []
  const drafts = list.filter((r) => r.status === 'draft')
  const published = list.filter((r) => r.status === 'published')

  async function publish() {
    setBusy(true)
    setError(null)
    try {
      await api.post(`/courses/${courseId}/resource-publications`, { resource_ids: selected, notify })
      toast(`${plural(selected.length, 'resource')} published${notify ? '. Students were notified.' : ''}`)
      setSelected([])
      resources.reload()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  async function remove() {
    setBusy(true)
    try {
      await api.delete(`/resources/${deleting.id}`)
      toast('Resource deleted')
      setDeleting(null)
      resources.reload()
    } catch (err) {
      setError(err)
      setDeleting(null)
    } finally {
      setBusy(false)
    }
  }

  const rowActions = (r) =>
    archived ? null : (
      <div className="row gap8">
        <Button variant="secondary" size="small" onClick={() => setEditing(r)}>
          Edit
        </Button>
        <Button variant="danger" size="small" onClick={() => setDeleting(r)}>
          Delete
        </Button>
      </div>
    )

  return (
    <div className="row gap24 start stack-sm">
      <div className="col gap24 grow" style={{ minWidth: 0 }}>
        <Card as="section" className="col" aria-labelledby="drafts-title">
          <div className="row between" style={{ marginBottom: 4 }}>
            <h3 id="drafts-title">Drafts</h3>
            <span className="small muted">Not visible to students</span>
          </div>
          {resources.loading && <Loading />}
          {resources.data && drafts.length === 0 && <Empty>No draft resources. Upload a file or add a link.</Empty>}
          {drafts.map((r) => (
            <div key={r.id} className="row gap12">
              <Checkbox
                checked={selected.includes(r.id)}
                onChange={(on) => setSelected((s) => (on ? [...s, r.id] : s.filter((x) => x !== r.id)))}
              >
                <span className="sr-only">Select {r.title}</span>
              </Checkbox>
              <div className="grow">
                <ResourceRow resource={r} actions={rowActions(r)} />
              </div>
            </div>
          ))}
          {drafts.length > 0 && (
            <div className="row gap16 wrap" style={{ marginTop: 12, justifyContent: 'flex-end' }}>
              <div className="row gap8 small">
                <Toggle checked={notify} onChange={setNotify} label="Notify students" />
                Notify students
              </div>
              <Button onClick={publish} disabled={busy || selected.length === 0 || archived}>
                {selected.length ? `Publish ${plural(selected.length, 'resource')}` : 'Select drafts to publish'}
              </Button>
            </div>
          )}
        </Card>
        <Card as="section" className="col" aria-labelledby="published-title">
          <div className="row between" style={{ marginBottom: 4 }}>
            <h3 id="published-title">Published</h3>
            <span className="small muted">{published.length} published</span>
          </div>
          {resources.data && published.length === 0 && <Empty>Nothing published yet.</Empty>}
          {published.map((r) => (
            <ResourceRow key={r.id} resource={r} actions={rowActions(r)} />
          ))}
        </Card>
        <ErrorMessage error={error ?? resources.error} />
      </div>
      <div className="col gap24 side-col" style={{ width: 400 }}>
        <Card as="section" className="col gap12">
          <h3>Add a resource</h3>
          <p className="small muted">New resources start as drafts. Files up to 25 MB: PDF, Word, PowerPoint, Excel, text, PNG, JPEG or ZIP.</p>
          <Button full icon="upload" onClick={() => setAdding('file')} disabled={archived}>
            Upload a file
          </Button>
          <Button full variant="secondary" icon="link" onClick={() => setAdding('link')} disabled={archived}>
            Add a link
          </Button>
        </Card>
      </div>
      {adding && (
        <AddResource
          courseId={courseId}
          kind={adding}
          onClose={() => setAdding(null)}
          onAdded={() => {
            setAdding(null)
            resources.reload()
          }}
        />
      )}
      {editing && (
        <EditResource
          resource={editing}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null)
            resources.reload()
          }}
        />
      )}
      {deleting && (
        <Confirm title="Delete this resource?" danger confirmLabel="Delete" busy={busy} onConfirm={remove} onCancel={() => setDeleting(null)}>
          "{deleting.title}" is removed for everyone.
        </Confirm>
      )}
    </div>
  )
}

function AddResource({ courseId, kind, onClose, onAdded }) {
  const toast = useToast()
  const [title, setTitle] = useState('')
  const [description, setDescription] = useState('')
  const [url, setUrl] = useState('')
  const [file, setFile] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const input = useRef(null)

  async function save(event) {
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (kind === 'file') {
        const form = new FormData()
        form.append('file', file)
        form.append('title', title.trim() || file.name)
        if (description.trim()) form.append('description', description.trim())
        await api.post(`/courses/${courseId}/resources/files`, form)
      } else {
        await api.post(`/courses/${courseId}/resources/links`, { title: title.trim(), description: description.trim() || null, url: url.trim() })
      }
      toast('Added as a draft')
      onAdded()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title={kind === 'file' ? 'Upload a file' : 'Add a link'} onClose={onClose}>
      <form className="col gap16" onSubmit={save}>
        {kind === 'file' ? (
          <div className="drop">
            <div className="grow">
              <b>{file ? file.name : 'Choose a file'}</b>
              <p className="small muted">{file ? `${Math.round(file.size / 1024)} KB` : 'Up to 25 MB'}</p>
            </div>
            <Button variant="secondary" onClick={() => input.current?.click()}>
              Browse
            </Button>
            <input
              ref={input}
              className="file-input"
              type="file"
              accept={ACCEPT}
              onChange={(e) => {
                const f = e.target.files[0]
                setFile(f ?? null)
                if (f && !title) setTitle(f.name.replace(/\.[^.]+$/, ''))
              }}
            />
          </div>
        ) : (
          <TextField label="Link" icon="link" type="url" placeholder="https://" value={url} onChange={(e) => setUrl(e.target.value)} required />
        )}
        <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Lecture 1 – Introduction" />
        <TextArea label="Description (optional)" value={description} onChange={(e) => setDescription(e.target.value)} />
        <ErrorMessage error={error} />
        <div className="row gap12" style={{ justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy || (kind === 'file' ? !file : !url || !title)}>
            {busy ? 'Saving…' : 'Add as draft'}
          </Button>
        </div>
      </form>
    </Modal>
  )
}

function EditResource({ resource, onClose, onSaved }) {
  const toast = useToast()
  const [title, setTitle] = useState(resource.title)
  const [description, setDescription] = useState(resource.description ?? '')
  const [url, setUrl] = useState(resource.url ?? '')
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)

  async function save(event) {
    event.preventDefault()
    setBusy(true)
    try {
      const body = { title: title.trim(), description: description.trim() || null }
      if (resource.kind === 'link') body.url = url.trim()
      await api.patch(`/resources/${resource.id}`, body)
      toast('Resource saved')
      onSaved()
    } catch (err) {
      setError(err)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal title="Edit resource" onClose={onClose}>
      <form className="col gap16" onSubmit={save}>
        <TextField label="Title" value={title} onChange={(e) => setTitle(e.target.value)} required />
        {resource.kind === 'link' && <TextField label="Link" type="url" value={url} onChange={(e) => setUrl(e.target.value)} />}
        <TextArea label="Description" value={description} onChange={(e) => setDescription(e.target.value)} />
        <ErrorMessage error={error} />
        <div className="row gap12" style={{ justifyContent: 'flex-end' }}>
          <Button variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" disabled={busy || !title}>
            Save
          </Button>
        </div>
      </form>
    </Modal>
  )
}
