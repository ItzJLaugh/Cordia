// Pure structural edits over an Interface Definition — the only writers
// the canvas has. Every function returns a NEW definition (no mutation)
// or null when the edit would break the write contract (caps from
// backend/dashboard/types.py) — the caller shows copy, the server is
// never asked to refuse what the client can already see.
//
// Two rules the whole file honours:
//   * ids are immutable once minted — re-slugging an id from an edited
//     display name is the builder bug this repo already fixed once;
//   * the workflow is an ORDERED LIST, not an edge set: edge k means
//     "step k runs on target after step k-1's agent" — so inserting and
//     deleting relink neighbours, and callers must re-project wholesale.

export const MAX_ITEMS = 200
export const MAX_INSTRUCTION = 10000
export const MAX_TEXT = 400

const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._-]{0,199}$/

function clone(definition) {
  return JSON.parse(JSON.stringify(definition))
}

function usedIds(list) {
  const out = new Set()
  for (const item of list || []) {
    if (item && typeof item.id === 'string') out.add(item.id)
  }
  return out
}

// Mint `prefix1`, `prefix2`, … skipping anything already declared —
// stable, _ID_RE-safe, and never reuses a live id.
export function mintId(prefix, taken) {
  for (let n = 1; ; n++) {
    const candidate = `${prefix}${n}`
    if (!taken.has(candidate)) return candidate
  }
}

export function addAgent(definition) {
  const d = clone(definition)
  d.agents = Array.isArray(d.agents) ? d.agents : []
  if (d.agents.length >= MAX_ITEMS) return null
  // Taken ids include what STEPS reference, not just declared agents — a
  // dangling step referencing "agent1" would otherwise be hijacked by the
  // new blank agent the moment it minted that id.
  const taken = usedIds(d.agents)
  for (const s of ((d.workflow || {}).steps) || []) {
    if (s && typeof s.agentId === 'string') taken.add(s.agentId)
  }
  const id = mintId('agent', taken)
  d.agents.push({ id, name: 'New agent', role: 'custom', instructions: '' })
  return { definition: d, id }
}

// A dashed placeholder is a step whose agent record is gone (the wild
// holds them). Declaring it turns the reference into a real agent with
// the SAME id — never a re-mint, so every step keeps pointing at it.
export function declareAgent(definition, agentId) {
  if (typeof agentId !== 'string' || !ID_RE.test(agentId)) return null
  const d = clone(definition)
  d.agents = Array.isArray(d.agents) ? d.agents : []
  if (d.agents.length >= MAX_ITEMS) return null
  if (usedIds(d.agents).has(agentId)) return null
  d.agents.push({ id: agentId, name: agentId, role: 'custom', instructions: '' })
  return d
}

export function updateAgent(definition, agentIndex, fields) {
  const d = clone(definition)
  const agent = (d.agents || [])[agentIndex]
  if (!agent || typeof agent !== 'object') return null
  if ('name' in fields) agent.name = String(fields.name).slice(0, MAX_TEXT)
  if ('role' in fields) agent.role = String(fields.role).slice(0, MAX_TEXT)
  if ('instructions' in fields) {
    const text = String(fields.instructions)
    if (text.trim().length > MAX_INSTRUCTION) return null
    agent.instructions = text
  }
  return d
}

// Removing an agent also removes the steps that reference it — leaving
// them would re-mint the agent as a dashed placeholder and reshuffle the
// column, which reads as the delete half-working. The caller confirms
// when referencedSteps(definition, id) is non-empty.
export function removeAgent(definition, agentId) {
  const d = clone(definition)
  d.agents = (d.agents || []).filter((a) => !(a && a.id === agentId))
  const steps = ((d.workflow || {}).steps || [])
  d.workflow = { ...(d.workflow || {}), steps: steps.filter((s) => !(s && s.agentId === agentId)) }
  return d
}

export function referencedSteps(definition, agentId) {
  const steps = ((definition || {}).workflow || {}).steps || []
  return steps.reduce((n, s) => n + (s && s.agentId === agentId ? 1 : 0), 0)
}

// A→B on the canvas becomes "insert a step for B after A's LAST step"
// (after the start marker = index 0). "Last occurrence" is the one
// deterministic reading of an ambiguous gesture — the step editor can
// move it afterwards. A source that is not in the flow yet gets wired in
// FIRST: the drawn edge was A→B, and appending B after some other agent
// would render an edge the person never drew while leaving A orphaned.
export function insertStepAfter(definition, sourceId, targetId, requiresApproval) {
  const d = clone(definition)
  d.workflow = d.workflow && typeof d.workflow === 'object' ? d.workflow : {}
  const steps = Array.isArray(d.workflow.steps) ? d.workflow.steps : []
  let at = steps.length
  if (sourceId === '__start__') {
    at = 0
  } else {
    let found = -1
    for (let i = steps.length - 1; i >= 0; i--) {
      if (steps[i] && steps[i].agentId === sourceId) { found = i; break }
    }
    if (found >= 0) {
      at = found + 1
    } else {
      if (steps.length + 2 > MAX_ITEMS) return null
      steps.push({
        id: mintId('s', usedIds(steps)),
        agentId: sourceId,
        toolIds: [],
        instruction: '',
        // the caller's approval default applies to BOTH inserted steps —
        // a checkpoint-every-step workspace must not silently gain an
        // ungated step through the wiring half of the gesture
        requiresApproval: Boolean(requiresApproval),
      })
      at = steps.length
    }
  }
  if (steps.length >= MAX_ITEMS) return null
  const step = {
    id: mintId('s', usedIds(steps)),
    agentId: targetId,
    toolIds: [],
    instruction: '',
    requiresApproval: Boolean(requiresApproval),
  }
  steps.splice(at, 0, step)
  d.workflow.steps = steps
  return { definition: d, index: at }
}

export function updateStep(definition, index, fields) {
  const d = clone(definition)
  const step = (((d.workflow || {}).steps) || [])[index]
  if (!step || typeof step !== 'object') return null
  if ('instruction' in fields) {
    const text = String(fields.instruction)
    if (text.trim().length > MAX_INSTRUCTION) return null
    step.instruction = text
  }
  if ('requiresApproval' in fields) step.requiresApproval = Boolean(fields.requiresApproval)
  if ('toolIds' in fields && Array.isArray(fields.toolIds)) {
    if (fields.toolIds.length > MAX_ITEMS) return null
    step.toolIds = fields.toolIds.map(String)
  }
  return d
}

export function removeStep(definition, index) {
  const d = clone(definition)
  const steps = ((d.workflow || {}).steps) || []
  if (index < 0 || index >= steps.length) return null
  steps.splice(index, 1)
  d.workflow = { ...(d.workflow || {}), steps }
  return d
}
