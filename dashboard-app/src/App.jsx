import { useCallback, useEffect, useRef, useState } from 'react'
import '@xyflow/react/dist/style.css'
import { api } from './api.js'
import ChatPanel from './ChatPanel.jsx'
import DefinitionGraph from './DefinitionGraph.jsx'
import EditorPanel from './EditorPanel.jsx'
import { addAgent, insertStepAfter } from './mutations.js'
import { cardDetailFor, seedDefinition } from './seed.js'

// The dashboard shell. Step 9: the canvas edits — App owns the draft
// definition (the single source of truth the graph re-projects from),
// every structural change flows through the pure mutations module, and
// saves go to POST /dashboard/interface carrying the `updated` stamp the
// copy was loaded from, so two tabs refuse to clobber each other instead
// of last-write-wins. Name/description/theme are echoed on every save —
// the store row is a full replace, and omitting them would blank them.

const NEW_ID = '__new__'

export default function App() {
  const [state, setState] = useState({ phase: 'loading' })
  const [selected, setSelected] = useState(null)   // stored row | null (creating)
  const [creating, setCreating] = useState(false)
  const [wsName, setWsName] = useState('')
  const [draft, setDraft] = useState(null)         // the definition being edited
  const [dirty, setDirty] = useState(false)
  const [stamp, setStamp] = useState(null)         // `updated` our copy loaded from
  const [readOnlyNote, setReadOnlyNote] = useState(null)
  // saveNote is {text, reload} — the note CARRIES its own reload
  // affordance. Reload discards the draft, so it may render only with
  // the stale-409 copy that says so; a separate flag drifted onto
  // "your edits are still here" notes twice (sweeps 2 and 3), and a
  // one-object shape makes that drift unrepresentable.
  const [saveNote, setSaveNote] = useState(null)
  const [saving, setSaving] = useState(false)
  const [selection, setSelection] = useState(null)
  const [overrides, setOverrides] = useState({})
  const [opening, setOpening] = useState(null)
  const [openNote, setOpenNote] = useState(null)
  const [pendingSwitch, setPendingSwitch] = useState(null)
  // One sequence for every workspace-context change (open, new, switch):
  // any in-flight open OR save response from a superseded context is
  // discarded wholesale — a late save 200 once dragged the person back
  // to the workspace they had just left and let its name bleed across.
  const openSeq = useRef(0)
  // Live mirrors of draft/wsName for async save() adoption — the closure
  // holds click-time values, and adopting the echo over NEWER edits both
  // destroyed the edits and reported "saved".
  const draftRef = useRef(null)
  const wsNameRef = useRef('')
  const dirtyRef = useRef(false)
  // Set by "Discard and switch" for exactly one adoption: an open that
  // RESOLVES onto a dirty draft must not adopt silently (the guard runs
  // at click time, but typing during the round trip re-dirties), unless
  // the person just authorized the discard.
  const discardArmedRef = useRef(false)
  useEffect(() => { draftRef.current = draft }, [draft])
  useEffect(() => { wsNameRef.current = wsName }, [wsName])
  useEffect(() => { dirtyRef.current = dirty }, [dirty])
  // The unsaved-changes banner exists only while something is unsaved —
  // a save or an adoption that clears dirty takes the banner with it.
  useEffect(() => { if (!dirty) setPendingSwitch(null) }, [dirty])

  function adoptRow(row) {
    // Adoption IS a context change — bump here, not just at request
    // time: a save clicked in the window between an open's request and
    // its adoption captured the request-time seq, which is the same seq
    // the post-adoption context runs under, and its late response
    // adopted the OLD workspace's row into the NEW context.
    ++openSeq.current
    setSelected(row)
    setCreating(false)
    setWsName(row.name || '')
    setDraft(row.definition)
    setDirty(false)
    setStamp(row.updated || null)
    setReadOnlyNote(null)
    setSaveNote(null)
    setSelection(null)
    setOverrides({})
    // A save stalled in a PREVIOUS context must not hold this one
    // hostage — its response is seq-discarded anyway.
    setSaving(false)
  }

  function openInterface(id) {
    const seq = ++openSeq.current
    setOpening(id)
    setOpenNote(null)
    // The discard grant is consumed at REQUEST time, per open: a
    // superseded or hung open takes its grant with it. Leaving the flag
    // for the response body leaked it past the seq check — a stale grant
    // then authorized a later, unrelated adoption and lost real work.
    const armed = discardArmedRef.current
    discardArmedRef.current = false
    api('/dashboard/interface?id=' + encodeURIComponent(id)).then((r) => {
      if (seq !== openSeq.current) return
      setOpening(null)
      if (r.code === 200 && r.data && r.data.interface) {
        if (dirtyRef.current && !armed) {
          // The dirty guard ran at CLICK time, but the person typed
          // during the round trip — adopting now would silently discard
          // that work. Re-raise the guard instead; Discard re-opens with
          // the authorization armed.
          setPendingSwitch(id)
          return
        }
        adoptRow(r.data.interface)
      } else {
        setOpenNote('That workspace could not be opened just now.')
        // The failed open leaves the person in the PREVIOUS context, but
        // this open already bumped openSeq — a save in flight when they
        // switched can never clear `saving` (its response is discarded,
        // and adoptRow never ran). Without this, "Saving…" pins forever
        // and the dirty edits on screen become unsavable.
        setSaving(false)
      }
    }).catch(() => {
      if (seq !== openSeq.current) return
      setOpening(null)
      setOpenNote('That workspace could not be opened just now.')
      setSaving(false)
    })
  }

  const refreshInterfaces = useCallback(() => {
    api('/dashboard/interface').then((r) => {
      if (r.code === 200 && r.data && Array.isArray(r.data.interfaces)) {
        setState((s) => (s.phase === 'ready'
          ? { ...s, interfaces: r.data.interfaces } : s))
      }
    }).catch(() => {})
  }, [])

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
      .catch(() => { if (alive) setState({ phase: 'offline' }) })
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
  const editingSomething = draft !== null
  const readOnly = Boolean(readOnlyNote)

  function startNew() {
    ++openSeq.current            // cancel in-flight opens and saves
    discardArmedRef.current = false  // consumed by this synchronous switch
    setOpening(null)
    setOpenNote(null)
    setSelected(null)
    setCreating(true)
    setWsName('New workspace')
    setDraft(seedDefinition(framework))
    setDirty(true)
    setStamp(null)
    setReadOnlyNote(null)
    setSaveNote(null)
    setSelection(null)
    setOverrides({})
    setSaving(false)
  }

  // The select's onChange routes here: a dirty draft blocks the switch
  // until the person saves or explicitly discards — silent discard was
  // the alternative, and it loses real work.
  function requestSwitch(value) {
    if (!value) return
    if (dirty) { setPendingSwitch(value); return }
    if (value === NEW_ID) startNew()
    else openInterface(value)
  }

  function applyEdit(next, sel) {
    if (readOnly || !next) return
    setDraft(next)
    setDirty(true)
    setSelection(sel === undefined ? selection : sel)
    // Prune drag overrides for ids that no longer exist — a later
    // re-minted id must not inherit a deleted node's dragged position.
    setOverrides((o) => {
      const live = new Set((next.agents || []).map((a) => a && a.id))
      for (const s of ((next.workflow || {}).steps) || []) {
        if (s && typeof s.agentId === 'string') live.add(s.agentId)
      }
      const kept = {}
      for (const [id, pos] of Object.entries(o)) {
        if (live.has(id)) kept[id] = pos
      }
      return kept
    })
  }

  function handleConnect(sourceId, targetId) {
    const res = insertStepAfter(
      draft, sourceId, targetId,
      framework.approval_density === 'checkpoint_every_step',
    )
    if (!res) {
      // true at 200, and at 199 when the gesture needs two inserts
      setSaveNote({ text: 'There is not enough room left for this connection — a workspace holds at most 200 steps.' })
      return
    }
    applyEdit(res.definition, { kind: 'step', index: res.index })
  }

  function handleAddAgent() {
    const res = addAgent(draft)
    if (!res) { setSaveNote({ text: 'This workspace already holds the maximum 200 agents.' }); return }
    const idx = (res.definition.agents || []).length - 1
    applyEdit(res.definition, { kind: 'agent', id: res.id, agentIndex: idx, placeholder: false })
  }

  function save() {
    if (!dirty || saving || readOnly || !draft) return
    const seq = openSeq.current      // discard the response if the person leaves
    const postedDraft = draft
    const postedName = wsName.trim() || 'Untitled interface'
    setSaving(true)
    setSaveNote(null)
    const body = {
      id: selected ? selected.id : null,
      name: postedName,
      description: (selected && selected.description) || '',
      theme: (selected && selected.theme) || null,
      definition: postedDraft,
    }
    if (selected && stamp) body.expected_updated = stamp
    api('/dashboard/interface', body).then((r) => {
      // saving clears only for the context that started this save —
      // adoptRow/startNew reset it on every context change, and an
      // unconditional clear here let a superseded response release a
      // LIVE save running in the new context.
      if (seq === openSeq.current) setSaving(false)
      if (r.code === 200 && r.data && r.data.ok) {
        // Also context-independent: the row landed server-side whether or
        // not the person is still looking at it — a created workspace
        // must reach the picker, or it reads as a failed save and gets
        // rebuilt as a duplicate.
        refreshInterfaces()
      }
      if (seq !== openSeq.current) return   // they switched away — the row
                                            // is saved; this context is gone
      if (r.code === 200 && r.data && r.data.ok) {
        setStamp(r.data.updated || null)
        setSelected({
          ...(selected || {}), id: r.data.id, name: postedName,
          description: body.description, theme: body.theme,
          definition: r.data.definition, updated: r.data.updated,
        })
        // Adopt the canonical echo ONLY when the draft is still the one
        // that was posted — edits made during the round trip are newer
        // than the echo, and clobbering them while clearing the dirty
        // flag both destroyed work and reported it saved.
        if (draftRef.current === postedDraft) {
          setDraft(r.data.definition)
          const nameMovedOn = wsNameRef.current.trim() !== postedName
            && !(wsNameRef.current.trim() === '' && postedName === 'Untitled interface')
          setDirty(nameMovedOn)
          if (!nameMovedOn) setWsName(postedName)
        }
        setCreating(false)
      } else if (r.code === 409 && r.data && r.data.kind === 'stale') {
        setSaveNote({ text: 'This workspace changed since you loaded it — reloading picks up the newer version; your unsaved edits here would be replaced.', reload: true })
      } else if (r.code === 409) {
        setReadOnlyNote((r.data && r.data.error) || 'This workspace holds content the dashboard cannot edit yet — open it in the builder instead.')
      } else if (r.code === 404) {
        setSaveNote({ text: 'This workspace no longer exists — it may have been removed elsewhere.' })
      } else if (r.code === 401) {
        setSaveNote({ text: 'Your session ended — sign in again to save. Your edits stay right here.' })
      } else {
        setSaveNote({ text: (r.data && r.data.error) || 'That save did not get through. Your edits are still here — try again.' })
      }
    }).catch(() => {
      if (seq !== openSeq.current) return
      setSaving(false)
      setSaveNote({ text: 'The server is unreachable right now. Your edits are still here — try again.' })
    })
  }

  return (
    <div className="shell">
      <header className="topbar">
        <span className="brand">Cordia — Dashboard</span>
        <span className="shaped">{framework.reason}</span>
        {limited && <span className="limited">Limited mode</span>}
      </header>
      {limited && <div className="limited-note">{llm.note}</div>}
      <main className="split">
        <aside className="panel chat-panel">
          <div className="workspace-row">
            <label className="ws-label" htmlFor="ws-select">Workspace</label>
            <select
              id="ws-select"
              value={creating ? NEW_ID : (opening || (selected ? selected.id : ''))}
              onChange={(e) => requestSwitch(e.target.value)}
            >
              <option value="">
                {interfaces.length === 0
                  ? 'None yet — start one'
                  : 'Pick a workspace…'}
              </option>
              <option value={NEW_ID}>+ New workspace</option>
              {/* A just-created workspace is selected before the async
                  list refresh lands; a controlled select with no
                  matching option falls back to the placeholder, which
                  read as the save having failed. */}
              {selected && !interfaces.some((i) => i.id === selected.id) && (
                <option value={selected.id}>{selected.name}</option>
              )}
              {interfaces.map((iface) => (
                <option key={iface.id} value={iface.id}>{iface.name}</option>
              ))}
            </select>
          </div>
          <div className="ws-status" role="status" aria-live="polite">
            {pendingSwitch ? 'You have unsaved changes here.' : (openNote || '')}
          </div>
          {pendingSwitch && (
            <div className="ed-confirm-row ws-switch-row">
              <button
                type="button"
                className="ed-danger"
                onClick={() => {
                  const target = pendingSwitch
                  setPendingSwitch(null)
                  // dirty is NOT cleared here: the open is async and can
                  // fail, and the discard only truly happens when the
                  // replacement is adopted (adoptRow/startNew both settle
                  // it). Clearing early left edited content on screen
                  // with the app claiming nothing was unsaved. The armed
                  // ref authorizes exactly the adoption this click asked
                  // for — without it, a still-dirty draft re-raises the
                  // guard when the open resolves, forever.
                  discardArmedRef.current = true
                  if (target === NEW_ID) startNew()
                  else openInterface(target)
                }}
              >
                Discard and switch
              </button>
              <button type="button" onClick={() => setPendingSwitch(null)}>Stay here</button>
            </div>
          )}
          <ChatPanel />
        </aside>
        <section className="canvas">
          {editingSomething && (
            <div className="canvas-toolbar">
              <input
                className="ws-name"
                value={wsName}
                maxLength={120}
                aria-label="Workspace name"
                disabled={readOnly}
                onChange={(e) => { setWsName(e.target.value); setDirty(true) }}
              />
              <button type="button" onClick={handleAddAgent} disabled={readOnly}>
                Add agent
              </button>
              {Object.keys(overrides).length > 0 && (
                <button type="button" onClick={() => setOverrides({})}>
                  Reset layout
                </button>
              )}
              <span className="toolbar-space" />
              {dirty && !readOnly && <span className="dirty-chip">Unsaved changes</span>}
              <button
                type="button"
                className="save-btn"
                onClick={save}
                disabled={!dirty || saving || readOnly}
              >
                {saving ? 'Saving…' : 'Save'}
              </button>
            </div>
          )}
          {readOnlyNote && <div className="limited-note">{readOnlyNote}</div>}
          {saveNote && (
            <div className="limited-note">
              {saveNote.text}
              {saveNote.reload && selected && (
                <button
                  type="button"
                  className="note-action"
                  onClick={() => {
                    setSaveNote(null)
                    // the stale note this button lives in already stated
                    // the consequence ("your unsaved edits here would be
                    // replaced") — this click IS the authorization, and
                    // without arming it the dirty re-guard bounced the
                    // reload every single time with mismatched copy
                    discardArmedRef.current = true
                    openInterface(selected.id)
                  }}
                >
                  Reload newest
                </button>
              )}
            </div>
          )}
          <div className="canvas-body">
            {editingSomething ? (
              <DefinitionGraph
                key={selected ? selected.id : NEW_ID}
                definition={draft}
                overrides={overrides}
                cardDetail={cardDetailFor(framework)}
                readOnly={readOnly}
                selection={selection}
                onSelect={setSelection}
                onConnect={handleConnect}
                onNodeMoved={(id, position) =>
                  setOverrides((o) => ({ ...o, [id]: position }))}
              />
            ) : (
              <div className="canvas-empty">
                {interfaces.length === 0
                  ? 'Your workspace canvas — start a new workspace to begin.'
                  : 'Pick a workspace on the left, or start a new one.'}
              </div>
            )}
            <EditorPanel
              definition={draft}
              selection={readOnly ? null : selection}
              onChange={applyEdit}
              onClose={() => setSelection(null)}
            />
          </div>
        </section>
      </main>
    </div>
  )
}
