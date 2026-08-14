import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import alidora


class TestAlidora(unittest.TestCase):
    def test_map_payload_is_safe_and_deterministic(self):
        state = {
            "id": "w-1",
            "title": "Launch",
            "agents": [{"id": "review", "name": "Review"}],
            "skills": [],
            "connectors": [],
            "permissions": {"mode": "compiled"},
            "context_sources": [{"id": "C:\\private\\repo"}],
            "provenance": [{"secret": "must-not-leak"}],
        }

        result = alidora.map_payload(state)

        self.assertEqual(
            result["workspace"],
            {"id": "w-1", "title": "Launch", "description": ""},
        )
        self.assertEqual(
            result["nodes"],
            [{"id": "agent:review", "kind": "agent", "label": "Review", "detail": ""}],
        )
        self.assertEqual(
            result["summary"],
            {"agents": 1, "skills": 0, "connectors": 0, "approval_mode": "compiled"},
        )
        self.assertNotIn("private", repr(result))
        self.assertNotIn("must-not-leak", repr(result))

    def test_map_payload_discards_unresolved_references(self):
        result = alidora.map_payload({"id": "w", "workflow": {"steps": [{"agent_id": "missing"}]}})

        self.assertEqual(result["nodes"], [])
        self.assertEqual(result["edges"], [])

    def test_map_payload_projects_canonical_workflow_edges_only(self):
        result = alidora.map_payload(
            {
                "agents": [
                    {"id": "writer", "name": "Writer"},
                    {"id": "review", "name": "Review"},
                    {"name": "Malformed"},
                ],
                "skills": [
                    {"id": "draft", "name": "Draft"},
                    {"id": "check", "name": "Check"},
                ],
                "connectors": [{"id": "github", "name": "GitHub"}],
                "workflow": {
                    "steps": [
                        {"id": "write", "agentId": "writer", "toolIds": ["draft", None, "missing"]},
                        {"id": "review", "agentId": "review", "toolIds": ["check", "missing"]},
                        {"agentId": "missing", "toolIds": ["draft"]},
                    ]
                },
            }
        )

        self.assertEqual(
            [node["id"] for node in result["nodes"]],
            ["agent:review", "agent:writer", "connector:github", "skill:check", "skill:draft"],
        )
        self.assertEqual(
            result["edges"],
            [
                {"from": "agent:review", "to": "skill:check"},
                {"from": "agent:writer", "to": "agent:review"},
                {"from": "agent:writer", "to": "skill:draft"},
            ],
        )

    def test_map_payload_drops_unsafe_strings_from_every_emitted_position(self):
        result = alidora.map_payload(
            {
                "id": "C:\\private\\workspace",
                "title": "/private/project",
                "description": "token=must-not-leak",
                "agents": [
                    {"id": "C:\\private\\agent", "name": "password=hunter2"},
                    {"id": "safe-agent", "name": "Review", "description": "sk-secret-value"},
                ],
                "skills": [{"id": "safe-skill", "name": "Bearer private-token", "description": "Useful"}],
                "connectors": [{"id": "safe-connector", "name": "Connector", "description": "\\\\server\\share"}],
                "permissions": {"mode": "authorization=private"},
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:safe-agent", "kind": "agent", "label": "Review", "detail": ""},
                {"id": "connector:safe-connector", "kind": "connector", "label": "Connector", "detail": ""},
                {"id": "skill:safe-skill", "kind": "skill", "label": "", "detail": "Useful"},
            ],
        )
        self.assertEqual(result["summary"]["approval_mode"], "")
        for forbidden in ("private", "must-not-leak", "hunter2", "secret-value", "Bearer", "server"):
            self.assertNotIn(forbidden, repr(result))

    def test_map_payload_rejects_duplicate_ids_independently_of_input_order(self):
        first = {
            "agents": [
                {"id": "same", "name": "First"},
                {"id": "same", "name": "Second"},
                {"id": "other", "name": "Other"},
            ]
        }
        second = {"agents": list(reversed(first["agents"]))}

        self.assertEqual(alidora.map_payload(first), alidora.map_payload(second))
        self.assertEqual(
            alidora.map_payload(first)["nodes"],
            [{"id": "agent:other", "kind": "agent", "label": "Other", "detail": ""}],
        )

    def test_map_payload_rejects_control_characters_and_overlong_identifiers(self):
        result = alidora.map_payload(
            {
                "id": "workspace\x00id",
                "title": "Normal\nTitle",
                "agents": [{"id": "a" * 81, "name": "Too long"}],
                "skills": [{"id": "valid", "name": "Useful\x1f detail"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [{"id": "skill:valid", "kind": "skill", "label": "", "detail": ""}],
        )

    def test_map_payload_drops_embedded_paths_and_common_credential_shapes(self):
        result = alidora.map_payload(
            {
                "id": "w1",
                "title": "Build from C:\\private\\repo",
                "description": "See /home/jacks/private/project for details",
                "agents": [
                    {"id": "review", "name": "Review Notes", "description": "Checks product evidence."},
                    {"id": "path", "name": "Open \\\\server\\share", "description": "xoxb-123456789012-abcdefghijk"},
                ],
                "skills": [{"id": "deploy", "name": "ghp_abcdefghijklmnopqrstuvwxyz", "description": "AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE"}],
                "connectors": [{"id": "database", "name": "Postgres", "description": "postgres://user:password@db.example/internal"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "w1", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:path", "kind": "agent", "label": "", "detail": ""},
                {"id": "agent:review", "kind": "agent", "label": "Review Notes", "detail": "Checks product evidence."},
                {"id": "connector:database", "kind": "connector", "label": "Postgres", "detail": ""},
                {"id": "skill:deploy", "kind": "skill", "label": "", "detail": ""},
            ],
        )
        for forbidden in ("private", "home", "server", "xoxb", "ghp", "AKIA", "password@"):
            self.assertNotIn(forbidden, repr(result))

    def test_map_payload_drops_remaining_posix_and_key_shapes(self):
        posix_usr = "Run /usr/local/bin/tool"
        posix_root = "Read /root/private/key"
        aws_secret = "AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"
        github_pat = "github_pat_abcdefghijklmnopqrstuvwxyz0123456789"
        result = alidora.map_payload(
            {
                "title": posix_usr,
                "description": posix_root,
                "agents": [{"id": "safe", "name": "Review Notes", "description": aws_secret}],
                "skills": [{"id": "safe-skill", "name": github_pat, "description": "Useful summary"}],
            }
        )

        self.assertEqual(result["workspace"], {"id": "", "title": "", "description": ""})
        self.assertEqual(
            result["nodes"],
            [
                {"id": "agent:safe", "kind": "agent", "label": "Review Notes", "detail": ""},
                {"id": "skill:safe-skill", "kind": "skill", "label": "", "detail": "Useful summary"},
            ],
        )
        for forbidden in (posix_usr, posix_root, aws_secret, github_pat):
            self.assertNotIn(forbidden, repr(result))


if __name__ == "__main__":
    unittest.main()
