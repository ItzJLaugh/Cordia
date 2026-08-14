"""Authenticated encryption for connector secrets, returning opaque references."""

from __future__ import annotations

import os
import secrets

from cryptography.fernet import Fernet, InvalidToken


class VaultUnavailable(RuntimeError):
    pass


class Vault:
    def __init__(self, key: bytes | str):
        try:
            self._fernet = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise VaultUnavailable("A valid CORDIA_VAULT_KEY Fernet key is required.") from exc

    def seal(self, connector: str, value: str) -> tuple[str, bytes]:
        value = (value or "").strip()
        if not value:
            raise ValueError("Connector secret is empty.")
        clean_connector = "".join(c for c in connector.lower() if c.isalnum() or c == "_")
        if not clean_connector:
            raise ValueError("Connector name is invalid.")
        ref = "secret_%s_%s" % (clean_connector, secrets.token_hex(8))
        return ref, self._fernet.encrypt(value.encode("utf-8"))

    def open(self, ciphertext: bytes | str) -> str:
        try:
            return self._fernet.decrypt(ciphertext).decode("utf-8")
        except (InvalidToken, UnicodeDecodeError) as exc:
            raise VaultUnavailable("Stored connector secret could not be decrypted.") from exc


def from_environment(env=None) -> Vault:
    key = (env if env is not None else os.environ).get("CORDIA_VAULT_KEY", "")
    if not key:
        raise VaultUnavailable("CORDIA_VAULT_KEY must be configured before storing connector secrets.")
    return Vault(key)
