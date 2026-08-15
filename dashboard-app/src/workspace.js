import { isSafeIdentifier, isSensitiveText } from './identifier.js'

const CONNECTOR_ENUMS = {
  consent: new Set(['confirmed', 'suggested']),
  implementation: new Set(['live', 'planned']),
  lifecycle: new Set(['proposed', 'needs_handoff', 'live', 'failed']),
  runtime: new Set(['not_observed', 'live', 'needs_attention']),
}

const EMPTY_MODEL = () => ({
  artifactCards: [],
  workflowRows: [],
  connectors: [],
  viewMode: { default: 'dash', liveAvailable: false },
})

function safeIdentifier(value) {
  return isSafeIdentifier(value) ? value : ''
}

function safeLabel(value) {
  if (typeof value !== 'string' || value.length > 160 || isSensitiveText(value)) {
    return ''
  }
  return /^[\x20-\x7e]+$/.test(value) ? value : ''
}

function connectorRecord(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const connector = {
    id: safeIdentifier(value.id),
    consent: typeof value.status === 'string' ? value.status : '',
    implementation: typeof value.implementation_status === 'string' ? value.implementation_status : '',
    lifecycle: typeof value.lifecycle === 'string' ? value.lifecycle : '',
    runtime: value.runtime_status === undefined ? 'not_observed' : value.runtime_status,
  }
  return connector.id && Object.entries(CONNECTOR_ENUMS).every(([field, allowed]) => allowed.has(connector[field]))
    ? connector
    : null
}

function stableUnique(records, key) {
  const selected = new Map()
  for (const record of records.sort((left, right) => JSON.stringify(left).localeCompare(JSON.stringify(right)))) {
    if (!selected.has(record[key])) selected.set(record[key], record)
  }
  return [...selected.values()].sort((left, right) => left[key].localeCompare(right[key]))
}

function connectorsFrom(workspace) {
  const raw = Array.isArray(workspace.connectors) ? workspace.connectors : []
  return stableUnique(raw.map(connectorRecord).filter(Boolean), 'id')
}

function viewMode(window) {
  const liveAvailable = window.live_view_supported === true && window.live_view_enabled === true
  return { default: 'dash', liveAvailable }
}

function cardsFrom(workspace, connectors) {
  const connectorById = new Map(connectors.map((connector) => [connector.id, connector]))
  const raw = Array.isArray(workspace.windows) ? workspace.windows : []
  const cards = raw
    .filter((window) => window && typeof window === 'object' && !Array.isArray(window))
    .map((window) => {
      const id = safeIdentifier(window.id)
      const kind = safeIdentifier(window.kind)
      const title = safeLabel(window.title)
      if (!id || !kind || !title) return null
      const connector = connectorById.get(safeIdentifier(window.connector_id))
      return {
        id,
        kind,
        title,
        viewMode: viewMode(window),
        ...(connector ? { connector } : {}),
      }
    })
    .filter(Boolean)
  return stableUnique(cards, 'id')
}

function workflowRowsFrom(workspace) {
  const steps = workspace.workflow && typeof workspace.workflow === 'object' && Array.isArray(workspace.workflow.steps)
    ? workspace.workflow.steps
    : []
  const rows = steps
    .filter((step) => step && typeof step === 'object' && !Array.isArray(step))
    .map((step) => {
      const id = safeIdentifier(step.id)
      const agentId = safeIdentifier(step.agentId)
      const skillIds = Array.isArray(step.toolIds)
        ? [...new Set(step.toolIds.map(safeIdentifier).filter(Boolean))].sort((left, right) => left.localeCompare(right))
        : []
      return id && agentId ? { id, agentId, skillIds, requiresApproval: step.requiresApproval === true } : null
    })
    .filter(Boolean)
  return stableUnique(rows, 'id')
}

// This is a pure, renderer-safe adapter for the canonical /surveyor/workspace response.
// It deliberately performs no transport, persistence, permission decision, or execution.
export function workspaceToRendererModel(response) {
  if (!response || typeof response !== 'object' || Array.isArray(response) || response.ok !== true || !response.workspace || typeof response.workspace !== 'object' || Array.isArray(response.workspace)) {
    return EMPTY_MODEL()
  }

  const workspace = response.workspace
  const connectors = connectorsFrom(workspace)
  const artifactCards = cardsFrom(workspace, connectors)
  return {
    artifactCards,
    workflowRows: workflowRowsFrom(workspace),
    connectors,
    viewMode: {
      default: 'dash',
      liveAvailable: artifactCards.some((card) => card.viewMode.liveAvailable),
    },
  }
}
