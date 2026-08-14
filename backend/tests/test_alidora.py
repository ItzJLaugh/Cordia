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

    def test_map_payload_sorts_nodes_and_only_emits_resolved_edges(self):
        result = alidora.map_payload(
            {
                "agents": [
                    {"id": "writer", "name": "Writer"},
                    {"id": "review", "name": "Review"},
                    {"name": "Malformed"},
                ],
                "skills": [{"id": "draft", "name": "Draft"}],
                "connectors": [{"id": "github", "name": "GitHub"}],
                "workflow": {
                    "steps": [
                        {"id": "write", "agent_id": "writer", "skill_id": "draft"},
                        {"id": "review", "agent_id": "review", "connector_id": "github"},
                        {"agent_id": "missing", "skill_id": "draft"},
                    ]
                },
            }
        )

        self.assertEqual(
            [node["id"] for node in result["nodes"]],
            ["agent:review", "agent:writer", "connector:github", "skill:draft"],
        )
        self.assertEqual(
            result["edges"],
            [
                {"from": "agent:review", "to": "connector:github"},
                {"from": "agent:writer", "to": "skill:draft"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
