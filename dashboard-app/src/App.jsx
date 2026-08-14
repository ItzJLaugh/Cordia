import { useEffect, useState } from 'react'
import '@xyflow/react/dist/style.css'

import { getApi, safeErrorMessage } from './api.js'
import DefinitionGraph from './DefinitionGraph.jsx'

function workspaceIdFromQuery() {
  return new URLSearchParams(window.location.search).get('workspace') || ''
}

export default function App() {
  const [state, setState] = useState({ phase: 'loading' })
  const workspaceId = workspaceIdFromQuery()

  useEffect(() => {
    let active = true
    if (!workspaceId) {
      setState({ phase: 'empty' })
      return () => { active = false }
    }

    getApi(`/surveyor/alidora/map?id=${encodeURIComponent(workspaceId)}`)
      .then(({ map }) => {
        if (!active) return
        setState(map && typeof map === 'object' ? { phase: 'ready', map } : { phase: 'empty' })
      })
      .catch((error) => {
        if (active) setState({ phase: 'error', error: safeErrorMessage(error) })
      })
    return () => { active = false }
  }, [workspaceId])

  let content
  if (state.phase === 'loading') {
    content = <div className="canvas-empty">Loading Alidora system map…</div>
  } else if (state.phase === 'empty') {
    content = <div className="canvas-empty">No system map is available for this workspace.</div>
  } else if (state.phase === 'error') {
    content = <div className="canvas-empty">Unable to load Alidora: {state.error}</div>
  } else {
    content = <DefinitionGraph map={state.map} />
  }

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Alidora</span>
        <span className="shaped">Agentic System Builder by Cordia</span>
      </header>
      <main className="canvas">{content}</main>
    </div>
  )
}
