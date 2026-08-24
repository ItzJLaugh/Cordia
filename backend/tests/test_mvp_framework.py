import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import cordia_agent


class TestMvpFramework(unittest.TestCase):
    def test_simulated_memory_to_connector_proposal_workspace_revision(self):
        workspace = {
            "id": "workspace_demo",
            "revision": 0,
            "title": "Demo",
            "description": "",
            "connectors": [],
            "artifacts": [],
            "skills": [],
            "pending_actions": [],
        }
        captured = {}

        def simulated_model(system, user, max_tokens):
            captured.update(system=system, user=user, max_tokens=max_tokens)
            return json.dumps({
                "kind": "propose_connector",
                "proposal": {
                    "connector_id": "status_api",
                    "display_name": "Status API",
                    "setup_kind": "api_key",
                    "purpose": "Read service status.",
                },
            })

        context = cordia_agent.build_context(
            "# Workspace Memory\nCommunication policy: Start with the outcome.",
            workspace,
            [],
        )
        envelope = cordia_agent.run_turn(context, "Connect our status API", simulated_model)
        updated, public = cordia_agent.apply_proposal(workspace, envelope)

        self.assertIn("Start with the outcome", captured["system"])
        self.assertEqual(captured["user"], "Connect our status API")
        self.assertEqual(captured["max_tokens"], 700)
        self.assertEqual(public["speech"], "I prepared a connector setup card.")
        self.assertEqual(public["action"], {
            "kind": "propose_connector",
            "state": "setup_required",
            "connector_id": "status_api",
            "setup_kind": "api_key",
        })
        self.assertEqual(public["revision"], 1)
        self.assertEqual(updated["revision"], 1)
        self.assertEqual(updated["pending_actions"][0], {
            "kind": "propose_connector",
            "connector_id": "status_api",
            "display_name": "Status API",
            "setup_kind": "api_key",
            "purpose": "Read service status.",
        })


if __name__ == "__main__":
    unittest.main()
