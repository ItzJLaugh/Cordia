#!/usr/bin/env python3
"""Human-in-the-loop approval policy.

NOT IMPLEMENTED IN MVP. EXTENSION POINT ONLY.

In the MVP, `requiresApproval` on a workflow step is honoured by the runtime
prompt (produce the draft, then stop) and surfaced in the UI as a notice. There
is no durable pause, no approval record, and no resume — the run completes in
one call.

When this is built it needs: a persisted pending-approval record keyed to the
run, a reviewer identity, an audit trail of what was approved and by whom, and a
resume path. `surveyor_runs.meta` is the natural place to anchor that, and the
existing `outcomes` table already carries the outcome_worked column for whether
the approved action turned out to be right.

    def requires_approval(step: dict, context: dict) -> bool
    def record_decision(run_id, step_id, approver, approved: bool, note: str) -> None
"""

from __future__ import annotations


def available() -> bool:
    return False


def requires_approval(step, context=None):
    """MVP behaviour: honour the flag on the step, nothing more."""
    return bool((step or {}).get("requiresApproval"))


def record_decision(run_id, step_id, approver, approved, note=""):
    raise NotImplementedError(
        "Approval records are an extension point, not implemented in the MVP.")
