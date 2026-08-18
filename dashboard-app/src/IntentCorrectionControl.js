import React, { useEffect, useRef, useState } from 'react'

import { apiErrorKind, postIntentMiss } from './api.js'

const CATEGORIES = [
  ['missing_context', 'Missing context'],
  ['wrong_audience', 'Wrong audience'],
  ['too_generic', 'Too generic'],
  ['needs_evidence', 'Needs evidence'],
  ['wrong_format', 'Wrong format'],
  ['wrong_constraint', 'Wrong constraint'],
  ['unsafe_to_automate', 'Unsafe to automate'],
  ['needs_human_checkpoint', 'Needs a human checkpoint'],
]

function failureCopy(error) {
  const kind = apiErrorKind(error)
  if (kind === 'signed-out') return 'Your session ended. Sign in again before saving this correction.'
  if (kind === 'rate-limit') return 'Correction limit reached. Wait a few minutes and try again.'
  if (kind === 'offline') return 'Cordia is unavailable right now. Your correction is still here.'
  return 'Cordia could not save this correction. Review it and try again.'
}

export default function IntentCorrectionControl({
  messages = [],
  readOnly = false,
  disabled = false,
  operation,
  onBusyChange = () => {},
  refresh = async () => {},
}) {
  const localOperation = useRef('')
  const operationRef = operation || localOperation
  const submitting = useRef(false)
  const categoryControl = useRef(null)
  const [open, setOpen] = useState(false)
  const [pending, setPending] = useState(false)
  const [category, setCategory] = useState('')
  const [correction, setCorrection] = useState('')
  const [effect, setEffect] = useState('')
  const [notice, setNotice] = useState({ kind: '', text: '' })

  const available = !readOnly && Array.isArray(messages)
    && messages.some((message) => message && message.who === 'cordia')

  useEffect(() => {
    if (open && categoryControl.current) categoryControl.current.focus()
  }, [open])

  if (!available) return null

  function cancel() {
    setCategory('')
    setCorrection('')
    setEffect('')
    setNotice({ kind: '', text: '' })
    setOpen(false)
  }

  async function submit(event) {
    event.preventDefault()
    if (disabled || submitting.current || operationRef.current
        || !category || !correction.trim() || !effect.trim()) return false
    submitting.current = true
    operationRef.current = 'intent-correction'
    setPending(true)
    setNotice({ kind: '', text: '' })
    onBusyChange(true)

    try {
      await postIntentMiss(category, correction, effect)
    } catch (error) {
      setNotice({ kind: 'error', text: failureCopy(error) })
      submitting.current = false
      operationRef.current = ''
      setPending(false)
      onBusyChange(false)
      return false
    }

    setCategory('')
    setCorrection('')
    setEffect('')
    setOpen(false)
    try {
      await refresh()
      setNotice({
        kind: 'success',
        text: 'Correction saved. Cordia refreshed this workspace guidance.',
      })
    } catch (_) {
      setNotice({
        kind: 'success',
        text: 'Correction saved. Reload this workspace to see the refreshed guidance.',
      })
    } finally {
      submitting.current = false
      operationRef.current = ''
      setPending(false)
      onBusyChange(false)
    }
    return true
  }

  return React.createElement(
    'section',
    { className: 'intent-correction', 'aria-label': 'Correct Cordia' },
    !open && React.createElement(
      'button',
      {
        type: 'button',
        className: 'intent-correction-toggle',
        'data-intent-correction-toggle': true,
        disabled,
        onClick: () => {
          setOpen(true)
          setNotice({ kind: '', text: '' })
        },
      },
      'Cordia missed my intent',
    ),
    open && React.createElement(
      'form',
      {
        className: 'intent-correction-form',
        role: 'dialog',
        'aria-labelledby': 'intent-correction-title',
        'aria-describedby': 'intent-correction-description',
        onSubmit: submit,
      },
      React.createElement('h3', { id: 'intent-correction-title' }, 'Correct Cordia'),
      React.createElement('p', { id: 'intent-correction-description' },
        'Help Cordia change how it works with you next time.'),
      React.createElement('label', null,
        'What did Cordia miss?',
        React.createElement('select', {
          ref: categoryControl,
          name: 'category',
          value: category,
          disabled: pending,
          onChange: (event) => setCategory(event.target.value),
        },
        React.createElement('option', { value: '' }, 'Choose one'),
        ...CATEGORIES.map(([value, label]) => React.createElement('option', { key: value, value }, label))),
      ),
      React.createElement('label', null,
        'What should Cordia understand instead?',
        React.createElement('textarea', {
          name: 'correction',
          value: correction,
          maxLength: 600,
          rows: 3,
          disabled: pending,
          onChange: (event) => setCorrection(event.target.value),
        }),
      ),
      React.createElement('label', null,
        'How should Cordia respond next time?',
        React.createElement('textarea', {
          name: 'effect',
          value: effect,
          maxLength: 600,
          rows: 3,
          disabled: pending,
          onChange: (event) => setEffect(event.target.value),
        }),
      ),
      React.createElement('div', { className: 'intent-correction-actions' },
        React.createElement('button', {
          type: 'submit',
          disabled: pending || disabled || !category || !correction.trim() || !effect.trim(),
        }, pending ? 'Saving…' : 'Save correction'),
        React.createElement('button', {
          type: 'button',
          disabled: pending,
          onClick: cancel,
        }, 'Cancel'),
      ),
    ),
    notice.text && React.createElement(
      'p',
      { role: notice.kind === 'error' ? 'alert' : 'status' },
      notice.text,
    ),
  )
}
