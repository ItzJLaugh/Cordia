import { useEffect, useState } from 'react'
import { ReactFlow, Background, Controls } from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { api } from './api.js'

// Step 6 scope, deliberately small: authenticate with the same session as
// the rest of the site, load the framework and the interface list, and
// prove the canvas mounts. The graph itself is Step 7; interaction is
// Step 9. Signed-out and Limited-mode states are real states here, not
// errors — the surface must degrade the way the rest of Cordia does.

const PLACEHOLDER_NODES = [
  {
    id: 'placeholder',
    position: { x: 40, y: 40 },
    data: { label: 'Your workspace canvas — agents land here in the next step' },
  },
]

export default function App() {
  const [state, setState] = useState({ phase: 'loading' })

  useEffect(() => {
    let alive = true
    Promise.all([api('/dashboard/framework'), api('/dashboard/interface')])
      .then(([fw, ifaces]) => {
        if (!alive) return
        if (fw.code === 401 || ifaces.code === 401) {
          setState({ phase: 'signed-out' })
        } else if (fw.code === 503 || ifaces.code === 503) {
          setState({ phase: 'offline' })
        } else if (fw.code === 200 && ifaces.code === 200
                   && fw.data && typeof fw.data.framework === 'object'
                   && fw.data.framework !== null) {
          // The shape guard matters as much as the status: a 200 whose body
          // did not parse resolves to data {}, and rendering from it would
          // blank the page with a TypeError instead of showing a state.
          setState({
            phase: 'ready',
            framework: fw.data.framework,
            llm: fw.data.llm,
            interfaces: (ifaces.data && ifaces.data.interfaces) || [],
          })
        } else {
          setState({ phase: 'error' })
        }
      })
      .catch(() => {
        // Transport failure — server down, offline, blocked. fetch rejects
        // rather than returning a status, and without this branch the UI
        // would sit on "Loading…" forever.
        if (alive) setState({ phase: 'offline' })
      })
    return () => { alive = false }
  }, [])

  if (state.phase === 'loading') {
    return <div className="notice">Loading your workspace…</div>
  }
  if (state.phase === 'signed-out') {
    return (
      <div className="notice">
        Sign in to open your dashboard.{' '}
        <a href="/">Go to the Cordia home page</a> to sign in first.
      </div>
    )
  }
  if (state.phase === 'offline') {
    return (
      <div className="notice">
        The dashboard is unavailable right now. Nothing else is affected.
      </div>
    )
  }
  if (state.phase === 'error') {
    return (
      <div className="notice">
        Something unexpected came back from the server. Refresh to try again.
      </div>
    )
  }

  const { framework, llm, interfaces } = state
  const limited = llm && llm.live === false
  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Cordia — Dashboard</span>
        <span className="shaped">{framework.reason}</span>
        {limited && <span className="limited">Limited mode</span>}
      </header>
      {limited && (
        // The note renders as visible text, the same way cordia-surveyor.js
        // and interface.html surface this exact string — it carries a
        // data-provenance warning, and hover-only delivery hid it from
        // keyboard users.
        <div className="limited-note">{llm.note}</div>
      )}
      <main className="split">
        <aside className="panel">
          <h2>Your setup</h2>
          <dl className="kv">
            <div><dt>Leading surface</dt><dd>{framework.lead_surface}</dd></div>
            <div><dt>Diagram style</dt><dd>{framework.diagram_forward.replace(/_/g, ' ')}</dd></div>
            <div><dt>Approvals</dt><dd>{framework.approval_density.replace(/_/g, ' ')}</dd></div>
            <div><dt>Detail level</dt><dd>{framework.node_density}</dd></div>
          </dl>
          <h2>Workspaces</h2>
          <p className="count">
            {interfaces.length === 0
              ? 'None yet — the canvas will help you build your first.'
              : `${interfaces.length} saved`}
          </p>
        </aside>
        <section className="canvas">
          <ReactFlow nodes={PLACEHOLDER_NODES} edges={[]} fitView>
            <Background />
            <Controls />
          </ReactFlow>
        </section>
      </main>
    </div>
  )
}
