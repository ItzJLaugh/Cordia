// Pure projection of the safe Alidora map contract into React Flow data.
// The renderer never receives canonical workspace state; it accepts only
// the endpoint's allow-listed nodes and references between those nodes.

export const COL_LEFT = 60
export const CARD_W = 210
export const MAX_CARD_H = 180
const ROW_GAP = 80
const NODE_KINDS = new Set(['agent', 'skill', 'connector'])
const SAFE_NODE_ID = /^[A-Za-z0-9][A-Za-z0-9._:-]{0,95}$/
const CREDENTIAL_PREFIX = /^(?:token|authorization|password|secret|credential|api[_-]?key)\s*[:=]/i
const SECRET_OR_PATH = /(?:[A-Za-z]:\\|\\\\[^\s]+\\|\/(?:home|root|Users)\/|\b(?:token|secret|password|credential|authorization|bearer|api[_-]?key)\b\s*[:=]|\b(?:ghp_|github_pat_|xox[baprs]-|sk-)[A-Za-z0-9_-]{8,})/i
const CONNECTOR_ENUMS = {
  consent: new Set(['confirmed', 'suggested']),
  implementation: new Set(['live', 'planned']),
  lifecycle: new Set(['proposed', 'needs_handoff', 'live', 'failed']),
  runtime: new Set(['not_observed', 'live', 'needs_attention']),
}

function stringField(value) {
  return typeof value === 'string' ? value : ''
}

function safeIdentifier(value) {
  return typeof value === 'string' && SAFE_NODE_ID.test(value) && !CREDENTIAL_PREFIX.test(value) ? value : ''
}

function safeDisplayText(value, limit) {
  if (typeof value !== 'string') return ''
  const text = value.trim()
  return text.length <= limit
    && !/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(text)
    && !SECRET_OR_PATH.test(text) ? text : ''
}

function connectorStatus(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  const status = {
    consent: stringField(value.consent),
    implementation: stringField(value.implementation),
    lifecycle: stringField(value.lifecycle),
    runtime: stringField(value.runtime),
  }
  return Object.entries(CONNECTOR_ENUMS).every(([field, allowed]) => allowed.has(status[field]))
    ? status
    : null
}

function safeNodes(map) {
  if (!map || typeof map !== 'object' || !Array.isArray(map.nodes)) return []

  const seen = new Set()
  return map.nodes
    .filter((node) => node && typeof node === 'object')
    .map((node) => ({
      id: safeIdentifier(node.id),
      kind: NODE_KINDS.has(node.kind) ? node.kind : '',
      label: safeDisplayText(node.label, 160),
      detail: safeDisplayText(node.detail, 400),
      connectorStatus: connectorStatus(node.connector_status),
    }))
    .filter((node) => node.id && node.kind)
    .filter((node) => node.kind !== 'connector' || node.connectorStatus)
    .filter((node) => node.id && !seen.has(node.id) && (seen.add(node.id), true))
    .sort((left, right) => left.id.localeCompare(right.id))
}

// Return a static graph only. Neither map metadata nor unknown server fields
// cross this boundary, and React Flow receives no editable node state.
export function alidoraMapToFlow(map) {
  const safe = safeNodes(map)
  const nodeIds = new Set(safe.map((node) => node.id))
  const nodes = safe.map((node, index) => ({
    id: node.id,
    type: 'alidoraNode',
    position: { x: COL_LEFT, y: 60 + index * (MAX_CARD_H + ROW_GAP) },
    data: {
      kind: node.kind,
      label: node.label,
      detail: node.detail,
      ...(node.connectorStatus ? { connectorStatus: node.connectorStatus } : {}),
    },
    draggable: false,
    connectable: false,
    deletable: false,
    selectable: false,
  }))

  const rawEdges = map && typeof map === 'object' && Array.isArray(map.edges)
    ? map.edges
    : []
  const edgeIds = new Set()
  const edges = rawEdges
    .filter((edge) => edge && typeof edge === 'object')
    .map((edge) => ({ source: safeIdentifier(edge.from), target: safeIdentifier(edge.to) }))
    .filter(({ source, target }) => {
      const id = `${source}\u0000${target}`
      if (!source || !target || !nodeIds.has(source) || !nodeIds.has(target) || edgeIds.has(id)) {
        return false
      }
      edgeIds.add(id)
      return true
    })
    .sort((left, right) => (
      left.source.localeCompare(right.source) || left.target.localeCompare(right.target)
    ))
    .map(({ source, target }) => ({
      id: `alidora:${source}:${target}`,
      source,
      target,
      deletable: false,
      selectable: false,
      focusable: false,
      reconnectable: false,
    }))

  return { nodes, edges }
}
