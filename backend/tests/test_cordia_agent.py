import json
import os
import sys
import unittest
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import cordia_agent, workspace_state


CONNECTOR = {
    "kind": "propose_connector",
    "proposal": {
        "connector_id": "issue_tracker", "display_name": "Issue tracker",
        "setup_kind": "api_key", "purpose": "Review current issues.",
    },
}
ARTIFACT = {
    "kind": "create_artifact",
    "proposal": {
        "artifact_id": "weekly_plan", "title": "Weekly plan",
        "view_mode": "dash", "summary": "A focused weekly plan.",
    },
}
SKILL = {
    "kind": "propose_skill",
    "proposal": {
        "skill_id": "review_issues", "name": "Review issues",
        "purpose": "Review issues.", "connector_id": "issue_tracker",
        "operation_id": "list_issues", "artifact_id": "weekly_plan",
    },
}
RUN_SKILL = {"kind": "run_approved_skill", "proposal": {"skill_id": "review_issues"}}


class TestCordiaAgent(unittest.TestCase):
    def test_action_envelopes_accept_only_kind_and_proposal(self):
        for envelope in (CONNECTOR, ARTIFACT, SKILL, RUN_SKILL):
            with self.subTest(kind=envelope["kind"]):
                self.assertEqual(cordia_agent.validate_envelope(envelope), envelope)
                for extra in ("speech", "providerSpeech", "secret_ref"):
                    with self.subTest(extra=extra), self.assertRaises(ValueError):
                        cordia_agent.validate_envelope({**envelope, extra: "Provider sentinel prose."})

    def test_speak_accepts_only_bounded_privacy_screened_speech(self):
        ordinary = {"kind": "speak", "speech": "What outcome matters most?"}
        self.assertEqual(cordia_agent.validate_envelope(ordinary), ordinary)
        for unsafe in (
            "sk-private-token", "ghp_privatetoken", "token=private",
            "C:\\private\\workspace", "/etc/cordia/secret", "private/secret.txt",
        ):
            with self.subTest(unsafe=unsafe), self.assertRaises(ValueError):
                cordia_agent.validate_envelope({"kind": "speak", "speech": unsafe})
        with self.assertRaises(ValueError):
            cordia_agent.validate_envelope({"kind": "speak", "speech": "Hello", "proposal": {}})

    def test_operational_speak_uses_fixed_clarification_after_privacy_screening(self):
        clarification = "I can discuss that, but workspace status and changes must use a Cordia action."
        for speech in (
            "GitHub is live.",
            "I have not configured GitHub.",
            "If GitHub is connected, can we proceed?",
            "I would have configured GitHub if approved.",
            "This feature is available in the catalog, and the app is ready.",
        ):
            with self.subTest(speech=speech):
                self.assertEqual(cordia_agent.validate_envelope({"kind": "speak", "speech": speech}),
                                 {"kind": "speak", "speech": clarification})
        with self.assertRaises(ValueError):
            cordia_agent.validate_envelope({"kind": "speak", "speech": "sk-private-token connect"})

    def test_public_action_copy_is_fixed_and_server_owned(self):
        cases = (
            (CONNECTOR, "I prepared a connector setup card."),
            (ARTIFACT, "I prepared a proposed workspace artifact."),
            (SKILL, "I prepared a proposed skill for review."),
            (RUN_SKILL, "This skill requires approval before it can run."),
        )
        for envelope, expected in cases:
            with self.subTest(kind=envelope["kind"]):
                accepted = cordia_agent.validate_envelope(envelope)
                self.assertEqual(cordia_agent.public_action_copy(accepted, accepted["proposal"]), expected)

    def test_connector_display_name_rejects_provider_action_prose(self):
        for connector_id, display_name in (
            ("github", "GitHub. I connected it"),
            ("github_i_connected_it", "GitHub I connected it"),
            ("github_ready_now", "GitHub Ready Now"),
            ("github_tools", "GitHub\nTools"),
            ("github_i_support_you", "GitHub I Support You"),
        ):
            with self.subTest(connector_id=connector_id, display_name=display_name):
                envelope = deepcopy(CONNECTOR)
                envelope["proposal"].update({
                    "connector_id": connector_id,
                    "display_name": display_name,
                })
                with self.assertRaises(ValueError):
                    cordia_agent.validate_envelope(envelope)
                with self.assertRaises(ValueError):
                    cordia_agent.apply_proposal(workspace_state.empty("workspace_1"), envelope)

    def test_connector_proposal_public_copy_never_uses_provider_display_name(self):
        envelope = deepcopy(CONNECTOR)
        envelope["proposal"].update({
            "connector_id": "github_i_linked",
            "display_name": "GitHub I linked",
        })

        accepted = cordia_agent.validate_envelope(envelope)
        next_state, public = cordia_agent.apply_proposal(
            workspace_state.empty("workspace_1"), accepted)

        self.assertEqual(public["speech"], "I prepared a connector setup card.")
        self.assertEqual(next_state["pending_actions"][0]["display_name"], "GitHub I linked")

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

    def test_prompt_lists_speech_only_for_speak(self):
        prompt = cordia_agent.build_system_prompt({"memory": "", "workspace": {}, "recent_turns": []})
        schemas = json.loads(prompt.split("Allowed actions and exact fields: ", 1)[1].split("\n", 1)[0])
        self.assertEqual(schemas["speak"]["fields"], ["kind", "speech"])
        for kind in ("propose_connector", "create_artifact", "propose_skill", "run_approved_skill"):
            with self.subTest(kind=kind):
                self.assertEqual(schemas[kind]["fields"], ["kind", "proposal"])

    def test_prompt_exposes_supported_connector_setup_kinds(self):
        prompt = cordia_agent.build_system_prompt({"memory": "", "workspace": {}, "recent_turns": []})
        schemas = json.loads(prompt.split("Allowed actions and exact fields: ", 1)[1].split("\n", 1)[0])

        self.assertEqual(
            schemas["propose_connector"]["allowed_setup_kinds"],
            ["api_key", "openapi", "remote_mcp"],
        )
        self.assertEqual(schemas["propose_connector"]["unsupported_setup_action"], "speak")

    def test_context_has_only_compiled_memory_and_safe_workspace_summaries(self):
        state = workspace_state.empty("workspace_1")
        state.update({
            "title": "Planning", "description": "A safe workspace.",
            "windows": [{"id": "weekly_plan", "title": "Weekly plan", "summary": "Safe summary",
                         "payload": "private provider response", "path": "C:\\private"}],
            "connectors": [{"id": "issues", "status": "suggested", "secret_ref": "secret-1",
                            "reason": "private reason"}],
        })
        prompt = cordia_agent.build_system_prompt(cordia_agent.build_context("Compiled memory.", state, [
            {"user": "Prior safe user message", "assistant": "Prior safe reply", "raw": "omit"},
        ]))
        for expected in ("Compiled memory.", "Planning", "Weekly plan", "Prior safe user message"):
            self.assertIn(expected, prompt)
        for private in ("secret-1", "private reason", "private provider", "C:\\private", "raw"):
            self.assertNotIn(private, prompt)

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
            cordia_agent.run_turn({}, "Hello", lambda *_args, **_kwargs: json.dumps({
                **CONNECTOR, "speech": "Provider sentinel prose."}))

    def test_run_turn_reports_unsupported_oauth_without_proposing_fake_setup(self):
        oauth = deepcopy(CONNECTOR)
        oauth["proposal"].update({
            "connector_id": "google_drive",
            "display_name": "Google Drive",
            "setup_kind": "oauth",
        })

        result = cordia_agent.run_turn(
            {}, "Connect Google Drive", lambda *_args, **_kwargs: json.dumps(oauth))

        self.assertEqual(result, {
            "kind": "speak",
            "speech": "This request requires OAuth, which this Cordia beta does not support yet.",
        })

    def test_apply_proposal_persists_only_action_and_deterministic_copy(self):
        state = workspace_state.empty("workspace_1")
        same, public = cordia_agent.apply_proposal(state, {"kind": "speak", "speech": "GitHub is live."})
        self.assertEqual(same, state)
        self.assertEqual(public, {"ok": True,
            "speech": "I can discuss that, but workspace status and changes must use a Cordia action.",
            "action": None, "revision": 0})
        expected = {
            "propose_connector": ("I prepared a connector setup card.",
                {"kind": "propose_connector", "state": "setup_required", "connector_id": "issue_tracker",
                 "setup_kind": "api_key"}),
            "create_artifact": ("I prepared a proposed workspace artifact.",
                {"kind": "create_artifact", "state": "proposal_required", "artifact_id": "weekly_plan"}),
            "propose_skill": ("I prepared a proposed skill for review.",
                {"kind": "propose_skill", "state": "proposal_required", "skill_id": "review_issues"}),
        }
        for envelope in (CONNECTOR, ARTIFACT, SKILL):
            with self.subTest(kind=envelope["kind"]):
                next_state, public = cordia_agent.apply_proposal(state, envelope)
                speech, action = expected[envelope["kind"]]
                self.assertEqual(public, {"ok": True, "speech": speech, "action": action, "revision": 1})
                self.assertEqual(next_state["pending_actions"], [{"kind": envelope["kind"], **envelope["proposal"]}])

    def test_apply_proposal_rejects_action_speech_before_mutation(self):
        for envelope in (CONNECTOR, ARTIFACT, SKILL, RUN_SKILL):
            with self.subTest(kind=envelope["kind"]):
                state = workspace_state.empty("workspace_1")
                with self.assertRaises(ValueError):
                    cordia_agent.apply_proposal(state, {**envelope, "speech": "Provider sentinel prose."})
                self.assertEqual(state, workspace_state.empty("workspace_1"))

    def test_run_approved_skill_never_executes_without_server_approval(self):
        state = workspace_state.empty("workspace_1")
        next_state, public = cordia_agent.apply_proposal(state, RUN_SKILL)
        self.assertEqual(next_state, state)
        self.assertEqual(public, {"ok": True, "speech": "This skill requires approval before it can run.",
                                  "revision": 0, "action": {"kind": "run_approved_skill",
                                  "state": "approval_required", "skill_id": "review_issues"}})


if __name__ == "__main__":
    unittest.main()
