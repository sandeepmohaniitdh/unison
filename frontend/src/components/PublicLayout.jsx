import Brand from './Brand'

// Layout of the public pages (Figma screens 01 Course catalogue and 04 Invitation):
// a white bar across the top with the brand, then the page.
//
//   <PublicLayout nav={<>...links and buttons...</>}>...</PublicLayout>
export default function PublicLayout({ nav, children }) {
  return (
    <div className="public">
      <header className="pubnav">
        <Brand />
        {nav}
      </header>
      {children}
    </div>
  )
}
