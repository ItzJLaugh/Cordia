// Definition -> React Flow projection, mirroring the backend's canonical
// reading (backend/dashboard/types.py as_graph): agents are nodes, each
// workflow step is the edge entering its agent — from the previous step's
// agent, or from the Start marker for the first step — and requiresApproval
// rides the edge it gates. Definitions arrive canonicalised from
// GET /dashboard/interface, but the projection still reads defensively:
// a partial result, never a throw.
//
// The projection also resolves dangling references with placeholder nodes,
// exactly as the backend does — the wild holds them (the builder's old
// re-slug bug), and a step must stay visible even when its agent record
// is gone.
//
// LAYOUT AND ROUTE SKELETONS LIVE HERE, pure and testable. One column,
// top to bottom — the same order the builder and the interface page list
// steps in (a snake grid was tried and kept manufacturing degenerate
// geometry). Every edge's rails and crossing lane are computed here as
// absolute coordinates:
//
//   * each row's card is height-bounded by CSS (MAX_CARD_H), and the BAND
//     above each row grows to hold one lane per horizontal segment that
//     must cross there — downward arrivals, self-loop crossings, and the
//     drop legs of returns from the row above. Unique lane per segment,
//     by allocation, not by modulo (adversarial review measured periodic
//     per-node fans drawing unrelated steps exactly on top of each
//     other), at a pitch wider than the approval pill so labels can
//     never stack;
//   * vertical rails are globally unique AND family-disjoint by modular
//     arithmetic: railR/railL sit on 12px-grid residue 0, the return
//     rails on residue 6 — the families can never alias.

export const START_ID = '__start__'

export const COL_LEFT = 60
export const CARD_W = 210
export const MAX_CARD_H = 132
const BAND_BASE = 58          // minimum air between rows
const LANE_STEP = 26          // vertical lane pitch — MUST exceed the
                              // approval pill box (~24px incl. margin), or
                              // pills on adjacent lanes occlude each other
const LANE_FIRST = 12         // first lane sits this far above a row top
const RAIL_R_BASE = COL_LEFT + CARD_W + 30
const RAIL_STEP = 12

export function definitionToFlow(definition) {
  const d = definition && typeof definition === 'object' ? definition : {}
  const agents = Array.isArray(d.agents) ? d.agents : []
  const workflow = d.workflow && typeof d.workflow === 'object' ? d.workflow : {}
  const steps = Array.isArray(workflow.steps) ? workflow.steps : []

  // ---- pass 1: node order (rows), no y yet -------------------------------
  const rowOf = new Map([[START_ID, 0]])
  const nodeSpecs = [{ id: START_ID, start: true }]
  for (const a of agents) {
    if (!a || typeof a !== 'object' || typeof a.id !== 'string' || !a.id) continue
    if (rowOf.has(a.id)) continue
    rowOf.set(a.id, nodeSpecs.length)
    nodeSpecs.push({
      id: a.id,
      name: typeof a.name === 'string' && a.name ? a.name : a.id,
      role: typeof a.role === 'string' && a.role ? a.role : 'custom',
      instructions: typeof a.instructions === 'string' ? a.instructions : '',
      placeholder: false,
    })
  }
  const validSteps = []
  steps.forEach((s, originalIndex) => {
    if (s && typeof s === 'object' && typeof s.agentId === 'string' && s.agentId) {
      validSteps.push({ s, originalIndex })
    }
  })
  for (const { s } of validSteps) {
    if (rowOf.has(s.agentId)) continue
    rowOf.set(s.agentId, nodeSpecs.length)
    nodeSpecs.push({
      id: s.agentId, name: s.agentId, role: 'custom',
      instructions: '', placeholder: true,
    })
  }

  // ---- pass 2: allocate one unique lane per horizontal segment -----------
  // laneCount[r] = lanes consumed in the band above row r. A downward edge
  // (or self-loop) crosses above its TARGET row; a return's drop leg
  // crosses above the row BELOW its source (or a synthetic row past the
  // last, where the canvas is open).
  const laneCount = new Array(nodeSpecs.length + 1).fill(0)
  const prelim = []
  let prev = START_ID
  for (const { s, originalIndex } of validSteps) {
    const target = s.agentId
    const srcRow = rowOf.get(prev)
    const tgtRow = rowOf.get(target)
    const upward = tgtRow < srcRow
    const bandRow = upward ? srcRow + 1 : tgtRow
    const lane = laneCount[bandRow]
    laneCount[bandRow] += 1
    prelim.push({ s, originalIndex, source: prev, target, upward, bandRow, lane })
    prev = target
  }

  // ---- pass 3: row tops from band sizes ----------------------------------
  const rowTop = new Array(nodeSpecs.length + 1)
  rowTop[0] = 60
  for (let r = 1; r <= nodeSpecs.length; r++) {
    // +14 headroom above the deepest lane: the pill rides 13px above
    // its crossing line and must clear the card above too.
    const band = Math.max(BAND_BASE, LANE_FIRST + laneCount[r] * LANE_STEP + 14)
    rowTop[r] = rowTop[r - 1] + MAX_CARD_H + band
  }

  const nodes = nodeSpecs.map((spec, r) =>
    spec.start
      ? {
          id: START_ID, type: 'cordiaStart',
          position: { x: COL_LEFT, y: rowTop[0] }, data: {}, draggable: false,
        }
      : {
          id: spec.id, type: 'cordiaAgent',
          position: { x: COL_LEFT, y: rowTop[r] },
          data: {
            name: spec.name, role: spec.role,
            instructions: spec.instructions, placeholder: spec.placeholder,
          },
        },
  )

  // ---- pass 4: absolute route skeletons ----------------------------------
  // rowTop[bandRow] is always defined: bandRow ≤ nodeSpecs.length, and the
  // pass above fills through that synthetic past-the-last-row index, so
  // returns out of the bottom row use the same lane formula as everything
  // else.
  const edges = prelim.map(({ s, originalIndex, source, target, upward, bandRow, lane }, i) => {
    const requiresApproval = Boolean(s.requiresApproval)
    const crossY = rowTop[bandRow] - LANE_FIRST - lane * LANE_STEP
    const route = upward
      ? {
          kind: 'return',
          // residue-6 offsets keep the return rails permanently disjoint
          // from the residue-0 railR/railL families for every i and lane —
          // exact aliasing at lane = i + 8 was measured before this.
          railOut: RAIL_R_BASE + 6 + i * RAIL_STEP,
          dropY: crossY,
          railBack: COL_LEFT - 126 - i * RAIL_STEP,
        }
      : {
          kind: 'down',
          railR: RAIL_R_BASE + i * RAIL_STEP,
          railL: COL_LEFT - 24 - lane * RAIL_STEP,
          crossY,
        }
    return {
      id: `step-${originalIndex}`,
      source, target,
      type: 'cordiaStep',
      animated: requiresApproval,
      className: requiresApproval ? 'edge-approval' : 'edge-flow',
      zIndex: requiresApproval ? 1 : 0,
      data: {
        step: originalIndex,
        instruction: typeof s.instruction === 'string' ? s.instruction : '',
        toolIds: Array.isArray(s.toolIds) ? s.toolIds : [],
        requiresApproval,
        route,
      },
    }
  })

  // The Start marker only earns its place when there is a flow to enter.
  return { nodes: edges.length ? nodes : nodes.slice(1), edges }
}
