import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react'
import cx from '../lib/cx'
import Card from './Card'
import Icon from './Icon'

// Messages, empty states, loading and dialogs, all in the design's colours.

// <Alert tone="error">The email or password is wrong.</Alert>
export function Alert({ tone = 'error', children, className }) {
  if (!children) return null
  const icon = { error: 'clock', success: 'check', info: 'clock', note: 'sparkle' }[tone]
  return (
    <div className={cx('alert', tone, className)} role={tone === 'error' ? 'alert' : 'status'}>
      <Icon name={icon} size={16} />
      <div>{children}</div>
    </div>
  )
}

// The error of an API call, with the request id for support.
export function ErrorMessage({ error, className }) {
  if (!error) return null
  return (
    <Alert tone="error" className={className}>
      {error.message || 'Something went wrong.'}
      {error.status >= 500 && error.requestId && <span className="tiny"> (request {error.requestId})</span>}
    </Alert>
  )
}

export function Empty({ children }) {
  return <p className="empty">{children}</p>
}

export function Loading({ label = 'Loading…' }) {
  return (
    <div className="loading" role="status" aria-live="polite">
      {label}
    </div>
  )
}

// Shown in place of a page when its data could not be loaded.
export function PageError({ error }) {
  const notFound = error?.status === 404
  return (
    <Card className="col gap8">
      <h3>{notFound ? 'Not found' : 'Could not load this page'}</h3>
      <p className="small muted">
        {notFound ? 'It does not exist, or you do not have access to it.' : error?.message}
      </p>
    </Card>
  )
}

// Pop-up dialog. Escape and the backdrop close it; focus moves into it and back.
export function Modal({ title, onClose, wide = false, children, footer }) {
  const box = useRef(null)
  useEffect(() => {
    const previous = document.activeElement
    const first = box.current?.querySelector('input, select, textarea, button:not([data-close])')
    ;(first ?? box.current)?.focus()
    function onKey(event) {
      if (event.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('keydown', onKey)
      previous?.focus?.()
    }
  }, [onClose])
  return (
    <div className="modal-backdrop" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div
        ref={box}
        className={cx('card modal col gap16', wide && 'wide')}
        role="dialog"
        aria-modal="true"
        aria-labelledby="modal-title"
        tabIndex={-1}
      >
        <div className="row between">
          <h3 id="modal-title">{title}</h3>
          <button type="button" className="btn o sm" onClick={onClose} data-close aria-label="Close">
            Close
          </button>
        </div>
        {children}
        {footer && (
          <div className="row gap12" style={{ justifyContent: 'flex-end' }}>
            {footer}
          </div>
        )}
      </div>
    </div>
  )
}

// "Are you sure?" dialog.
export function Confirm({ title, children, confirmLabel = 'Confirm', danger = false, busy, onConfirm, onCancel }) {
  return (
    <Modal
      title={title}
      onClose={onCancel}
      footer={
        <>
          <button type="button" className="btn o" onClick={onCancel}>
            Cancel
          </button>
          <button type="button" className={cx('btn', danger ? 'd' : 'p')} onClick={onConfirm} disabled={busy}>
            {busy ? 'Please wait…' : confirmLabel}
          </button>
        </>
      }
    >
      <div className="small muted">{children}</div>
    </Modal>
  )
}

// Short notices in the corner: const toast = useToast(); toast('Saved')
const ToastContext = createContext(() => {})

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([])
  const show = useCallback((text, tone = 'ok') => {
    const id = Math.random()
    setToasts((list) => [...list, { id, text, tone }])
    setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), 4000)
  }, [])
  return (
    <ToastContext.Provider value={show}>
      {children}
      <div className="toasts" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={cx('toast', t.tone === 'error' && 'error')}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  )
}

export function useToast() {
  return useContext(ToastContext)
}
