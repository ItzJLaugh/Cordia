import { useEffect, useRef, useState } from 'react'
import '@xyflow/react/dist/style.css'
import { api } from './api.js'
import ChatPanel from './ChatPanel.jsx'
import DefinitionGraph from './DefinitionGraph.jsx'

// The dashboard shell: authenticate with the same session as the rest of
// the site, load the framework and the interface list, and render the
// selected interface as a read-only graph (interaction is Step 9).
// Signed-out and Limited-mode states are real states here, not errors —
// the surface must degrade the way the rest of Cordia does.

export default function App() {
  const [state, setState] = useState({ phase: 'loading' })
  const [selected, setSelected] = useState(null)   // { id, name, definition } | null
  const [opening, setOpening] = useState(null)     // id being fetched, for the pressed state
  const [openNote, setOpenNote] = useState(null)   // a failed open says so, briefly
  const openSeq = useRef(0)                        // last click wins, not last response

  function openInterface(id) {
    const seq = ++openSeq.current
    setOpening(id)
    setOpenNote(null)
    api('/dashboard/interface?id=' + encodeURIComponent(id)).then((r) => {
      // A response from a superseded click must not overwrite the newer
      // selection — without this, a slow fetch for A lands after a fast
      // fetch for B and the canvas settles on the wrong workspace.
      if (seq !== openSeq.current) return
      setOpening(null)
      if (r.code === 200 && r.data && r.data.interface) {
        setSelected(r.data.interface)
      } else {
        // A 404 (deleted elsewhere) or a bad response keeps the previous
        // selection — the canvas never blanks over a stale click — but
        // the select reverting with no explanation read as the click
        // being silently swallowed.
        setOpenNote('That workspace could not be opened just now.')
      }
    }).catch(() => {
      if (seq !== openSeq.current) return
      setOpening(null)
      setOpenNote('That workspace could not be opened just now.')
    })
  }

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
        <aside className="panel chat-panel">
          <div className="workspace-row">
            <label className="ws-label" htmlFor="ws-select">Workspace</label>
            <select
              id="ws-select"
              // While a fetch is in flight the visible choice is the one
              // the person just made — snapping back to the old value
              // mid-flight read as the click being discarded. On failure
              // `opening` clears and the select reverts to what the
              // canvas still shows, with the note below saying why.
              // Never disabled mid-flight: disabling blurred the select
              // to <body> and broke arrowing through the list; openSeq
              // already makes overlapping opens safe (last click wins).
              value={opening || (selected ? selected.id : '')}
              onChange={(e) => e.target.value && openInterface(e.target.value)}
            >
              <option value="">
                {interfaces.length === 0
                  ? 'None yet — chat to start one'
                  : 'Pick a workspace…'}
              </option>
              {interfaces.map((iface) => (
                <option key={iface.id} value={iface.id}>{iface.name}</option>
              ))}
            </select>
          </div>
          {/* Permanently rendered so the live region exists before its
              content arrives — a region mounted together with its text is
              announced unreliably. Empty, it takes no space (CSS
              :not(:empty)); filled, it reads as the amber note. Without
              this, the failed-open explanation was visible but never
              spoken — the exact silent-swallow the note exists to fix. */}
          <div className="ws-status" role="status" aria-live="polite">{openNote}</div>
          <ChatPanel />
        </aside>
        <section className="canvas">
          {selected ? (
            <DefinitionGraph key={selected.id} definition={selected.definition} />
          ) : (
            <div className="canvas-empty">
              {interfaces.length === 0
                ? 'Your workspace canvas — agents will land here.'
                : 'Pick a workspace on the left to see it as a graph.'}
            </div>
          )}
        </section>
      </main>
    </div>
  )
}
