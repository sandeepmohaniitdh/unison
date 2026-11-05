import { Component } from 'react'

// If a page crashes, show a message instead of a blank screen.
export default class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { error: null }
  }

  static getDerivedStateFromError(error) {
    return { error }
  }

  componentDidCatch(error, info) {
    console.error('Page error', error, info.componentStack)
  }

  render() {
    if (!this.state.error) return this.props.children
    return (
      <div style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', padding: 16 }}>
        <div className="card col gap12" style={{ width: 480, maxWidth: '100%' }}>
          <h1 style={{ fontSize: 22 }}>Something went wrong on this page</h1>
          <p className="small muted">Reload the page to try again. If it keeps happening, tell the course team what you clicked.</p>
          <div className="row gap12">
            <button type="button" className="btn p" onClick={() => window.location.reload()}>
              Reload
            </button>
            <a className="btn o" href="/">
              Go home
            </a>
          </div>
        </div>
      </div>
    )
  }
}
