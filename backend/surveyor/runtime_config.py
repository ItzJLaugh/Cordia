"""Small, explicit runtime settings shared by local preview and production."""
from __future__ import annotations


def cookie_secure(environment=None):
    """Return the cookie attribute; production is secure unless explicitly local."""
    environment = environment or {}
    return '' if str(environment.get('CORDIA_COOKIE_SECURE', '1')) == '0' else 'Secure; '
