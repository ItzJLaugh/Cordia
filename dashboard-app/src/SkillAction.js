import { createElement } from 'react'

export default function SkillAction({ action, busy, disabled, onAction }) {
  if (!action || action.kind !== 'skill') return null
  if (!action.enabled) {
    return createElement('p', { className: 'artifact-action-status', role: 'status' }, action.reason)
  }
  const label = action.request.replace(/^Run skill: /, '').replace(/\.$/, '')
  return createElement('button', {
    type: 'button',
    className: 'artifact-action',
    'data-skill-action': action.id,
    'aria-label': `Run ${label}`,
    disabled: Boolean(busy || disabled),
    onClick: () => {
      if (!busy && !disabled && typeof onAction === 'function') onAction(action)
    },
  }, busy ? 'Running\u2026' : 'Run skill')
}
