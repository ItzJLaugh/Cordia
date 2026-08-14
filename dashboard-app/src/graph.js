// Pure projection of the safe Alidora map contract into React Flow data.
// The renderer never receives canonical workspace state; it accepts only
// the endpoint's allow-listed nodes and references between those nodes.

export const COL_LEFT = 60
export const CARD_W = 210
export const MAX_CARD_H = 132
const ROW_GAP = 80

function stringField(value) {
  return typeof value === 'string' ? value : ''
}

function safeNodes(map) {
  if (!map || typeof map !== 'object' || !Array.isArray(map.nodes)) return []

  const seen = new Set()
  return map.nodes
    .filter((node) => node && typeof node === 'object')
    .map((node) => ({
      id: stringField(node.id),
      kind: stringField(node.kind),
      label: stringField(node.label),
      detail: stringField(node.detail),
      status: stringField(node.status),
    }))
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
      status: node.status,
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
    .map((edge) => ({ source: stringField(edge.from), target: stringField(edge.to) }))
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
