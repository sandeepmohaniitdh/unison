import { Link } from 'react-router'

// IIT Dharwad logo with "Unison / for IIT Dharwad". The logo file is
// frontend/public/assets/iitdh_logo.png (the path used in the Figma mockup).
export default function Brand({ to = '/' }) {
  return (
    <Link to={to} className="brand" aria-label="Unison for IIT Dharwad, home">
      <img src="/assets/iitdh_logo.png" alt="" />
      <div>
        <b>Unison</b>
        <span>for IIT Dharwad</span>
      </div>
    </Link>
  )
}
