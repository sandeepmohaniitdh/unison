import { useId } from 'react'
import cx from '../lib/cx'
import Icon from './Icon'

// Form controls styled like the design's input boxes. Each one is a real, labelled
// HTML control. Give `label` for a visible label; otherwise pass `aria-label`.

function FieldLabel({ htmlFor, children }) {
  return (
    <label className="lbl" htmlFor={htmlFor}>
      {children}
    </label>
  )
}

// Text input, optionally with an icon on the left: search, email, password...
export function TextField({ label, icon, iconSize = 16, id, className, boxClassName, boxStyle, ...inputProps }) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <div className={className}>
      {label && <FieldLabel htmlFor={inputId}>{label}</FieldLabel>}
      <div className={cx('inp', inputProps.readOnly && 'f', boxClassName)} style={boxStyle}>
        {icon && <Icon name={icon} size={iconSize} />}
        <input id={inputId} {...inputProps} />
      </div>
    </div>
  )
}

export function TextArea({ label, id, className, boxClassName, boxStyle, ...textareaProps }) {
  const autoId = useId()
  const inputId = id ?? autoId
  return (
    <div className={className}>
      {label && <FieldLabel htmlFor={inputId}>{label}</FieldLabel>}
      <div className={cx('inp', 'ta', boxClassName)} style={boxStyle}>
        <textarea id={inputId} {...textareaProps} />
      </div>
    </div>
  )
}

// Drop-down shown as "Department: All ⌄" like the design. The native <select> sits on
// top, invisible, so mouse, keyboard and screen readers work as usual.
// options: [{ value, label }]. `filled` uses the dark text colour (e.g. role pickers).
export function Select({
  label,
  prefix,
  options,
  value,
  onChange,
  filled = false,
  chevronSize = 16,
  id,
  className,
  style,
  boxClassName,
  boxStyle,
  ...selectProps
}) {
  const autoId = useId()
  const selectId = id ?? autoId
  const selected = options.find((o) => String(o.value) === String(value)) ?? options[0]
  const shown = selected ? selected.label : ''
  return (
    <div className={className} style={style}>
      {label && <FieldLabel htmlFor={selectId}>{label}</FieldLabel>}
      <div className={cx('inp', 'select', filled && 'f', boxClassName)} style={boxStyle}>
        <span>{prefix ? `${prefix}: ${shown}` : shown}</span>
        <Icon name="chevronDown" size={chevronSize} />
        <select id={selectId} value={value} onChange={(e) => onChange?.(e.target.value)} {...selectProps}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  )
}

// Small boxed number, e.g. team size "2 to 4", rubric scores, adjustment "0%".
export function NumberBox({ value, onChange, suffix, width, className, ...inputProps }) {
  const text = value ?? ''
  return (
    <div className={cx('num', className)} style={width ? { width } : undefined}>
      <input
        inputMode="decimal"
        value={text}
        onChange={(e) => onChange?.(e.target.value)}
        style={{ width: `${Math.max(String(text).length, 1) + (suffix ? 0 : 0.5)}ch` }}
        {...inputProps}
      />
      {suffix}
    </div>
  )
}

// On/off switch. Always give a label (visible text next to it is not enough for screen
// readers unless you pass it here too).
export function Toggle({ checked, onChange, label, disabled }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={label}
      disabled={disabled}
      className={cx('tog', !checked && 'off')}
      onClick={() => onChange?.(!checked)}
    >
      <i />
    </button>
  )
}

export function Checkbox({ checked, onChange, children, className }) {
  return (
    <label className={cx('check', className)}>
      <input type="checkbox" className="sr-only" checked={checked} onChange={(e) => onChange?.(e.target.checked)} />
      <span className={cx('cb', !checked && 'off')} aria-hidden="true">
        <Icon name="check" size={12} color="#fff" strokeWidth={3} />
      </span>
      {children}
    </label>
  )
}
