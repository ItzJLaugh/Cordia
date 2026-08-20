import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'
import { approvalStops, boundedContinuation } from './runflow.js'

// The run drawer: run the SAVED workspace, show labeled output, honor
// approval interrupts, and capture the "did this help?" outcome.
//
// Two honesty rules govern everything here:
//   * runs execute the STORED row (the server fetches by id), so a dirty
//     draft blocks the Run button — silently running yesterday's
//     definition while showing today's canvas would be a lie;
//   * every piece of output renders as a React text node, and the mock's
//     output labels itself — this panel never adds or removes labels.

export default function RunPanel({ interfaceId, savedDefinition, savedStamp, dirty, readOnly }) {
  const [input, setInput] = useState('')
  const [phase, setPhase] = useState('idle')  // idle | running | paused | done
  const [outputs, setOutputs] = useState([])  // [{text}]
  const [remaining, setRemaining] = useState(0)
  const [note, setNote] = useState(null)
  const [outcome, setOutcome] = useState(null) // null | 'asked' | 'recorded' | 'unattached'
  const [outcomeNote, setOutcomeNote] = useState('')
  const [outcomeBusy, setOutcomeBusy] = useState(false)
  const aliveRef = useRef(true)
  const runSeq = useRef(0)
  // The request this run STARTED with. approve() must never read the live
  // textarea — the box stays editable while paused (composing the next
  // request is the natural gesture), and a continuation built from live
  // text silently rewrote the run's premise and persisted a request the
  // person never made against that draft.
  const runInputRef = useRef('')
  const panelRef = useRef(null)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  // New output lands below the fold of the scrolling drawer — bring it
  // into view the way the chat transcript does.
  useEffect(() => {
    const el = panelRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [outputs, phase, outcome])

  // A different workspace, or a new save of this one, invalidates the
  // shown run wholesale — outputs of the old definition must not sit
  // beside the new one as if they were its results.
  useEffect(() => {
    ++runSeq.current
    setPhase('idle')
    setOutputs([])
    setRemaining(0)
    setNote(null)
    setOutcome(null)
    setOutcomeNote('')
    setOutcomeBusy(false)
  }, [interfaceId, savedStamp])

  const stops = approvalStops(savedDefinition)
  // A read-only latch makes saving impossible — blocking runs on dirty
  // would dead-end. The stored row is what runs either way.
  const runBlocked = dirty && !readOnly

  function post(runInput, isContinuation) {
    const seq = ++runSeq.current
    setPhase('running')
    setNote(null)
    api('/dashboard/run', { id: interfaceId, input: runInput }).then((r) => {
      if (!aliveRef.current || seq !== runSeq.current) return
      if (r.code === 200 && r.data && typeof r.data.output === 'string'
          && !r.data.output.trim()) {
        // the run landed but nothing came back — a blank pre followed by
        // the outcome question would present silence as a finished result
        setPhase(isContinuation ? 'paused' : 'idle')
        setNote('No output came back for this run.')
      } else if (r.code === 200 && r.data && typeof r.data.output === 'string') {
        setOutputs((o) => [...o, { text: r.data.output }])
        const left = isContinuation ? remaining - 1 : stops
        setRemaining(left)
        if (left > 0) {
          setPhase('paused')
        } else {
          setPhase('done')
          setOutcome('asked')
        }
      } else if (r.code === 429) {
        setPhase(isContinuation ? 'paused' : 'idle')
        setNote((r.data && r.data.error) || 'Run limit reached — wait a few minutes.')
      } else if (r.code === 401) {
        setPhase(isContinuation ? 'paused' : 'idle')
        setNote('Your session ended — sign in again to run this workspace.')
      } else if (r.code === 404) {
        setPhase('idle')
        setNote('This workspace no longer exists on the server.')
      } else {
        // 502 and the rest: the server already shapes these as prose;
        // render as text, keep the person where they were.
        setPhase(isContinuation ? 'paused' : 'idle')
        setNote((r.data && r.data.error) || 'That run did not get through. Try again.')
      }
    }).catch(() => {
      if (!aliveRef.current || seq !== runSeq.current) return
      setPhase(isContinuation ? 'paused' : 'idle')
      setNote('The server is unreachable right now. Try again.')
    })
  }

  function run() {
    const text = input.trim()
    if (!text || phase === 'running' || runBlocked || !interfaceId) return
    runInputRef.current = text
    setOutputs([])
    setOutcome(null)
    setOutcomeNote('')
    setOutcomeBusy(false)
    post(text, false)
  }

  function approve() {
    if (phase !== 'paused' || outputs.length === 0) return
    const last = outputs[outputs.length - 1].text
    post(boundedContinuation(runInputRef.current, last), true)
  }

  function stopHere() {
    if (phase !== 'paused') return
    setPhase('done')
    setRemaining(0)
    setNote(null)
    setOutcome('asked')
  }

  function sendOutcome(worked) {
    if (outcomeBusy) return
    const seq = runSeq.current   // a late reply must not paint onto a
                                 // different workspace's panel
    setOutcomeBusy(true)
    setNote(null)
    const body = { interface_id: interfaceId, worked }
    const text = outcomeNote.trim()
    if (text) body.description = text
    api('/dashboard/outcome', body).then((r) => {
      if (!aliveRef.current) return
      // context-independent, like every busy flag in this app: a clear
      // below the seq guard latched the buttons forever when a new run
      // bumped the seq while this POST was in flight
      setOutcomeBusy(false)
      if (seq !== runSeq.current) return
      if (r.code === 200 && r.data && r.data.ok) {
        setNote(null)
        setOutcome(r.data.recorded ? 'recorded' : 'unattached')
      } else {
        setNote('That answer did not get through — you can try again.')
      }
    }).catch(() => {
      if (!aliveRef.current) return
      setOutcomeBusy(false)
      if (seq !== runSeq.current) return
      setNote('That answer did not get through — you can try again.')
    })
  }

  return (
    <div className="run-panel" ref={panelRef}>
      <div className="run-input-row">
        <textarea
          rows={2}
          value={input}
          maxLength={6000}
          placeholder="What should this workspace work on?"
          onChange={(e) => setInput(e.target.value)}
          disabled={phase === 'running'}
        />
        <button
          type="button"
          className="run-btn"
          onClick={run}
          disabled={phase === 'running' || runBlocked || !interfaceId || !input.trim()}
        >
          {phase === 'running' ? 'Running…' : 'Run'}
        </button>
      </div>
      {runBlocked && (
        <div className="run-hint">
          Save your changes first — runs use the saved workspace.
        </div>
      )}
      {readOnly && (
        <div className="run-hint">
          Runs use the saved workspace, not the canvas above.
        </div>
      )}
      {!runBlocked && stops > 0 && phase === 'idle' && outputs.length === 0 && (
        <div className="run-hint">
          {stops === 1
            ? 'This workspace pauses once for your approval during a run.'
            : `This workspace pauses ${stops} times for your approval during a run.`}
        </div>
      )}
      <div role="log" aria-live="polite">
        {outputs.map((o, i) => (
          <pre key={i} className="run-output">{o.text}</pre>
        ))}
      </div>
      {phase === 'paused' && (
        <div className="run-approve" role="status" aria-live="polite">
          <span className="run-pause-label">
            Paused for your approval — review the draft above.
          </span>
          <button type="button" className="run-btn" onClick={approve}>
            Approve and continue
          </button>
          <button type="button" onClick={stopHere}>Stop here</button>
        </div>
      )}
      {/* permanently rendered: a live region mounted with its text is
          announced unreliably (the ws-status lesson) */}
      <div className="ws-status" role="status" aria-live="polite">{note}</div>
      {outcome === 'asked' && (
        <div className="run-outcome">
          <span>Did this run give you what you needed?</span>
          <input
            value={outcomeNote}
            maxLength={600}
            placeholder="Anything to add? (optional)"
            onChange={(e) => setOutcomeNote(e.target.value)}
          />
          <div className="ed-confirm-row">
            <button type="button" disabled={outcomeBusy} onClick={() => sendOutcome(true)}>
              It helped
            </button>
            <button type="button" disabled={outcomeBusy} onClick={() => sendOutcome(false)}>
              Not this time
            </button>
          </div>
        </div>
      )}
      <div role="status" aria-live="polite">
        {outcome === 'recorded' && (
          <div className="run-hint">Recorded — thank you.</div>
        )}
        {outcome === 'unattached' && (
          <div className="run-hint">
            Thanks for answering. This workspace has no outcomes record
            yet, so the answer was not saved.
          </div>
        )}
      </div>
    </div>
  )
}
