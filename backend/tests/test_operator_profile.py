import importlib
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import freeform, operator_profile, pipeline, scenarios, types


IDENTIFIERS = [
    {
        "name": "Evidence-minded",
        "meaning": "You want important claims grounded in sources.",
        "use_ai_this_way": "Ask Cordia to show the evidence behind a draft.",
        "criterion": "verification_instinct",
        "confidence": "clear",
        "private": "must-not-leak",
    },
    {
        "name": "Intent-led",
        "meaning": "You start with the result that matters.",
        "use_ai_this_way": "State the outcome before the method.",
        "criterion": "intent_clarity",
        "confidence": "emerging",
    },
    {
        "name": "Checkpoint-aware",
        "meaning": "You know when a human should review.",
        "use_ai_this_way": "Mark the irreversible boundary.",
        "criterion": "risk_boundary_awareness",
        "confidence": "early",
    },
]


def ready_profile():
    return {
        "signals": {
            "domain": "building enclosure consulting",
            "primary_goal": "turn observations into evidence-backed reports",
            "delegation_style": "human_checkpoint_before_final",
        },
        "identifiers": IDENTIFIERS,
        "evidence": [
            {
                "summary": "I review client-facing claims before they go out.",
                "confidence": "high",
                "criterion": "verification_instinct",
            }
        ],
        "scores": {
            "verification_instinct": 0.9,
            "intent_clarity": 0.9,
            "risk_boundary_awareness": 0.9,
        },
        "confidence": 1.0,
        "intent_misses": [{"correction": "private correction"}],
    }


class TestOperatorProfileProjection(unittest.TestCase):
    def test_existing_public_profile_hides_internal_criteria_and_numeric_completion(self):
        incomplete = pipeline.public_profile("owner@example.test", ready_profile())
        completed_profile = ready_profile()
        completed_profile["signals"].update({
            key: ("known" if types.SIGNAL_SCHEMA[key] is None
                  else next(value for value in types.SIGNAL_SCHEMA[key] if value != "unknown"))
            for key in types.SIGNAL_PRIORITY
        })
        completed_profile["scenarios"] = {
            item["id"]: item["options"][0][0] for item in scenarios.SCENARIOS}
        completed_profile["freeform"] = {key: "known answer" for key in freeform.KEYS}
        public = pipeline.public_profile("owner@example.test", completed_profile)

        self.assertNotIn("percent_complete", public)
        self.assertFalse(incomplete["complete"])
        self.assertTrue(public["complete"])
        self.assertEqual(
            set(public["identifiers"][0]),
            {"name", "meaning", "use_ai_this_way", "evidence_strength"},
        )
        self.assertNotIn("criterion", repr(public).lower())
        self.assertNotIn("private", repr(public).lower())

    def test_returns_only_bounded_non_scored_display_contract(self):
        profile = ready_profile()
        result = operator_profile.build(
            profile,
            {"github": "confirmed", "notion": "suggested"},
            [{
                "id": "workspace-1",
                "name": "Inspection workspace",
                "description": "private description",
                "definition": {"secret": "must-not-leak"},
                "updated": "2026-08-18",
            }],
        )

        self.assertEqual(
            set(result),
            {"title", "identifiers", "understanding", "evidence", "connectors",
             "still_learning", "next_action", "latest_workspace"},
        )
        self.assertEqual(
            set(result["identifiers"][0]),
            {"name", "meaning", "use_ai_this_way", "evidence_strength"},
        )
        self.assertEqual(
            [item["evidence_strength"] for item in result["identifiers"]],
            ["clear", "emerging", "early"],
        )
        self.assertEqual(result["latest_workspace"], {
            "id": "workspace-1", "name": "Inspection workspace"})
        self.assertEqual(result["next_action"]["type"], "refine_profile")
        self.assertNotIn("score", repr(result).lower())
        self.assertNotIn("criterion", repr(result).lower())
        self.assertNotIn("must-not-leak", repr(result))
        self.assertNotIn("private correction", repr(result))

    def test_drops_sensitive_user_text_and_does_not_scan_past_unsafe_latest_workspace(self):
        profile = ready_profile()
        profile["signals"]["domain"] = "C:\\private\\client-work"
        profile["evidence"] = [
            {"summary": "token=private-value", "confidence": "high"},
            {"summary": "Safe evidence in the person's own words.", "confidence": "medium"},
        ]
        result = operator_profile.build(
            profile,
            {"github": "confirmed"},
            [
                {"id": "github_pat_abcdefghijklmnopqrstuvwxyz012345", "name": "Unsafe"},
                {"id": "workspace-2", "name": "Must not be scanned"},
            ],
        )

        self.assertNotIn("C:\\private\\client-work", repr(result))
        self.assertNotIn("private-value", repr(result))
        self.assertIn("Safe evidence", result["evidence"][0]["summary"])
        self.assertIsNone(result["latest_workspace"])

    def test_malformed_remote_url_encoding_is_rejected_fail_closed(self):
        profile = ready_profile()
        profile["evidence"] = [{
            "summary": "See https://example.test/docs?bad=%ZZ for context.",
            "confidence": "high",
        }]

        result = operator_profile.build(profile, {}, [])

        self.assertEqual(result["evidence"], [])

    def test_learning_items_and_actions_are_derived_without_numeric_completion(self):
        empty = operator_profile.build({}, {}, [])
        partial = operator_profile.build({
            "signals": {"domain": "operations"},
            "identifiers": IDENTIFIERS[:1],
            "scores": {"verification_instinct": 0.9},
            "evidence": [],
        }, {}, [])
        ready = operator_profile.build(ready_profile(), {}, [])

        self.assertEqual(empty["next_action"]["type"], "continue_survey")
        self.assertEqual(partial["next_action"]["type"], "refine_profile")
        self.assertEqual(ready["next_action"]["type"], "refine_profile")
        self.assertTrue(empty["still_learning"])
        self.assertTrue(partial["still_learning"])
        self.assertEqual(ready["still_learning"], ["Which systems should be connected"])
        self.assertNotIn("percent", repr((empty, partial, ready)).lower())

    def test_generation_action_uses_the_same_canonical_completion_rule_as_the_route(self):
        sparse_at_cap = types.empty_profile()
        sparse_at_cap["questions_answered"] = types.ONBOARDING_TURN_LIMIT

        rich_but_incomplete = ready_profile()

        completed = operator_profile.build(sparse_at_cap, {}, [])
        incomplete = operator_profile.build(rich_but_incomplete, {}, [])

        self.assertTrue(operator_profile.is_complete(sparse_at_cap))
        self.assertEqual(completed["next_action"]["type"], "create_interface")
        self.assertFalse(operator_profile.is_complete(rich_but_incomplete))
        self.assertNotEqual(incomplete["next_action"]["type"], "create_interface")

    def test_malformed_legacy_rows_are_dropped_instead_of_breaking_projection(self):
        result = operator_profile.build({
            "signals": {"delegation_style": {}, "domain": ["legacy"]},
            "identifiers": [{"name": "Bad", "meaning": "Bad", "use_ai_this_way": "Bad",
                             "confidence": {"not": "a label"}}],
            "evidence": ["legacy", {"summary": "Bad", "confidence": ["high"]}],
            "scores": {"verification_instinct": "high"},
            "connector_states": ["legacy"],
        }, {"github": "confirmed"}, [{"id": ["workspace"], "name": {}}])

        self.assertEqual(result["identifiers"], [])
        self.assertEqual(result["evidence"], [])
        self.assertIsNone(result["latest_workspace"])

    def test_empty_canonical_connector_state_never_revives_legacy_profile_state(self):
        profile = ready_profile()
        profile["connector_states"] = {"github": "confirmed"}

        result = operator_profile.build(profile, {}, [])

        self.assertEqual(result["connectors"], [])

    def test_common_local_paths_and_private_key_headers_are_removed(self):
        profile = ready_profile()
        profile["evidence"] = [
            {"summary": value, "confidence": "high"}
            for value in (
                "/tmp",
                "./private/key.txt",
                "..\\private\\key.txt",
                "-----BEGIN RSA PRIVATE KEY-----",
            )
        ]

        result = operator_profile.build(profile, {}, [])

        self.assertEqual(result["evidence"], [])

    def test_safe_remote_urls_survive_while_nested_local_paths_do_not(self):
        profile = ready_profile()
        profile["evidence"] = [
            {"summary": "See https://example.test/tmp for public docs.", "confidence": "high"},
            {"summary": "See https://[2001:db8::1]/docs/start.", "confidence": "medium"},
            {"summary": "See https://example.test/docs?next=/tmp.", "confidence": "high"},
        ]

        result = operator_profile.build(profile, {}, [])

        self.assertEqual(
            [item["summary"] for item in result["evidence"]],
            ["See https://example.test/tmp for public docs.",
             "See https://[2001:db8::1]/docs/start."],
        )


