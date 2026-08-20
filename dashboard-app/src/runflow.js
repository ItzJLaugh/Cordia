// The pure half of the run flow — approval-interrupt arithmetic and the
// stateless continuation prompt. The server holds no run state (each
// POST /dashboard/run is one seam call), so honoring requiresApproval as
// an interrupt works by segmenting on the CLIENT: the runtime prompt
// already tells the model to stop at an approval step and produce the
// draft; approving sends a continuation that carries the draft forward,
// because a stateless second call has no memory of the first.

// How many approval pauses the SAVED definition holds — the run uses the
// stored row, so this must be counted on the saved definition, never the
// local draft.
export function approvalStops(definition) {
  const steps = (((definition || {}).workflow || {}).steps) || []
  let n = 0
  for (const s of steps) {
    if (s && typeof s === 'object' && Boolean(s.requiresApproval)) n += 1
  }
  return n
}

// The continuation input for one approval: the original request, the
// draft the run paused on, and the person's decision — everything the
// next stateless call needs, stated plainly.
export function continuationInput(originalInput, pausedOutput) {
  return (
    `${originalInput}\n\n` +
    '--- approval checkpoint ---\n' +
    'The run paused at a step that requires the person\'s approval. ' +
    'The draft produced so far:\n\n' +
    `${pausedOutput}\n\n` +
    'The person reviewed this draft and approved it. Continue from the ' +
    'approval checkpoint and complete the remaining steps.'
  )
}

// Cap the continuation to the run-input limit the server enforces. The
// checkpoint scaffolding must ALWAYS survive — a final tail-slice once
// cut it off entirely for long inputs, turning the "continuation" into a
// byte-identical re-run of the original task. So the budget is allocated
// up front (request keeps at most two-thirds, the draft gets the rest,
// both trimmed with visible markers) and the result is bounded by
// construction — there is no closing slice to lose the scaffolding to.
export const MAX_RUN_INPUT = 6000

// A slice at a code-unit boundary can split a surrogate pair; the lone
// high surrogate then fails to encode server-side and the whole run
// request dies. Back the cut off one unit when it lands mid-pair.
function safeSlice(s, n) {
  if (s.length <= n) return s
  let end = n
  const last = s.charCodeAt(end - 1)
  if (last >= 0xD800 && last <= 0xDBFF) end -= 1
  return s.slice(0, Math.max(0, end))
}

export function boundedContinuation(originalInput, pausedOutput) {
  const full = continuationInput(originalInput, pausedOutput)
  if (full.length <= MAX_RUN_INPUT) return full
  const overhead = continuationInput('', '').length
  const budget = MAX_RUN_INPUT - overhead - 64   // headroom for the markers
  // The request is trimmed only as far as the draft actually needs the
  // room — a tiny draft must not cost the person two-thirds of a long
  // request — and never below one third of the budget.
  let req = originalInput
  const reqMax = Math.max(
    Math.floor(budget / 3),
    Math.min(req.length, budget - pausedOutput.length - 40),
    Math.min(req.length, Math.floor((budget * 2) / 3)),
  )
  if (req.length > reqMax) {
    req = `${safeSlice(req, reqMax)}\n[request shortened to fit]`
  }
  const draftMax = Math.max(1, budget - req.length)
  let draft = pausedOutput
  if (draft.length > draftMax) {
    draft = `${safeSlice(draft, draftMax)}\n[draft shortened to fit]`
  }
  return continuationInput(req, draft)
}
