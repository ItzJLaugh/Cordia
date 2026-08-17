import '@xyflow/react/dist/style.css'

import SignOutControl from './SignOutControl.js'
import WorkspaceView from './WorkspaceView.jsx'
import { routeFromSearch } from './workspace-view.js'

export default function App() {
  const route = routeFromSearch(window.location.search)
  if (route.phase === 'missing') {
    return (
      <main className="page-notice">
        <h1>Choose a workspace</h1>
        <p>This link does not identify a Cordia workspace.</p>
        <a href="/interfaces.html">Open your saved workspaces</a>
      </main>
    )
  }

  return (
    <div className="shell">
      <header className="topbar">
        <a className="brand" href="/" aria-label="Cordia home">Cordia</a>
        <span className="workspace-label">Workspace</span>
        <nav className="view-navigation" aria-label="Workspace views">
          <a href={route.workspaceHref} aria-current={route.view === 'workspace' ? 'page' : undefined}>Workspace</a>
          <a href={route.alidoraHref} aria-current={route.view === 'alidora' ? 'page' : undefined}>Alidora <span>Advanced</span></a>
        </nav>
        <SignOutControl />
      </header>
      <WorkspaceView route={route} />
    </div>
  )
}
