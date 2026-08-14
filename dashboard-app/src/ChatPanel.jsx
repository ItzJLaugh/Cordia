import { useEffect, useRef, useState } from 'react'
import { api } from './api.js'

// The Cordia agent's text chat — the left half of the split Jackson liked
// from the refund-agent demo. Text-only in v1, but the seam is kept clean
// for voice later: everything below talks to one function, send(), whose
// input happens to come from a textbox today.
//
// Every message renders as a React text node — no HTML paths — so a
// hostile reply or a pasted <script> is inert by construction. The
// transcript lives in client state only; the server is stateless in v1.

export default function ChatPanel({ disabled }) {
  const [transcript, setTranscript] = useState([])
  const [draft, setDraft] = useState('')
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState(null)     // session-expiry / failure copy
  const scrollRef = useRef(null)
  const inputRef = useRef(null)
  const aliveRef = useRef(true)
  const idRef = useRef(0)                    // stable keys for entries that can be withdrawn
  const wasBusyRef = useRef(false)

  useEffect(() => {
    aliveRef.current = true
    return () => { aliveRef.current = false }
  }, [])

  useEffect(() => {
    const el = scrollRef.current
    if (el) el.scrollTop = el.scrollHeight
  }, [transcript, busy])

  useEffect(() => {
    // Disabling the field during flight blurs it to <body>, and without
    // this the person re-clicks into the box on every single turn. Only
    // reclaim focus when it is still parked on <body> — if they moved to
    // the workspace select mid-flight, that choice wins.
    if (wasBusyRef.current && !busy && !disabled
        && document.activeElement === document.body && inputRef.current) {
      inputRef.current.focus()
    }
    wasBusyRef.current = busy
  }, [busy, disabled])

  function send() {
    const message = draft.trim()
    if (!message || busy) return
    const id = ++idRef.current
    setDraft('')
    setNote(null)
    setBusy(true)
    setTranscript((t) => [...t, { id, who: 'you', text: message }])
    // Every failure path withdraws the optimistic bubble AND restores the
    // draft — the two must move together. Leaving the bubble while
    // restoring the draft made a retry stack duplicate turns, and the
    // transcript showed messages that never actually got through.
    function fail(copy) {
      setTranscript((t) => t.filter((m) => m.id !== id))
      setDraft(message)
      setNote(copy)
    }
    api('/dashboard/chat', { message })
      .then((r) => {
        if (!aliveRef.current) return
        setBusy(false)
        if (r.code === 200 && r.data && typeof r.data.reply === 'string') {
          setTranscript((t) => [...t, { id: ++idRef.current, who: 'cordia', text: r.data.reply }])
        } else if (r.code === 401) {
          fail('Your session ended — sign in again to send this. The canvas keeps everything you built.')
        } else if (r.code === 429) {
          fail((r.data && r.data.error) || 'Message limit reached — wait a few minutes.')
        } else {
          fail('That message did not get through. Your draft is safe to send again.')
        }
      })
      .catch(() => {
        if (!aliveRef.current) return
        setBusy(false)
        fail('The server is unreachable right now. Your draft is safe to send again.')
      })
  }

  function onKeyDown(e) {
    // isComposing covers the IME window; some engines deliver the
    // composition-commit Enter with isComposing already false but
    // keyCode 229 — both must fall through to the IME, not send.
    if (e.nativeEvent.isComposing || e.nativeEvent.keyCode === 229) return
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      send()
    }
  }

  return (
    <div className="chat">
      <div className="chat-scroll" ref={scrollRef} role="log" aria-live="polite">
        {transcript.length === 0 && (
          <p className="chat-hint">
            Tell Cordia what you want this workspace to do — it will help
            you decide which agents to add and where you should stay in
            the loop.
          </p>
        )}
        {transcript.map((m) => (
          <div key={m.id} className={m.who === 'you' ? 'msg you' : 'msg cordia'}>
            {m.text}
          </div>
        ))}
        {busy && <div className="msg cordia pending">…</div>}
        {note && <div className="chat-note">{note}</div>}
      </div>
      <div className="chat-input">
        <textarea
          ref={inputRef}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Describe what you want to build…"
          rows={2}
          disabled={disabled || busy}
        />
        <button type="button" onClick={send} disabled={disabled || busy || !draft.trim()}>
          Send
        </button>
      </div>
    </div>
  )
}
