import cx from '../lib/cx'
import Icon from './Icon'

const TONES = { purple: 'b-p', green: 'b-g', amber: 'b-a', red: 'b-r', grey: 'b-n' }

// Pill-shaped status label, e.g. <Badge tone="green" icon="check">Current final</Badge>
export default function Badge({ tone = 'purple', icon, iconSize = 14, className, children, ...rest }) {
  return (
    <span className={cx('badge', TONES[tone], className)} {...rest}>
      {icon && <Icon name={icon} size={iconSize} />}
      {children}
    </span>
  )
}
