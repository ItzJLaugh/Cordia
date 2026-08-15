import { useEffect, useRef, useState } from 'react'

import { apiErrorKind, getApi, postRun, postSkillExecute } from './api.js'
import ArtifactCard from './ArtifactCard.jsx'
import DefinitionGraph from './DefinitionGraph.jsx'
import { alidoraMapToFlow } from './graph.js'
import {
  assistantReplyModel,
  assistantTurnFailed,
  assistantTurnStarted,
  createSkillInteractionController,
  isAssistantSendKey,
  loadWorkspaceTruth,
  workspaceRendererModel,
} from './workspace-view.js'

function loadNotice(state, subject) {
  if (state.phase === 'loading') return `Loading ${subject}…`
  if (state.phase === 'signed-out') return 'Your session ended. Sign in again to open this workspace.'
  if (state.phase === 'offline') return 'Cordia is unavailable right now. Your workspace has not been changed.'
  if (state.phase === 'malformed') return 'Cordia returned an unexpected response. Refresh to try again.'
  return `Unable to load ${subject}. Refresh to try again.`
}

function Assistant({ workspaceId, enabled, readOnly, state, setState, nextId, operationRef }) {
  const inputRef = useRef(null)
  const scrollRef = useRef(null)
  const aliveRef = useRef(true)
  const wasBusyRef = useRef(false)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  useEffect(() => {
    if (scrollRef.current) scrollRef.current.scrollTop = scrollRef.current.scrollHeight
  }, [state.transcript, state.busy, state.note])

  useEffect(() => {
    if (wasBusyRef.current && !state.busy && enabled
        && document.activeElement === document.body && inputRef.current) inputRef.current.focus()
    wasBusyRef.current = state.busy
  }, [enabled, state.busy])

  function fail(copy) {
    operationRef.current = ''
    setState((current) => assistantTurnFailed(current, copy))
  }

  function send() {
    if (!enabled || readOnly || state.busy || operationRef.current || !state.draft.trim()) return
    const started = assistantTurnStarted(state, nextId())
    if (!started.pending) return
    operationRef.current = 'assistant'
    setState(started)
    postRun(workspaceId, started.pending.text).then((response) => {
      if (!aliveRef.current) return
      const reply = assistantReplyModel(response)
      if (!reply) {
        fail('Cordia returned an unexpected response. Your draft is safe to send again.')
        return
      }
      const replyId = nextId()
      operationRef.current = ''
      setState((current) => ({
        transcript: [...current.transcript, { id: replyId, who: 'cordia', text: reply.text }],
        draft: '', note: reply.note, busy: false, pending: null,
      }))
    }).catch((error) => {
      if (!aliveRef.current) return
      const kind = apiErrorKind(error)
      if (kind === 'signed-out') fail('Your session ended. Sign in again to send this. Your draft is safe.')
      else if (kind === 'rate-limit') fail('Message limit reached. Wait a few minutes; your draft is safe.')
      else if (kind === 'offline') fail('The server is unreachable right now. Your draft is safe to send again.')
      else fail('That message did not get through. Your draft is safe to send again.')
    })
  }

  function onKeyDown(event) {
    if (!isAssistantSendKey(event)) return
    event.preventDefault()
    send()
  }

  const disabled = !enabled || readOnly || state.busy
  return (
    <aside className="assistant" aria-labelledby="assistant-title">
      <div className="assistant-heading">
        <span className="assistant-mark" aria-hidden="true">C</span>
        <div>
          <h2 id="assistant-title">Cordia assistant</h2>
          <p>{readOnly ? 'Alidora is a read-only system view.' : 'Shape the work. Cordia keeps the source of truth.'}</p>
        </div>
      </div>
      <div className="chat-scroll" ref={scrollRef} role="log" aria-live="polite" aria-label="Conversation with Cordia">
        {state.transcript.length === 0 && (
          <p className="chat-hint">
            {readOnly
              ? 'Return to Workspace to ask Cordia to act.'
              : 'Tell Cordia what you want to understand, coordinate, or move forward.'}
          </p>
        )}
        {state.transcript.map((message) => (
          <div key={message.id} className={`message ${message.who}`}>
            <span className="message-label">{message.who === 'you' ? 'You' : 'Cordia'}</span>
            <span>{message.text}</span>
          </div>
        ))}
        {state.busy && <div className="message cordia pending"><span>Thinking…</span></div>}
      </div>
      <div className="assistant-status" role="status" aria-live="polite">{state.note}</div>
      <form className="composer" onSubmit={(event) => { event.preventDefault(); send() }}>
        <label className="sr-only" htmlFor="cordia-message">Message Cordia</label>
        <textarea
          id="cordia-message"
          ref={inputRef}
          value={state.draft}
          onChange={(event) => setState((current) => ({ ...current, draft: event.target.value }))}
          onKeyDown={onKeyDown}
          placeholder={readOnly ? 'Return to Workspace to send' : 'Ask Cordia…'}
          rows={3}
          maxLength={6000}
          disabled={disabled}
        />
        <button type="submit" disabled={disabled || !state.draft.trim()} aria-label="Send message to Cordia">
          Send
        </button>
      </form>
    </aside>
  )
}

