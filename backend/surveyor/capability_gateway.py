"""The allow-listed capability boundary between Cordia agents and connectors."""
from __future__ import annotations

from copy import deepcopy

from . import permissions


_CAPABILITIES = {
    'github.read_repositories': {
        'connector': 'github', 'permission': 'ALLOW', 'transport': 'direct_api',
        'summary': 'List repository metadata without exposing credentials.',
    },
    'desktop.git.status': {
        'connector': 'desktop.local_repository', 'permission': 'ALLOW', 'transport': 'local_bridge',
        'summary': 'Read the status of a user-selected local Git repository.',
    },
    'desktop.git.wait': {
        'connector': 'desktop.local_repository', 'permission': 'ALLOW', 'transport': 'local_bridge',
        'summary': 'Recheck the status of a user-selected local Git repository.',
    },
    'desktop.git.pull': {
        'connector': 'desktop.local_repository', 'permission': 'ASK', 'transport': 'local_bridge',
        'summary': 'Pull the selected local Git repository after fresh approval.',
    },
    'desktop.git.push': {
        'connector': 'desktop.local_repository', 'permission': 'ASK', 'transport': 'local_bridge',
        'summary': 'Push the selected local Git repository after fresh approval.',
    },
}


def describe(name):
    """Return a copy of one registered typed capability, never an arbitrary request."""
    capability = _CAPABILITIES.get(str(name or ''))
    return deepcopy(capability) if capability else None


def catalog():
    return deepcopy(_CAPABILITIES)


def execute(name, connector_states, operation):
    """Run only a registered capability after the shared permission gate allows it."""
    capability = describe(name)
    if not capability:
        return {'ok': False, 'error': 'capability is not registered'}
    gate = permissions.decide(name, connector_states)
    if gate['decision'] != 'ALLOW':
        return {'ok': False, 'capability': capability, 'permission': gate,
                'error': gate['reason']}
    return {'ok': True, 'capability': capability, 'permission': gate,
            'result': operation()}
