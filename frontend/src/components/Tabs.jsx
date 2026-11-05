import { useRef } from 'react'
import cx from '../lib/cx'

// Underlined tabs ("Overview, Resources, Assignments, Members").
// tabs: [{ id, label }]. Arrow keys move between tabs, as screen-reader users expect.
// Render each panel with role="tabpanel" and aria-labelledby={`tab-${id}`}.
export default function Tabs({ tabs, value, onChange, label, className, style }) {
  const refs = useRef({})

  function onKeyDown(event, index) {
    const step = { ArrowRight: 1, ArrowLeft: -1 }[event.key]
    if (!step) return
    event.preventDefault()
    const next = tabs[(index + step + tabs.length) % tabs.length]
    onChange?.(next.id)
    refs.current[next.id]?.focus()
  }

  return (
    <div className={cx('tabs', className)} role="tablist" aria-label={label} style={style}>
      {tabs.map((tab, index) => {
        const selected = tab.id === value
        return (
          <button
            key={tab.id}
            ref={(el) => {
              refs.current[tab.id] = el
            }}
            id={`tab-${tab.id}`}
            type="button"
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            className={cx('tab', selected && 'on')}
            onClick={() => onChange?.(tab.id)}
            onKeyDown={(event) => onKeyDown(event, index)}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
