#!/usr/bin/env python3
"""Behavior tests for Cordia's first durable, read-only connector."""
import json
import os
import sys
import unittest
import urllib.error

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import github_connector, permissions


class TestPermissionGate(unittest.TestCase):
    def test_allows_reading_confirmed_github_repository_data(self):
        decision = permissions.decide("github.read_repositories", {"github": "confirmed"})
        self.assertEqual(decision["decision"], "ALLOW")

    def test_requires_approval_for_github_writes(self):
        decision = permissions.decide("github.create_issue", {"github": "confirmed"})
        self.assertEqual(decision["decision"], "ASK")

    def test_denies_secret_exposure(self):
        decision = permissions.decide("github.reveal_token", {"github": "confirmed"})
        self.assertEqual(decision["decision"], "DENY")


class TestGitHubConnector(unittest.TestCase):
    def test_lists_a_safe_native_repository_summary(self):
        seen = {}

        def transport(url, headers):
            seen.update(url=url, headers=headers)
            return [{"full_name": "ItzJLaugh/Cordia", "private": True,
                     "description": "Personal FDE", "html_url": "https://github.com/ItzJLaugh/Cordia",
                     "default_branch": "main", "updated_at": "2026-08-13T12:00:00Z"}]

        result = github_connector.list_repositories("secret-value", transport=transport)

        self.assertEqual(result["repositories"], [{
            "name": "ItzJLaugh/Cordia", "private": True, "description": "Personal FDE",
            "url": "https://github.com/ItzJLaugh/Cordia", "default_branch": "main",
            "updated_at": "2026-08-13T12:00:00Z"}])
        self.assertEqual(result["repository_limit"], 30)
        self.assertEqual(seen["url"], "https://api.github.com/user/repos?per_page=30&sort=updated")
        self.assertEqual(seen["headers"]["Authorization"], "Bearer secret-value")
        self.assertNotIn("secret-value", json.dumps(result))

    def test_rejects_an_empty_secret_before_network_access(self):
        with self.assertRaisesRegex(github_connector.ConnectorUnavailable, "not configured"):
            github_connector.list_repositories("")

    def test_validates_a_token_with_the_same_bounded_read_contract(self):
        result = github_connector.validate_token(
            "secret-value", transport=lambda _url, _headers: [])
        self.assertEqual(result, {"repositories": [], "repository_limit": 30})

    def test_never_returns_more_than_the_declared_repository_limit(self):
        rows = [{"full_name": f"owner/repository-{index}"} for index in range(35)]

        result = github_connector.list_repositories(
            "secret-value", transport=lambda _url, _headers: rows)

        self.assertEqual(len(result["repositories"]), 30)
        self.assertEqual(result["repository_limit"], 30)

    def test_classifies_rejected_authorization_separately_from_provider_outage(self):
        rejected = urllib.error.HTTPError('https://api.github.com', 401, 'Unauthorized', {}, None)
        with self.assertRaises(github_connector.AuthorizationRejected):
            github_connector.list_repositories('secret-value',
                                                transport=lambda _url, _headers: (_ for _ in ()).throw(rejected))
        with self.assertRaises(github_connector.ConnectorUnavailable):
            github_connector.list_repositories('secret-value',
                                                transport=lambda _url, _headers: (_ for _ in ()).throw(TimeoutError()))


if __name__ == "__main__":
    unittest.main()
