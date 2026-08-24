"""Non-secret deployment readiness checks for the Cordia workspace runtime."""
from __future__ import annotations

import os

from surveyor import model_provider


REQUIRED = ('CORDIA_PG_DSN', 'CORDIA_VAULT_KEY')
EMAIL_2FA_REQUIREMENT = 'GMAIL_USER/GMAIL_APP_PASSWORD or CORDIA_DEV_2FA=1'
# `training_backend.py` imports this research-only shadow scorer softly. Report
# its availability for operators without letting it block live workspace
# readiness, because rubric scoring remains authoritative when it is absent.
BACKEND_RUNTIME_DEPENDENCIES = ('numpy', 'sentence_transformers', 'faiss')


def health_view(result):
    """Public-safe readiness projection: never disclose deployment details."""
    return {'ok': bool((result or {}).get('ok'))}


def report(environment=None, has_cryptography=None, has_psycopg2=None,
           database_ready=None, dependency_available=None):
    environment = environment if environment is not None else os.environ
    missing = [name for name in REQUIRED if not str(environment.get(name) or '').strip()]
    provider_status = model_provider.status(environment)
    if not provider_status['configured']:
        missing.append('OpenAI model provider')
    has_email_2fa = (str(environment.get('CORDIA_DEV_2FA') or '') == '1' or
                     (str(environment.get('GMAIL_USER') or '').strip() and
                      str(environment.get('GMAIL_APP_PASSWORD') or '').strip()))
    if not has_email_2fa:
        missing.append(EMAIL_2FA_REQUIREMENT)
    if has_cryptography is None:
        try:
            import cryptography  # noqa: F401
            has_cryptography = True
        except ImportError:
            has_cryptography = False
    if not has_cryptography:
        missing.append('cryptography')
    if has_psycopg2 is None:
        try:
            import psycopg2  # noqa: F401
            has_psycopg2 = True
        except ImportError:
            has_psycopg2 = False
    if not has_psycopg2:
        missing.append('psycopg2')
        database_ready = False
    if dependency_available is None:
        def dependency_available(module):
            try:
                __import__(module)
                return True
            except ImportError:
                return False
    dependency_checks = {module: bool(dependency_available(module))
                         for module in BACKEND_RUNTIME_DEPENDENCIES}
    optional_missing = [module for module, available in dependency_checks.items()
                        if not available]
    dsn = str(environment.get('CORDIA_PG_DSN') or '').strip()
    if database_ready is None and dsn and has_psycopg2:
        try:
            import psycopg2
            with psycopg2.connect(dsn, connect_timeout=3):
                database_ready = True
        except Exception:
            database_ready = False
    if database_ready is False:
        missing.append('PostgreSQL connection')
    return {'ok': not missing, 'missing': missing, 'optional_missing': optional_missing,
            'checks': {name: name not in missing for name in REQUIRED} |
                      {'model_provider': provider_status,
                       'cryptography': bool(has_cryptography),
                       'psycopg2': bool(has_psycopg2),
                       **dependency_checks,
                       'postgres_connection': database_ready is not False}}


if __name__ == '__main__':
    result = report()
    print('Cordia preflight: ' + ('ready' if result['ok'] else 'missing ' + ', '.join(result['missing'])))
    raise SystemExit(0 if result['ok'] else 1)
