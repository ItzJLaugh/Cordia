import { workspaceToRendererModel } from './workspace.js'

const SAFE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,79}$/
const CREDENTIAL_PREFIX = /^(?:token|authorization|password|secret|credential|api[_-]?key)\s*[:=]/i
const SECRET_OR_PATH = /(?:[A-Za-z]:\\|\\\\[^\s]+\\|\/(?:home|root|Users)\/|\b(?:token|secret|password|authorization|bearer|api[_-]?key)\b\s*[:=]|\b(?:ghp_|github_pat_|xox[baprs]-|sk-)[A-Za-z0-9_-]{8,})/i
const SAFE_TIMESTAMP = /^\d{4}-\d{2}-\d{2}T[0-9:.+-]+Z?$/
const DECISIONS = new Set(['ALLOW', 'ASK', 'DENY'])
const PERMISSIONS = new Set(['ALLOW', 'ASK', 'DENY'])
const SUPPLEMENTAL_ENDPOINTS = {
  artifacts: '/surveyor/artifacts',
  capabilities: '/surveyor/capabilities',
  skills: '/surveyor/skills',
  activity: '/surveyor/activity',
}

function safeId(value) {
  return typeof value === 'string' && SAFE_ID.test(value) && !CREDENTIAL_PREFIX.test(value) ? value : ''
}

function safeText(value, limit = 160) {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  if (!text || text.length > limit || /[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text) || SECRET_OR_PATH.test(text)) return ''
  return text
}

function safeRepositoryLabel(source) {
  if (!source || typeof source !== 'object' || Array.isArray(source) || source.kind !== 'github_repository') return ''
  const label = typeof source.label === 'string' ? source.label.trim() : ''
  return /^[A-Za-z0-9_.-]{1,100}\/[A-Za-z0-9_.-]{1,100}$/.test(label) ? label : ''
}

function listFrom(response, key) {
  return response && typeof response === 'object' && !Array.isArray(response)
    && response.ok === true && Array.isArray(response[key]) ? response[key] : []
}

function stable(records) {
  return records.sort((left, right) => left.id.localeCompare(right.id))
}

function connectorReadiness(connectors, requiredIds) {
  const byId = new Map(connectors.map((connector) => [connector.id, connector]))
  const required = requiredIds.map((id) => byId.get(id))
  if (required.some((connector) => !connector)) return 'missing'
  if (required.some((connector) => connector.implementation === 'planned')) return 'planned'
  if (required.some((connector) => connector.consent !== 'confirmed')) return 'connect'
  if (required.some((connector) => connector.lifecycle !== 'live' || connector.runtime !== 'live')) return 'unhealthy'
  return 'ready'
}

function connectorIds(value) {
  if (value === undefined) return []
  if (!Array.isArray(value)) return null
  const ids = [...new Set(value.map(safeId).filter(Boolean))].sort((left, right) => left.localeCompare(right))
  return ids.length === value.length ? ids : null
}

function readinessBadge(readiness) {
  if (readiness === 'planned') return 'Planned'
  if (readiness === 'connect') return 'Connect first'
  if (readiness === 'missing' || readiness === 'unhealthy') return 'Unavailable'
  return ''
}

function skillRequest(title) {
  const name = title.replace(/[.!?]+$/u, '').trim()
  return name ? safeText(`Run skill: ${name}.`, 200) : ''
}

function skillActionReason(skill, readiness) {
  if (readiness === 'missing') return 'A required connector is not available in this workspace.'
  if (readiness === 'planned') return 'This skill is planned for a desktop or local surface and is not available here.'
  if (readiness === 'connect') return 'Connect the required connector before running this skill.'
  if (readiness === 'unhealthy') return 'A required connector needs attention before this skill can run.'
  if (skill.permission === 'ASK') return 'Approval is required. This web view cannot continue the protected external action.'
  if (skill.permission === 'DENY') return 'Cordia policy does not allow this skill.'
  if (skill.available !== true) return 'This skill is not available through its declared capability.'
  return ''
}

