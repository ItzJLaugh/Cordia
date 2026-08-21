import json
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import cordia_agent, workspace_state


CONNECTOR = {
    "kind": "propose_connector", "speech": "I can prepare that connection.",
    "proposal": {
        "connector_id": "issue_tracker", "display_name": "Issue tracker",
        "setup_kind": "api_key", "purpose": "Review current issues.",
    },
}


class TestCordiaAgent(unittest.TestCase):
    def test_speak_is_the_only_actionless_envelope(self):
        self.assertEqual(cordia_agent.validate_envelope(
            {"kind": "speak", "speech": "What should we connect first?"}),
            {"kind": "speak", "speech": "What should we connect first?"})

    def test_every_unknown_or_extra_field_fails_closed(self):
        for value in (
            {"kind": "shell", "command": "rm -rf /"},
            {"kind": "speak", "speech": "Hello", "connector": "github"},
            {"kind": "propose_connector", "speech": "Connect it", "proposal":
                {"connector_id": "drive", "setup_kind": "oauth"}},
        ):
            with self.subTest(value=value), self.assertRaises(ValueError):
                cordia_agent.validate_envelope(value)

    def test_every_proposal_requires_its_exact_allow_listed_shape(self):
        examples = (
            CONNECTOR,
            {"kind": "create_artifact", "speech": "I can add that.", "proposal": {
                "artifact_id": "weekly_plan", "title": "Weekly plan",
                "view_mode": "dash", "summary": "A focused weekly plan.",
            }},
            {"kind": "propose_skill", "speech": "I can propose it.", "proposal": {
                "skill_id": "review_issues", "name": "Review issues",
                "purpose": "Review issues.", "connector_id": "issue_tracker",
                "operation_id": "list_issues", "artifact_id": "weekly_plan",
            }},
            {"kind": "run_approved_skill", "speech": "Approval is required.",
             "proposal": {"skill_id": "review_issues"}},
        )
        for value in examples:
            with self.subTest(kind=value["kind"]):
                self.assertEqual(cordia_agent.validate_envelope(value), value)
                with self.assertRaises(ValueError):
                    cordia_agent.validate_envelope({**value, "secret_ref": "nope"})

    def test_turn_request_is_exact_revisioned_and_idempotent(self):
        valid = {"id": "workspace_1", "revision": 4, "message": "Review issues",
                 "idempotency_key": "turn_abc123"}
        self.assertEqual(cordia_agent.validate_turn_request(valid), valid)
        for bad in (
            {**valid, "revision": -1}, {**valid, "idempotency_key": ""},
            {**valid, "message": " "}, {**valid, "approval": "forged"},
        ):
            with self.subTest(value=bad), self.assertRaises(ValueError):
                cordia_agent.validate_turn_request(bad)

    def test_text_fields_reject_credentials_and_local_paths_but_allow_safe_remote_urls(self):
        for unsafe in (
            "sk-private-token", "ghp_privatetoken", "github_pat_privatetoken",
            "AKIA1234567890ABCD", "token=private", "-----BEGIN PRIVATE KEY-----",
            "C:\\private\\workspace", "..\\private", "/etc/cordia/secret", "\\\\host\\share",
        ):
            with self.subTest(unsafe=unsafe):
                with self.assertRaises(ValueError):
                    cordia_agent.validate_turn_request({
                        "id": "workspace_1", "revision": 0, "message": unsafe,
                        "idempotency_key": "turn_abc123",
                    })
                with self.assertRaises(ValueError):
                    cordia_agent.validate_envelope({"kind": "speak", "speech": unsafe})
        self.assertEqual(cordia_agent.validate_envelope({
            "kind": "speak", "speech": "See https://example.test/docs for the public guide.",
        })["kind"], "speak")

    def test_prompt_context_has_only_compiled_memory_and_safe_workspace_summaries(self):
        state = workspace_state.empty("workspace_1")
        state.update({
            "title": "Planning", "description": "A safe workspace.",
            "windows": [{"id": "weekly_plan", "title": "Weekly plan", "summary": "Safe summary",
                         "payload": "private provider response", "path": "C:\\private"}],
            "connectors": [{"id": "issues", "status": "suggested", "secret_ref": "secret-1",
                            "reason": "private reason"}],
            "skills": [{"id": "review_issues", "name": "Review issues", "purpose": "Read issues",
                        "operation_id": "list_issues", "ciphertext": "nope"}],
            "profile": {"raw": "never prompt"}, "event_payload": "never prompt",
        })
        context = cordia_agent.build_context("Compiled memory.", state, [
            {"user": "Prior safe user message", "assistant": "Prior safe reply", "raw": "omit"},
        ])
        prompt = cordia_agent.build_system_prompt(context)
        self.assertIn("Compiled memory.", prompt)
        self.assertIn("Planning", prompt)
        self.assertIn("Weekly plan", prompt)
        self.assertIn("Prior safe user message", prompt)
        for private in ("secret-1", "private reason", "private provider", "C:\\private",
                        "never prompt", "nope", "raw"):
            self.assertNotIn(private, prompt)

    def test_prompt_retains_only_bounded_connector_truth_fields(self):
        context = cordia_agent.build_context("Compiled memory.", {
            "title": "Planning", "description": "Coordinate work.",
            "windows": [{"id": "weekly_plan", "title": "Weekly plan", "summary": "Safe plan."}],
            "connectors": [{
                "id": "issue_tracker", "status": "confirmed", "implementation_status": "live",
                "lifecycle": "needs_handoff", "runtime_status": "not_observed",
                "secret_ref": "secret_issue_1", "reason": "private reason",
            }],
            "skills": [],
        }, [])
        prompt = cordia_agent.build_system_prompt(context)
        for expected in ("weekly_plan", "Weekly plan", "Safe plan.", "confirmed", "live",
                         "needs_handoff", "not_observed"):
            self.assertIn(expected, prompt)
        self.assertNotIn("secret_issue_1", prompt)
        self.assertNotIn("private reason", prompt)

    def test_run_turn_accepts_only_one_strict_json_envelope(self):
        seen = {}
        def call_model(system, message, max_tokens):
            seen.update({"system": system, "message": message, "max_tokens": max_tokens})
            return json.dumps(CONNECTOR)
        result = cordia_agent.run_turn({"memory": "Compiled memory.", "workspace": {}, "recent_turns": []},
                                       "Connect my tracker", call_model)
        self.assertEqual(result, CONNECTOR)
        self.assertEqual((seen["message"], seen["max_tokens"]), ("Connect my tracker", 700))
        with self.assertRaises(cordia_agent.InvalidAgentResponse):
            cordia_agent.run_turn({}, "Hello", lambda *_args, **_kwargs: "not json")

    def test_speak_never_revises_and_proposals_persist_one_pending_action(self):
        state = workspace_state.empty("workspace_1")
        same, public = cordia_agent.apply_proposal(state, {
            "kind": "speak", "speech": "Let us decide together.",
        })
        self.assertEqual(same, state)
        self.assertEqual(public, {"ok": True, "speech": "Let us decide together.",
                                  "action": None, "revision": 0})
        next_state, public = cordia_agent.apply_proposal(state, CONNECTOR)
        self.assertEqual(next_state["revision"], 1)
        self.assertEqual(next_state["pending_actions"], [{
            "kind": "propose_connector", **CONNECTOR["proposal"],
        }])
        self.assertEqual(public, {"ok": True, "speech": CONNECTOR["speech"], "revision": 1,
                                  "action": {"kind": "propose_connector", "state": "setup_required",
                                             "connector_id": "issue_tracker", "setup_kind": "api_key"}})
        self.assertFalse(any(item.get("id") == "issue_tracker" for item in next_state["connectors"]))

    def test_run_approved_skill_never_executes_without_server_approval(self):
        state = workspace_state.empty("workspace_1")
        next_state, public = cordia_agent.apply_proposal(state, {
            "kind": "run_approved_skill", "speech": "Approval is required.",
            "proposal": {"skill_id": "review_issues"},
        })
        self.assertEqual(next_state, state)
        self.assertEqual(public["action"], {"kind": "run_approved_skill", "state": "approval_required",
                                             "skill_id": "review_issues"})

    def test_speak_cannot_claim_an_unperformed_connector_or_skill_action(self):
        for speech in (
            "Your connector is connected.", "The skill completed.",
            "The action was approved.", "The connector is fully connected.",
            "The skill has completed.", "I executed the integration.",
        ):
            with self.subTest(speech=speech), self.assertRaises(ValueError):
                cordia_agent.validate_envelope({"kind": "speak", "speech": speech})
        self.assertEqual(cordia_agent.validate_envelope({
            "kind": "speak", "speech": "I can propose a connector setup for your approval.",
        })["speech"], "I can propose a connector setup for your approval.")


if __name__ == "__main__":
    unittest.main()
