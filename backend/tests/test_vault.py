#!/usr/bin/env python3
"""Behavior tests for Cordia's encrypted connector-secret boundary."""
import os
import sys
import unittest

from cryptography.fernet import Fernet

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import vault


class TestVault(unittest.TestCase):
    def test_encrypts_and_recovers_a_secret_without_echoing_it_in_reference(self):
        secret = "github_pat_example_secret"
        sealed = vault.Vault(Fernet.generate_key())

        ref, ciphertext = sealed.seal("github", secret)

        self.assertTrue(ref.startswith("secret_github_"))
        self.assertNotIn(secret, ref)
        self.assertNotIn(secret.encode(), ciphertext)
        self.assertEqual(sealed.open(ciphertext), secret)

    def test_rejects_an_invalid_master_key(self):
        with self.assertRaisesRegex(vault.VaultUnavailable, "valid CORDIA_VAULT_KEY"):
            vault.from_environment({"CORDIA_VAULT_KEY": "not-a-fernet-key"})

    def test_rejects_an_empty_secret(self):
        sealed = vault.Vault(Fernet.generate_key())
        with self.assertRaisesRegex(ValueError, "empty"):
            sealed.seal("github", "")


if __name__ == "__main__":
    unittest.main()
