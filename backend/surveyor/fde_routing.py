"""Deterministic, advisory recommendations over the safe FDE registry."""
from __future__ import annotations

from copy import deepcopy
import re

from . import fde_registry


_MAX_CANDIDATES = 5
_CONFIRMED = {'confirmed'}
_SAFE_EVIDENCE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$')


def recommend(context, limit=5):
    """Return safe, non-executable recommendations and blocked prerequisites.

    Context may carry mission tags, connector and capability states, evidence,
    preference tags, and a personalization mode.  Only explicit values affect
    ranking; outcome events are deliberately not used in this first slice.
    """
    context = context if isinstance(context, dict) else {}
    mode = context.get('personalization_mode', 'simple')
    personalization_off = mode == 'off'
    mission_tags = _strings(context.get('mission_tags', context.get('tags', [])))
    preference_tags = [] if personalization_off else _strings(
        context.get('preference_tags', context.get('preferences', [])))
    connectors = context.get('connector_states') if isinstance(context.get('connector_states'), dict) else {}
    evidence = _evidence(context.get('evidence', context.get('evidence_categories', {})))
    capability_states = context.get('capability_states', context.get('capabilities'))

    candidates, blocked = [], []
    for record in _records():
        prerequisites = _blocked_prerequisites(record, connectors, evidence, capability_states)
        if prerequisites:
            blocked.append({'id': record['id'], 'blocked_prerequisites': prerequisites})
            continue
        candidates.append(_recommendation(record, mission_tags, evidence, preference_tags,
                                          personalization_off))

    candidates.sort(key=lambda item: (-item['score_breakdown']['score'], item['id']))
    blocked.sort(key=lambda item: item['id'])
    return {'recommendations': candidates[:_limit(limit)], 'blocked': blocked}


def _records():
    return list(fde_registry.catalog().values())


def _blocked_prerequisites(record, connectors, evidence, capability_states):
    blocked = []
    if record.get('permission') == 'DENY':
        blocked.append('permission: DENY')
    for capability in record.get('required_capabilities', []):
        if not _capability_available(capability, capability_states):
            blocked.append('capability: ' + capability)
    for connector in record.get('required_connectors', []):
        if str(connectors.get(connector, '')).lower() not in _CONFIRMED:
            blocked.append('connector: ' + connector)
    for category in record.get('required_evidence', []):
        if not evidence.get(category):
            blocked.append('evidence: ' + category)
    return blocked


def _capability_available(capability, states):
    if states is None:
        return False
    if isinstance(states, dict):
        value = states.get(capability)
        return value is True or str(value).lower() in {'available', 'confirmed'}
    return capability in _strings(states)


def _recommendation(record, mission_tags, evidence, preference_tags, personalization_off):
    tags = _strings(record.get('tags', []))
    matched_mission = sorted(set(tags) & set(mission_tags))
    matched_evidence = {category: evidence[category] for category in record.get('required_evidence', [])
                        if evidence.get(category)}
    matched_preferences = sorted(set(tags) & set(preference_tags))
    breakdown = {
        'mission_relevance': min(len(matched_mission), 3),
        'evidence_support': 0 if personalization_off else min(len(matched_evidence), 2),
        'explicit_preference': min(len(matched_preferences), 2),
        'observed_success': 0,
        'risk_cost': 1 if record.get('permission') == 'ASK' else 0,
        'latency_cost': 1 if record.get('permission') == 'ASK' else 0,
    }
    breakdown['score'] = (breakdown['mission_relevance'] + breakdown['evidence_support']
                          + breakdown['explicit_preference'] + breakdown['observed_success']
                          - breakdown['risk_cost'] - breakdown['latency_cost'])
    why = []
    if matched_mission:
        why.append('Matched mission tags: ' + ', '.join(matched_mission) + '.')
    if matched_evidence and not personalization_off:
        why.append('Matched evidence: ' + ', '.join(sorted(matched_evidence)) + '.')
    if matched_preferences:
        why.append('Matched preference tags: ' + ', '.join(matched_preferences) + '.')
    return {
        'id': record['id'], 'kind': record['kind'], 'summary': record['summary'],
        'permission': record['permission'], 'maturity': record['maturity'],
        'why': why, 'matched_evidence': deepcopy(matched_evidence),
        'blocked_prerequisites': [], 'score_breakdown': breakdown,
    }


def _strings(value):
    if isinstance(value, str):
        return [value] if value else []
    return [item for item in value if isinstance(item, str) and item] if isinstance(value, (list, tuple, set)) else []


def _evidence(value):
    if isinstance(value, dict):
        evidence = {}
        for category, items in value.items():
            if not isinstance(category, str) or not category or items is None or items is False:
                continue
            if items is True:
                evidence[category] = ['present']
                continue
            identifiers = [item for item in _strings(items) if _SAFE_EVIDENCE_ID.fullmatch(item)]
            if identifiers:
                evidence[category] = identifiers[:_MAX_CANDIDATES]
        return evidence
    return {category: ['present'] for category in _strings(value)}


def _limit(value):
    try:
        return max(0, min(int(value), _MAX_CANDIDATES))
    except (TypeError, ValueError):
        return _MAX_CANDIDATES