function missionCard(response) {
  const artifacts = response && typeof response === 'object' && !Array.isArray(response)
    && response.ok === true && response.artifacts && typeof response.artifacts === 'object'
    && !Array.isArray(response.artifacts) ? response.artifacts : null
  if (!artifacts) return null
  const body = safeText(artifacts['runtime/fde-tasks.md'], 2000)
    .replace(/^# FDE Mission Brief\s*/i, '')
    .trim()
  return body ? { id: 'mission', kind: 'mission', title: 'Cordia mission', body } : null
}

function contextCard(workspace) {
  const items = (Array.isArray(workspace.context_sources) ? workspace.context_sources : [])
    .map((source) => {
      const label = safeRepositoryLabel(source)
      return label ? { label, meta: 'GitHub repository' } : null
    })
    .filter(Boolean)
    .sort((left, right) => left.label.localeCompare(right.label))
  return items.length ? { id: 'context', kind: 'context', title: 'Active context', items } : null
}

function workflowCard(model) {
  const items = model.workflowRows.map((row) => ({
    label: row.agentId,
    meta: `${row.skillIds.length ? row.skillIds.join(', ') : 'No skills'}${row.requiresApproval ? ' · approval required' : ''}`,
  }))
  return items.length ? { id: 'workflow', kind: 'workflow', title: 'Workflow', items } : null
}

function agentCards(workspace) {
  const cards = (Array.isArray(workspace.agents) ? workspace.agents : []).map((agent) => {
    if (!agent || typeof agent !== 'object' || Array.isArray(agent)) return null
    const id = safeId(agent.id)
    const title = safeText(agent.name)
    if (!id || !title) return null
    const body = safeText(agent.description, 320)
    return { id: `agent:${id}`, kind: 'agent', title, ...(body ? { body } : {}) }
  }).filter(Boolean)
  return stable(cards)
}

function connectorCards(model) {
  return model.connectors.map((connector) => {
    const readiness = connectorReadiness(model.connectors, [connector.id])
    return {
      id: `connector:${connector.id}`,
      kind: 'connector',
      title: connector.id,
      badge: readiness === 'ready' ? 'Available now' : readinessBadge(readiness),
      items: [
        { label: 'Consent', meta: connector.consent },
        { label: 'Adapter', meta: connector.implementation },
        { label: 'Lifecycle', meta: connector.lifecycle.replaceAll('_', ' ') },
        { label: 'Runtime', meta: connector.runtime.replaceAll('_', ' ') },
      ],
    }
  })
}

function derivedCards(model) {
  return model.artifactCards
    .filter((card) => card.kind === 'derived')
    .map((card) => ({ id: `derived:${card.id}`, kind: 'derived-note', title: card.title, badge: 'DashView' }))
}

function skillCards(response, connectors) {
  const cards = listFrom(response, 'skills').map((skill) => {
    if (!skill || typeof skill !== 'object' || Array.isArray(skill)) return null
    const id = safeId(skill.id)
    const title = safeText(skill.name)
    const body = safeText(skill.summary, 320)
    const permission = PERMISSIONS.has(skill.permission) ? skill.permission : ''
    const requiredConnectors = connectorIds(skill.required_connectors)
    if (!id || !title || !body || !permission || !requiredConnectors) return null
    const readiness = connectorReadiness(connectors, requiredConnectors)
    const connectorBadge = readinessBadge(readiness)
    const reason = skillActionReason(skill, readiness)
    const request = skillRequest(title)
    if (!request) return null
    return {
      id: `skill:${id}`, kind: 'skill', title, body,
      badge: connectorBadge || (skill.available === true && permission === 'ALLOW'
        ? 'Available now' : permission === 'ASK' ? 'Approval required' : 'Unavailable'),
      action: {
        kind: 'skill', id, request,
        enabled: readiness === 'ready' && skill.available === true && permission === 'ALLOW',
        reason,
      },
    }
  }).filter(Boolean)
  return stable(cards)
}

function capabilityCards(response, connectors) {
  const cards = listFrom(response, 'capabilities').map((capability) => {
    if (!capability || typeof capability !== 'object' || Array.isArray(capability)) return null
    const id = safeId(capability.name)
    const title = safeText(capability.summary, 320)
    const decision = DECISIONS.has(capability.decision) ? capability.decision : ''
    const connectorId = safeId(capability.connector)
    if (!id || !title || !decision || !connectorId) return null
    const connectorBadge = readinessBadge(connectorReadiness(connectors, [connectorId]))
    return {
      id: `capability:${id}`, kind: 'capability', title,
      badge: connectorBadge || (decision === 'ALLOW' ? 'Can use' : decision === 'ASK' ? 'Will ask' : 'Cannot use'),
    }
  }).filter(Boolean)
  return stable(cards)
}

function activityCards(response) {
  return listFrom(response, 'activity').slice(0, 5).map((event, index) => {
    if (!event || typeof event !== 'object' || Array.isArray(event)) return null
    const eventType = safeId(event.event_type)
    const created = typeof event.created === 'string' && event.created.length <= 64 && SAFE_TIMESTAMP.test(event.created)
      ? event.created : ''
    if (!eventType) return null
    return {
      id: `activity:${String(index).padStart(4, '0')}`, kind: 'activity', title: 'Recent activity',
      items: [{ label: eventType.replaceAll('_', ' '), ...(created ? { meta: created } : {}) }],
    }
  }).filter(Boolean)
}

export function routeFromSearch(search) {
  const params = new URLSearchParams(typeof search === 'string' ? search : '')
  const workspaceId = safeId(params.get('workspace'))
  if (!workspaceId) {
    return { phase: 'missing', workspaceId: '', view: 'workspace', workspaceHref: '', alidoraHref: '' }
  }
  const encoded = encodeURIComponent(workspaceId)
  return {
    phase: 'ready',
    workspaceId,
    view: params.get('view') === 'alidora' ? 'alidora' : 'workspace',
    workspaceHref: `?workspace=${encoded}`,
    alidoraHref: `?workspace=${encoded}&view=alidora`,
  }
}

export function workspaceRendererModel(response, supplemental = {}, expectedWorkspaceId = '') {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true
      || !response.workspace || typeof response.workspace !== 'object' || Array.isArray(response.workspace)
      || !expectedWorkspaceId || response.workspace.id !== expectedWorkspaceId) return null

  const workspace = response.workspace
  const canonical = workspaceToRendererModel(response)
  const cards = [
    missionCard(supplemental.artifacts),
    contextCard(workspace),
    workflowCard(canonical),
    ...agentCards(workspace),
    ...connectorCards(canonical),
    ...derivedCards(canonical),
    ...skillCards(supplemental.skills, canonical.connectors),
    ...capabilityCards(supplemental.capabilities, canonical.connectors),
    ...activityCards(supplemental.activity),
  ].filter(Boolean)

  return {
    title: safeText(workspace.title) || 'Cordia Workspace',
    description: safeText(workspace.description, 320),
    cards,
    viewMode: canonical.viewMode,
  }
}

