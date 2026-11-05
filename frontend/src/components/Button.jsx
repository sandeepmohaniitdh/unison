import { Link } from 'react-router'
import cx from '../lib/cx'
import Icon from './Icon'

const VARIANTS = { primary: 'p', secondary: 'o', tint: 'g', danger: 'd' }

// Buttons from the design: primary (purple), secondary (outlined), tint (soft purple)
// and danger (outlined red), in normal or small size. Pass `to` for a link that looks
// like a button, otherwise it is a real <button>.
export default function Button({
  variant = 'primary',
  size,
  full = false,
  icon,
  iconColor,
  to,
  type = 'button',
  className,
  children,
  ...rest
}) {
  const classes = cx('btn', VARIANTS[variant], size === 'small' && 'sm', full && 'full', className)
  const content = (
    <>
      {icon && <Icon name={icon} size={size === 'small' ? 14 : 16} color={iconColor} />}
      {children}
    </>
  )
  if (to) {
    return (
      <Link to={to} className={classes} {...rest}>
        {content}
      </Link>
    )
  }
  return (
    <button type={type} className={classes} {...rest}>
      {content}
    </button>
  )
}