class TestOperatorProfileEndpoint(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._missing = object()
        cls._prior = sys.modules.get("training_backend", cls._missing)
        cls._auth_patch = patch.dict(sys.modules, {"cordia_auth": SimpleNamespace()})
        cls._auth_patch.start()
        sys.modules.pop("training_backend", None)
        cls.backend = importlib.import_module("training_backend")

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("training_backend", None)
        cls._auth_patch.stop()
        if cls._prior is not cls._missing:
            sys.modules["training_backend"] = cls._prior

    def handler(self, email="owner@example.test"):
        handler = object.__new__(self.backend.H)
        handler.path = "/surveyor/operator-profile"
        handler._surv_guard = lambda: (email, None) if email else (None, True)
        handler.response = None
        handler._json = lambda payload, status=200: setattr(
            handler, "response", (payload, status))
        return handler

    def test_authenticated_get_is_owner_scoped_and_read_only(self):
        calls = []

        def forbidden(*_args, **_kwargs):
            raise AssertionError("operator profile endpoint must not write or execute")

        surveyor = SimpleNamespace(
            pipeline=SimpleNamespace(load_profile=lambda email: calls.append(("profile", email)) or ready_profile()),
            store=SimpleNamespace(
                get_connector_states=lambda email: calls.append(("connectors", email)) or {"github": "confirmed"},
                list_interfaces=lambda email: calls.append(("interfaces", email)) or [{"id": "workspace-1", "name": "Launch"}],
                save_profile=forbidden,
                save_workspace=forbidden,
                log_event=forbidden,
            ),
            operator_profile=operator_profile,
            skills=SimpleNamespace(execute=forbidden),
            capability_gateway=SimpleNamespace(execute=forbidden),
        )
        handler = self.handler()

        with patch.object(self.backend, "surveyor", surveyor):
            handler.do_GET()

        payload, status = handler.response
        self.assertEqual(status, 200)
        self.assertEqual(set(payload), {"ok", "operator_profile"})
        self.assertEqual(payload["operator_profile"]["latest_workspace"]["id"], "workspace-1")
        self.assertEqual(calls, [
            ("profile", "owner@example.test"),
            ("connectors", "owner@example.test"),
            ("interfaces", "owner@example.test"),
        ])

    def test_unauthenticated_get_stops_before_any_store_read(self):
        handler = self.handler(email=None)
        with patch.object(self.backend, "surveyor", SimpleNamespace()):
            handler.do_GET()
        self.assertIsNone(handler.response)


if __name__ == "__main__":
    unittest.main()
