"""Small inspectable skill manifests that compose typed Cordia capabilities."""
from __future__ import annotations

from copy import deepcopy
import re

from . import adaptation, capability_gateway


_SKILLS = {
    'github_repository_review': {
        'name': 'Review GitHub repositories',
        'summary': 'Collect repository metadata for a workspace review.',
        'required_connectors': ['github'],
        'required_capabilities': ['github.read_repositories'],
        'permission': 'ALLOW',
    },
    'local_git_status_wait': {
        'name': 'Check local Git status',
        'summary': 'Inspect or recheck a user-selected local Git repository.',
        'required_connectors': ['desktop.local_repository'],
        'required_capabilities': ['desktop.git.status', 'desktop.git.wait'],
        'permission': 'ALLOW',
    },
    'local_git_pull': {
        'name': 'Pull local Git repository',
        'summary': 'Pull a selected local Git repository after approval.',
        'required_connectors': ['desktop.local_repository'],
        'required_capabilities': ['desktop.git.pull'],
        'permission': 'ASK',
    },
    'local_git_push': {
        'name': 'Push local Git repository',
        'summary': 'Push a selected local Git repository after approval.',
        'required_connectors': ['desktop.local_repository'],
        'required_capabilities': ['desktop.git.push'],
        'permission': 'ASK',
    },
}

_SAFE_CONTEXT_KEY = re.compile(r'^[a-z][a-z0-9_]*$')
_SAFE_TAG = re.compile(r'[a-z][a-z0-9_-]{0,31}')


def describe(skill_id):
    skill = _SKILLS.get(str(skill_id or ''))
    return deepcopy(skill) if skill else None


def catalog():
    return deepcopy(_SKILLS)


def recommendation_context(profile, connector_states):
    """Build bounded routing input without returning profile text or machine data."""
    profile = profile if isinstance(profile, dict) else {}
    states = connector_states if isinstance(connector_states, dict) else {}
    mode = adaptation.effective_mode(profile)
    context = {
        'connector_states': {name: state for name, state in states.items()
                             if isinstance(name, str) and state == 'confirmed'},
        'capability_states': _available_capabilities(states),
        'personalization_mode': mode,
    }
    if mode == 'off':
        return context
    context.update({
        'mission_tags': _profile_tags(profile),
        'evidence': _profile_evidence(profile),
        'preference_tags': [],
    })
    return context


def _available_capabilities(connector_states):
    return {name: 'confirmed' for name, capability in capability_gateway.catalog().items()
            if connector_states.get(capability['connector']) == 'confirmed'}


def _profile_tags(profile):
    signals = profile.get('signals') if isinstance(profile.get('signals'), dict) else {}
    values = list(signals.values())
    freeform = profile.get('freeform') if isinstance(profile.get('freeform'), dict) else {}
    values.extend(freeform.values())
    tags = set()
    for value in values:
        if isinstance(value, str):
            tags.update(_SAFE_TAG.findall(value.lower()))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    tags.update(_SAFE_TAG.findall(item.lower()))
    return sorted(tags)


def _profile_evidence(profile):
    evidence = {}
    for item in profile.get('evidence') if isinstance(profile.get('evidence'), list) else []:
        if not isinstance(item, dict):
            continue
        category = item.get('category', item.get('criterion'))
        if isinstance(category, str) and _SAFE_CONTEXT_KEY.fullmatch(category):
            evidence[category] = ['present']
    return evidence


def execute(skill_id, connector_states, capability_executor):
    """Run only the single typed capability declared by a registered skill."""
    skill = describe(skill_id)
    if not skill:
        return {'ok': False, 'error': 'skill is not registered'}
    required = skill.get('required_capabilities') or []
    if len(required) != 1:
        return {'ok': False, 'error': 'skill has no executable capability'}
    gate = capability_gateway.execute(
        required[0], connector_states,
        lambda: capability_executor(required[0]),
    )
    if not gate.get('ok'):
        return {'ok': False, 'skill': skill, **gate}
    outcome = gate['result']
    if not outcome.get('ok'):
        return {'ok': False, 'skill': skill, **outcome}
    return {'ok': True, 'skill': skill, 'result': outcome.get('result')}
