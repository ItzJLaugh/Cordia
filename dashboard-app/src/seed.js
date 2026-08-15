// The framework-driven starting point for a NEW workspace — Step 2's
// framework decides what lands on the canvas before a person touches it.
// Pure and dependency-free so the offline harness can prove that a
// systems-thinker's seed visibly differs from the generic one.
//
// Vocabulary comes from backend/dashboard/framework.py (8 keys, all always
// present) and the definition contract from backend/dashboard/types.py:
// every id here matches _ID_RE, every string stays inside the caps, and
// the shape round-trips validate_definition unchanged.

// approval_density → which steps start with a human interrupt.
function approvalFor(density, index, count) {
  if (density === 'checkpoint_every_step') return true
  if (density === 'agent_led') return false
  return index === count - 1            // checkpoint_final — the default
}

export function seedDefinition(framework) {
  const fw = framework || {}
  const agents = [
    { id: 'intake', name: 'Intake', role: 'clarify',
      instructions: 'Restate the request in your own words and list what you will do.' },
    { id: 'draft', name: 'Drafter', role: 'draft',
      instructions: 'Produce the result the person asked for, clearly written.' },
  ]
  if (fw.verification_nodes === true) {
    agents.push({ id: 'verify', name: 'Evidence check', role: 'verify',
                  instructions: 'Check the draft against its sources and cite the evidence for each claim.' })
  }
  const density = fw.approval_density
  const steps = agents.map((a, i) => ({
    id: `s${i + 1}`,
    agentId: a.id,
    toolIds: [],
    instruction: a.instructions,
    requiresApproval: approvalFor(density, i, agents.length),
  }))

  // surface: the lead pane the framework chose, themed by density/diagram
  // preference — the same spirit as the vanilla builder's defaults.
  const type = fw.lead_surface === 'canvas' ? 'graph_and_chat'
    : fw.lead_surface === 'dashboard' ? 'dashboard' : 'chat'
  const theme = fw.node_density === 'detailed' ? 'data'
    : fw.node_density === 'minimal' ? 'minimal'
    : fw.diagram_forward === 'graph_first' ? 'visual' : 'formal'

  return {
    agents,
    tools: [],
    workflow: { steps },
    surface: { type, theme },
  }
}

// node_density → how much of each card shows by default. Not part of the
// definition (presentation, not content) — the canvas holds it as UI
// state. 'detailed' shows full instructions, 'minimal' name-only,
// 'balanced' name + role.
export function cardDetailFor(framework) {
  const d = (framework || {}).node_density
  return d === 'detailed' || d === 'minimal' ? d : 'balanced'
}
