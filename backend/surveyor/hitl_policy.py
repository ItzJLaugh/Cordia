"""Explicit, durable-state-ready approval checkpoints for consequential work."""
from __future__ import annotations

from datetime import datetime, timezone
import uuid


def available() -> bool:
    return True


def requires_approval(step, context=None):
    return bool((step or {}).get('requiresApproval'))


def create_checkpoint(run_id, step, summary):
    """Create the minimal safe record a store can persist, or None when unneeded."""
    if not requires_approval(step):
        return None
    return {'id': 'approval_' + uuid.uuid4().hex,
            'run_id': str(run_id), 'step_id': str((step or {}).get('id') or (step or {}).get('agentId') or ''),
            'summary': str(summary or '')[:1000], 'status': 'pending',
            'created': _now()}


def decide(checkpoint, approver, approved, note=''):
    """Return a terminal decision record; persistence is handled by the store."""
    if (checkpoint or {}).get('status') != 'pending':
        raise ValueError('Only a pending approval can be decided.')
    return {'id': checkpoint.get('id'), 'run_id': checkpoint.get('run_id'),
            'step_id': checkpoint.get('step_id'),
            'status': 'approved' if approved else 'declined',
            'approver': str(approver or ''), 'note': str(note or '')[:600],
            'decided': _now()}


def resume_instruction(checkpoint, decision):
    """Produce an opaque continuation reference only after recorded approval."""
    if (decision or {}).get('status') != 'approved':
        return None
    if not checkpoint or checkpoint.get('id') != decision.get('id'):
        return None
    if not checkpoint.get('run_id') or not checkpoint.get('step_id'):
        return None
    return {'approval_id': checkpoint.get('id'), 'run_id': checkpoint.get('run_id'),
            'step_id': checkpoint.get('step_id')}


def _now():
    return datetime.now(timezone.utc).isoformat()