function WorkspaceCanvas({
  workspaceId, onReadyChange, refreshRevision, onSkillAction, skillBusyId, actionsDisabled,
}) {
  const [state, setState] = useState({ phase: 'loading' })

  useEffect(() => {
    let active = true
    setState({ phase: 'loading' })
    onReadyChange(false)
    loadWorkspaceTruth(getApi, workspaceId).then(({ workspace, supplemental }) => {
      if (!active) return
      const model = workspaceRendererModel(workspace, supplemental, workspaceId)
      if (!model) {
        setState({ phase: 'malformed' })
        return
      }
      setState({ phase: 'ready', model })
      onReadyChange(true)
    }).catch((error) => {
      if (!active) return
      setState({ phase: apiErrorKind(error) })
    })
    return () => { active = false }
  }, [workspaceId, onReadyChange, refreshRevision])

  if (state.phase !== 'ready') {
    return <div className="canvas-notice" role="status">{loadNotice(state, 'your workspace')}</div>
  }

  return (
    <section className="artifact-canvas" aria-labelledby="workspace-heading">
      <header className="canvas-heading">
        <div>
          <span className="eyebrow">Workspace</span>
          <h1 id="workspace-heading">{state.model.title}</h1>
          {state.model.description && <p>{state.model.description}</p>}
        </div>
        <span className="view-mode">DashView</span>
      </header>
      {state.model.cards.length ? (
        <div className="artifact-grid">
          {state.model.cards.map((card) => (
            <ArtifactCard
              key={card.id}
              card={card}
              actionBusy={card.action && card.action.id === skillBusyId}
              actionsDisabled={actionsDisabled}
              onAction={onSkillAction}
            />
          ))}
        </div>
      ) : (
        <div className="canvas-empty">This workspace is ready for Cordia to shape its first artifacts.</div>
      )}
    </section>
  )
}

function AlidoraCanvas({ workspaceId }) {
  const [state, setState] = useState({ phase: 'loading' })

  useEffect(() => {
    let active = true
    setState({ phase: 'loading' })
    getApi(`/surveyor/alidora/map?id=${encodeURIComponent(workspaceId)}`).then((response) => {
      if (!active) return
      const map = response && response.map
      if (!map || typeof map !== 'object' || Array.isArray(map)
          || !map.workspace || map.workspace.id !== workspaceId) {
        setState({ phase: 'malformed' })
        return
      }
      setState({ phase: 'ready', flow: alidoraMapToFlow(map) })
    }).catch((error) => {
      if (active) setState({ phase: apiErrorKind(error) })
    })
    return () => { active = false }
  }, [workspaceId])

  if (state.phase !== 'ready') {
    return <div className="canvas-notice" role="status">{loadNotice(state, 'Alidora')}</div>
  }

  return (
    <section className="alidora-canvas" aria-labelledby="alidora-heading">
      <div className="alidora-heading">
        <div>
          <span className="eyebrow">Advanced · read-only</span>
          <h1 id="alidora-heading">Alidora system map</h1>
        </div>
      </div>
      <div className="graph-canvas"><DefinitionGraph flow={state.flow} /></div>
    </section>
  )
}

export default function WorkspaceView({ route }) {
  const [workspaceReady, setWorkspaceReady] = useState(false)
  const [refreshRevision, setRefreshRevision] = useState(0)
  const [assistantState, setAssistantState] = useState({
    transcript: [], draft: '', note: '', busy: false, pending: null,
  })
  const operationRef = useRef('')
  const idRef = useRef(0)
  const skillControllerRef = useRef(null)
  if (!skillControllerRef.current) {
    skillControllerRef.current = createSkillInteractionController({
      executeSkill: postSkillExecute,
      errorKind: apiErrorKind,
      nextId: () => ++idRef.current,
      operation: operationRef,
      updateState: setAssistantState,
      refresh: () => setRefreshRevision((revision) => revision + 1),
    })
  }
  const isAlidora = route.view === 'alidora'
  return (
    <main className="workspace-layout">
      <Assistant
        workspaceId={route.workspaceId}
        enabled={workspaceReady}
        readOnly={isAlidora}
        state={assistantState}
        setState={setAssistantState}
        nextId={() => ++idRef.current}
        operationRef={operationRef}
      />
      <div className="workspace-surface">
        {isAlidora
          ? <AlidoraCanvas workspaceId={route.workspaceId} />
          : (
            <WorkspaceCanvas
              workspaceId={route.workspaceId}
              onReadyChange={setWorkspaceReady}
              refreshRevision={refreshRevision}
              onSkillAction={skillControllerRef.current.run}
              skillBusyId={assistantState.pending && assistantState.pending.kind === 'skill'
                ? assistantState.pending.skillId : ''}
              actionsDisabled={assistantState.busy}
            />
          )}
      </div>
    </main>
  )
}