export async function loadWorkspaceTruth(get, workspaceId) {
  const id = safeId(workspaceId)
  if (!id || typeof get !== 'function') throw new Error('Invalid workspace request')
  const workspace = await get(`/surveyor/workspace?id=${encodeURIComponent(id)}`)
  const entries = Object.entries(SUPPLEMENTAL_ENDPOINTS)
  const settled = await Promise.allSettled(entries.map(([, path]) => get(path)))
  const supplemental = {}
  settled.forEach((result, index) => {
    if (result.status === 'fulfilled') supplemental[entries[index][0]] = result.value
  })
  return { workspace, supplemental }
}

function boundedAssistantText(value) {
  return typeof value === 'string' ? value.trim().slice(0, 6000) : ''
}

export function assistantReplyModel(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true) return null
  const text = safeText(response.output, 6000)
  if (!text) return null
  const limited = Boolean(response.llm && typeof response.llm === 'object' && response.llm.live === false)
  const note = limited ? safeText(response.llm.note, 240) : ''
  return { text, limited, note }
}

export function assistantTurnStarted(state, id) {
  const text = boundedAssistantText(state && state.draft)
  if (!text) return state
  return {
    transcript: [...(Array.isArray(state.transcript) ? state.transcript : []), { id, who: 'you', text }],
    draft: '', note: '', busy: true, pending: { id, text },
  }
}

