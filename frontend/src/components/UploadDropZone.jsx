import { useRef, useState } from 'react'
import cx from '../lib/cx'
import Button from './Button'
import Icon from './Icon'

// Dashed upload area from the team workspace. Files can be dropped on it or picked with
// the button; `onFiles` receives an array of File objects.
export default function UploadDropZone({
  title = 'Upload a new draft',
  hint = "Drag files here or browse. Drafts don't notify the teacher.",
  buttonLabel = 'Upload draft',
  accept,
  multiple = true,
  disabled = false,
  onFiles,
}) {
  const input = useRef(null)
  const [dragging, setDragging] = useState(false)

  function handleDrop(event) {
    event.preventDefault()
    setDragging(false)
    if (!disabled && event.dataTransfer.files.length) onFiles?.([...event.dataTransfer.files])
  }

  return (
    <div
      className={cx('drop', dragging && 'dragging')}
      onDragOver={(event) => {
        event.preventDefault()
        setDragging(true)
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={handleDrop}
    >
      <Icon name="upload" size={28} color="var(--color-primary)" />
      <div className="grow">
        <b>{title}</b>
        <p className="small muted">{hint}</p>
      </div>
      <Button onClick={() => input.current?.click()} disabled={disabled}>
        {buttonLabel}
      </Button>
      <input
        ref={input}
        type="file"
        hidden
        accept={accept}
        multiple={multiple}
        onChange={(event) => {
          if (event.target.files.length) onFiles?.([...event.target.files])
          event.target.value = ''
        }}
      />
    </div>
  )
}
