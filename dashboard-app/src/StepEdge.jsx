import { BaseEdge, EdgeLabelRenderer } from '@xyflow/react'

// Thin renderer over the route skeleton graph.js computes (pure and
// offline-testable there — this file holds no geometry decisions beyond
// assembling points and rounding corners). Left/right handles only:
// top/bottom handles made React Flow drop every edge silently, and
// runtime measurement raced its own first render — both bisected, which
// is why the skeleton is static arithmetic on row geometry.
//
// Labels ride the crossing segment of THEIR OWN route via
// EdgeLabelRenderer with a stacking context — "Your approval" stays
// unmistakable everywhere, and lanes are unique per band by allocation,
// so no two labels can stack.

const CORNER = 14

function ortho(points) {
  let d = `M ${points[0][0]},${points[0][1]}`
  for (let i = 1; i < points.length - 1; i++) {
    const [px, py] = points[i - 1]
    const [cx, cy] = points[i]
    const [nx, ny] = points[i + 1]
    const inX = Math.sign(cx - px)
    const inY = Math.sign(cy - py)
    const outX = Math.sign(nx - cx)
    const outY = Math.sign(ny - cy)
    const beforeX = cx - inX * Math.min(CORNER, Math.abs(cx - px) / 2)
    const beforeY = cy - inY * Math.min(CORNER, Math.abs(cy - py) / 2)
    const afterX = cx + outX * Math.min(CORNER, Math.abs(nx - cx) / 2)
    const afterY = cy + outY * Math.min(CORNER, Math.abs(ny - cy) / 2)
    d += ` L ${beforeX},${beforeY} Q ${cx},${cy} ${afterX},${afterY}`
  }
  const [lx, ly] = points[points.length - 1]
  return d + ` L ${lx},${ly}`
}

export default function StepEdge({
  id, sourceX, sourceY, targetX, targetY, data, markerEnd,
}) {
  const route = (data && data.route) || null
  const requiresApproval = Boolean(data && data.requiresApproval)

  let path
  let labelX
  let labelY
  if (route && route.kind === 'return') {
    path = ortho([
      [sourceX, sourceY],
      [route.railOut, sourceY],
      [route.railOut, route.dropY],
      [route.railBack, route.dropY],
      [route.railBack, targetY],
      [targetX, targetY],
    ])
    // The label rides the DROP LEG — the lane-allocated segment — exactly
    // like the down family rides its crossing. That makes pill separation
    // one global argument: every pill sits at laneY - 13, lane y-values
    // are ≥ 26px apart within a band and bands are disjoint, and 26px
    // exceeds the 22px pill box. (The first version rode the rail
    // midpoint, where measured collisions reached Δy=0.)
    labelX = (route.railOut + route.railBack) / 2
    labelY = route.dropY - 13
  } else if (route) {
    path = ortho([
      [sourceX, sourceY],
      [route.railR, sourceY],
      [route.railR, route.crossY],
      [route.railL, route.crossY],
      [route.railL, targetY],
      [targetX, targetY],
    ])
    labelX = (route.railR + route.railL) / 2
    labelY = route.crossY - 13
  } else {
    // No skeleton (unvalidated data fed straight to as_graph consumers):
    // a plain right-angle drop is honest enough to not lie about order.
    path = `M ${sourceX},${sourceY} L ${targetX - 40},${sourceY} L ${targetX - 40},${targetY} L ${targetX},${targetY}`
    labelX = targetX - 40
    labelY = (sourceY + targetY) / 2
  }

  return (
    <>
      <BaseEdge id={id} path={path} markerEnd={markerEnd} />
      {requiresApproval && (
        <EdgeLabelRenderer>
          <div
            className="edge-label-pill"
            style={{ transform: `translate(-50%, -50%) translate(${labelX}px, ${labelY}px)` }}
          >
            Your approval
          </div>
        </EdgeLabelRenderer>
      )}
    </>
  )
}
