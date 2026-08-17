"""Fail-closed filesystem locations shared by production and isolated checks."""

import os


DEFAULT_CORPUS_DIRECTORY = "/var/lib/cordia/corpus"


def corpus_directory(environment=None):
    """Use an explicit absolute override, otherwise retain the production default."""
    environment = os.environ if environment is None else environment
    configured = str(environment.get("CORDIA_CORPUS_DIR", "")).strip()
    return configured if configured and os.path.isabs(configured) else DEFAULT_CORPUS_DIRECTORY
