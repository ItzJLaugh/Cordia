"""Validate corrections that should change Cordia's next compiled mission."""
from __future__ import annotations

from datetime import datetime, timezone

from . import fde_registry


CATEGORIES = {
    'missing_context', 'wrong_audience', 'too_generic', 'needs_evidence',
    'wrong_format', 'wrong_constraint', 'unsafe_to_automate',
    'needs_human_checkpoint',
}
OUTCOMES = {'useful', 'not_useful'}


def build(category, correction, effect):
    """Return a safe, bounded correction record or None when incomplete."""
    category = str(category or '').strip()
    correction = str(correction or '').strip()[:600]
    effect = str(effect or '').strip()[:600]
    if category not in CATEGORIES or not correction or not effect:
        return None
    return {'date': datetime.now(timezone.utc).date().isoformat(),
            'category': category, 'correction': correction, 'effect': effect}


def build_outcome(record_id, outcome):
    """Return a safe outcome event for one known FDE registry record."""
    record_id = str(record_id or '').strip()
    outcome = str(outcome or '').strip()
    if outcome not in OUTCOMES or not fde_registry.describe(record_id):
        return None
    return {'date': datetime.now(timezone.utc).date().isoformat(),
            'record_id': record_id, 'outcome': outcome}