export function assistantTurnFailed(state, note) {
  if (!state || !state.pending) return state
  return {
    transcript: state.transcript.filter((message) => message.id !== state.pending.id),
    draft: state.pending.text,
    note: safeText(note, 240) || 'That message did not get through. Your draft is safe to send again.',
    busy: false,
    pending: null,
  }
}

const SKILL_ACTION_KEYS = ['enabled', 'id', 'kind', 'reason', 'request']

function runnableSkillAction(action) {
  if (!action || typeof action !== 'object' || Array.isArray(action)
      || Object.keys(action).sort().join('|') !== SKILL_ACTION_KEYS.join('|')
      || action.kind !== 'skill' || action.enabled !== true || action.reason !== ''
      || typeof action.id !== 'string' || !/^[a-z][a-z0-9_]{0,79}$/.test(action.id)) return false
  const request = safeText(action.request, 200)
  return request === action.request && /^Run skill: .{1,160}\.$/u.test(request)
}

function skillNameFromRequest(request) {
  const match = /^Run skill: (.{1,160})\.$/u.exec(request)
  return match ? safeText(match[1], 160) : ''
}

function skillTurnStarted(state, operation) {
  return {
    transcript: [...(Array.isArray(state.transcript) ? state.transcript : []), {
      id: operation.id, who: 'you', text: operation.action.request,
    }],
    draft: typeof state.draft === 'string' ? state.draft : '',
    note: '', busy: true,
    pending: { id: operation.id, text: operation.action.request, kind: 'skill', skillId: operation.action.id },
  }
}

function skillTurnCompleted(state, operation, replyId) {
  if (!state || !state.pending || state.pending.kind !== 'skill' || state.pending.id !== operation.id) return state
  const name = skillNameFromRequest(operation.action.request)
  if (!name) return state
  return {
    transcript: [...state.transcript, { id: replyId, who: 'cordia', text: `${name} completed.` }],
    draft: state.draft, note: '', busy: false, pending: null,
  }
}

function skillTurnFailed(state, operation, note) {
  if (!state || !state.pending || state.pending.kind !== 'skill' || state.pending.id !== operation.id) return state
  return {
    transcript: state.transcript.filter((message) => message.id !== operation.id),
    draft: state.draft,
    note: safeText(note, 240) || 'That skill did not run. Review its prerequisites and try again.',
    busy: false,
    pending: null,
  }
}

function skillFailureCopy(kind) {
  if (kind === 'signed-out') return 'Your session ended. Sign in again before retrying this skill.'
  if (kind === 'offline') return 'The server is unreachable right now. Retry this skill when Cordia is available.'
  if (kind === 'rate-limit') return 'Skill limit reached. Wait a few minutes before retrying.'
  if (kind === 'gate') return 'Cordia\'s execution gate did not allow this skill. Review its prerequisites and try again.'
  return 'That skill did not run. Review its prerequisites and try again.'
}

export function createSkillInteractionController({
  executeSkill, errorKind, nextId, operation, updateState, refresh,
}) {
  function run(action) {
    if (!runnableSkillAction(action) || operation.current) return false
    const pending = { id: nextId(), action }
    operation.current = 'skill'
    updateState((state) => skillTurnStarted(state, pending))

    let execution
    try {
      execution = executeSkill(action.id)
    } catch (error) {
      execution = Promise.reject(error)
    }
    Promise.resolve(execution).then((response) => {
      if (!response || response.ok !== true) throw new Error('skill execution failed')
      updateState((state) => skillTurnCompleted(state, pending, nextId()))
      refresh()
    }).catch((error) => {
      updateState((state) => skillTurnFailed(state, pending, skillFailureCopy(errorKind(error))))
    }).finally(() => {
      operation.current = ''
    })
    return true
  }

  return { run }
}

export function isAssistantSendKey(event) {
  return Boolean(event && event.key === 'Enter' && !event.shiftKey
    && event.nativeEvent && !event.nativeEvent.isComposing && event.nativeEvent.keyCode !== 229)
}
