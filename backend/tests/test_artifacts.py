#!/usr/bin/env python3
"""Behavior tests for Surveyor's evidence-backed FDE artifact compiler."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import artifacts, pipeline


PROFILE = {
    "signals": {
        "domain": "building enclosure consulting",
        "primary_goal": "turn field observations into evidence-backed reports",
        "delegation_style": "human_checkpoint_before_final",
        "risk_awareness": "high",
    },
    "freeform": {
        "automate": "Organize field notes and prepare report drafts.",
        "screen": "A research dashboard with documents and a checklist.",
    },
    "evidence": [{
        "criterion": "verification_instinct",
        "summary": "I want to review anything client-facing before it goes out.",
        "confidence": "high",
        "source": "surveyor_conversation",
    }],
}


class TestCompileArtifacts(unittest.TestCase):
    def test_preserves_surveyor_evidence_in_operator_source_artifact(self):
        bundle = artifacts.compile_artifacts(PROFILE)

        self.assertIn("# Operator", bundle["source/operator.md"])
        self.assertIn("building enclosure consulting", bundle["source/operator.md"])
        self.assertIn("I want to review anything client-facing", bundle["source/operator.md"])

    def test_marks_connector_confirmation_without_claiming_authorization(self):
        bundle = artifacts.compile_artifacts(
            PROFILE, connector_states={"github": "confirmed", "notion": "suggested"})

        connectors = bundle["source/connectors.md"]
        self.assertIn("GitHub", connectors)
        self.assertIn("Confirmed by user", connectors)
        self.assertIn("Notion", connectors)
        self.assertIn("Suggested - not connected", connectors)
        self.assertIn("Implementation: live", connectors)
        self.assertIn("Implementation: planned", connectors)
        self.assertIn("Credentials are not stored in this artifact", connectors)

    def test_compiled_runtime_is_operational_and_keeps_transcript_out(self):
        bundle = artifacts.compile_artifacts(PROFILE)

        tasks = bundle["runtime/fde-tasks.md"]
        self.assertIn("# FDE Mission Brief", tasks)
        self.assertIn("Organize field notes", tasks)
        self.assertNotIn("I want to review anything client-facing", tasks)
        self.assertIn("ASK", bundle["runtime/permissions.md"])
        self.assertIn("DENY", bundle["runtime/permissions.md"])
        self.assertIn("research dashboard", bundle["runtime/workspace-plan.md"])

    def test_catalog_is_provider_neutral_and_supports_durable_transports(self):
        catalog = artifacts.connector_catalog()
        github = catalog["github"]

        self.assertIn("direct_api", github["runtime_transports"])
        self.assertIn("mcp", github["runtime_transports"])
        self.assertIn("oauth", github["setup_modes"])
        self.assertIn("google_drive", catalog)
        self.assertIn("slack", catalog)
        self.assertIn("notion", catalog)

    def test_catalog_has_a_planned_custom_mcp_path_for_unlisted_services(self):
        catalog = artifacts.connector_catalog()

        self.assertEqual(catalog["custom_mcp"]["implementation_status"], "planned")
        self.assertEqual(catalog["custom_mcp"]["setup_modes"], ["mcp"])
        self.assertEqual(catalog["custom_mcp"]["runtime_transports"], ["mcp"])

    def test_catalog_includes_the_documented_hostinger_guided_setup_path(self):
        hostinger = artifacts.connector_catalog()["hostinger"]

        self.assertEqual(hostinger["implementation_status"], "planned")
        self.assertIn("guided_browser", hostinger["setup_strategy"])
        self.assertIn("direct_api", hostinger["runtime_transports"])

    def test_catalog_covers_major_planned_collaboration_crm_and_support_services(self):
        catalog = artifacts.connector_catalog()

        for connector_id in ("clickup", "azure_boards", "basecamp", "intercom",
                             "pipedrive", "zoho_crm", "docusign", "onepassword"):
            self.assertEqual(catalog[connector_id]["implementation_status"], "planned")
            self.assertIn("mcp", catalog[connector_id]["runtime_transports"])

    def test_catalog_distinguishes_live_adapters_from_supported_plans(self):
        catalog = artifacts.connector_catalog()
        self.assertEqual(catalog['github']['implementation_status'], 'live')
        self.assertEqual(catalog['notion']['implementation_status'], 'planned')
        self.assertIn('guided_browser', catalog['github']['setup_strategy'])

    def test_connector_state_update_preserves_existing_confirmations(self):
        states = artifacts.merge_connector_states(
            {"notion": "confirmed"}, {"github": "confirmed"})

        self.assertEqual(states, {"notion": "confirmed", "github": "confirmed"})

    def test_pipeline_compiles_artifacts_from_the_existing_profile_contract(self):
        profile = dict(PROFILE, connector_states={"github": "confirmed"})

        bundle = pipeline.compile_artifact_bundle(profile)

        self.assertIn("GitHub", bundle["source/connectors.md"])
        self.assertIn("# FDE Mission Brief", bundle["runtime/fde-tasks.md"])

    def test_intent_miss_is_carried_into_the_inspectable_source_artifact(self):
        profile = dict(PROFILE, intent_misses=[{
            'date': '2026-08-13', 'category': 'needs_evidence',
            'correction': 'Cite inspection photos.',
            'effect': 'Include source links in drafts.',
        }])
        bundle = artifacts.compile_artifacts(profile)
        self.assertIn('needs_evidence', bundle['source/intent-misses.md'])
        self.assertIn('Include source links in drafts.', bundle['source/intent-misses.md'])

    def test_latest_intent_correction_refines_runtime_mission(self):
        profile = dict(PROFILE, intent_misses=[{
            'date': '2026-08-13', 'category': 'needs_evidence',
            'correction': 'Cite inspection photos.',
            'effect': 'Include source links in drafts.',
        }])
        bundle = artifacts.compile_artifacts(profile)
        self.assertIn('Include source links in drafts.', bundle['runtime/fde-tasks.md'])

    def test_assessment_view_is_non_scored_and_keeps_evidence_inspectable(self):
        view = artifacts.assessment_view(PROFILE, {"github": "confirmed"})

        self.assertEqual(view["title"], "What Cordia currently understands")
        self.assertIn("building enclosure consulting",
                      [item["value"] for item in view["understanding"]])
        self.assertEqual(view["connectors"][0]["status"], "Confirmed by user")
        self.assertIn("I want to review anything client-facing", view["evidence"][0]["summary"])
        self.assertNotIn("score", view)


if __name__ == "__main__":
    unittest.main()
