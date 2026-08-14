#!/usr/bin/env python3
"""Tests for dashboard.framework — the approved profile->framework mapping.

Stdlib unittest only, no DB, no network. Run from backend/:
    python3 -m unittest tests.test_dashboard_framework -v
"""
import copy
import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import framework as fw
from surveyor import types as stypes


def profile_with(signals=None, **extra):
    p = stypes.empty_profile()
    p["signals"] = dict(signals or {})
    p.update(extra)
    return p


class EnvHermeticCase(unittest.TestCase):
    """Base: each test runs with PERSONALIZATION_MODE unset (so 'simple', the
    default mode, applies) and the developer's own environment restored
    afterwards — hermetic on entry without being destructive on exit."""

    def setUp(self):
        prior = os.environ.pop("PERSONALIZATION_MODE", None)
        if prior is not None:
            self.addCleanup(os.environ.__setitem__, "PERSONALIZATION_MODE", prior)


class TestMappingTable(EnvHermeticCase):
    """Every row of the approved mapping, value by value."""

    def test_preferred_workspace_decides_lead_surface(self):
        for stated, lead in (("canvas", "canvas"), ("graph_and_chat", "canvas"),
                             ("dashboard", "dashboard"), ("chat_first", "chat")):
            out = fw.framework_from_profile(
                profile_with({"preferred_workspace": stated}))
            self.assertEqual(out["lead_surface"], lead, stated)

    def test_workspace_balanced_falls_through_to_preferences(self):
        out = fw.framework_from_profile(
            profile_with({"preferred_workspace": "balanced",
                          "graph_preference": "high"}))
        self.assertEqual(out["lead_surface"], "canvas")

    def test_lead_surface_fallbacks_without_stated_workspace(self):
        self.assertEqual(fw.framework_from_profile(
            profile_with({"graph_preference": "high"}))["lead_surface"], "canvas")
        self.assertEqual(fw.framework_from_profile(
            profile_with({"visual_preference": "high"}))["lead_surface"], "dashboard")
        self.assertEqual(fw.framework_from_profile(
            profile_with({}))["lead_surface"], "chat")

    def test_graph_preference_decides_diagram_forwardness(self):
        for level, forward in (("high", "graph_first"), ("medium", "balanced"),
                               ("low", "text_first")):
            out = fw.framework_from_profile(
                profile_with({"graph_preference": level}))
            self.assertEqual(out["diagram_forward"], forward, level)

    def test_visual_preference_backstops_diagram_forwardness(self):
        out = fw.framework_from_profile(
            profile_with({"visual_preference": "high"}))
        self.assertEqual(out["diagram_forward"], "graph_first")
        # graph_preference, when present, wins over visual_preference
        out = fw.framework_from_profile(
            profile_with({"graph_preference": "low", "visual_preference": "high"}))
        self.assertEqual(out["diagram_forward"], "text_first")

    def test_delegation_style_decides_approval_density(self):
        for style, density in (("agent_autonomous", "agent_led"),
                               ("human_checkpoint_before_final", "checkpoint_final"),
                               ("human_reviews_every_step", "checkpoint_every_step")):
            out = fw.framework_from_profile(
                profile_with({"delegation_style": style}))
            self.assertEqual(out["approval_density"], density, style)

    def test_absent_delegation_defaults_to_the_cautious_end(self):
        out = fw.framework_from_profile(profile_with({}))
        self.assertEqual(out["approval_density"], "checkpoint_final")

    def test_interface_density_passes_through(self):
        for d in ("minimal", "balanced", "detailed"):
            out = fw.framework_from_profile(profile_with({"interface_density": d}))
            self.assertEqual(out["node_density"], d, d)
        self.assertEqual(fw.framework_from_profile(
            profile_with({}))["node_density"], "balanced")

    def test_role_tendency_decides_view(self):
        for role, view in (("analyzer", "graph"), ("technical_specialist", "graph"),
                           ("prototyper", "scaffold"), ("manager", "oversight"),
                           ("human_facing", "oversight"), ("mixed", "balanced")):
            out = fw.framework_from_profile(profile_with({"role_tendency": role}))
            self.assertEqual(out["role_view"], view, role)

    def test_verification_preference_surfaces_evidence_nodes(self):
        self.assertTrue(fw.framework_from_profile(
            profile_with({"verification_preference": "evidence_first"}))["verification_nodes"])
        for other in ("speed_first", "example_first"):
            self.assertFalse(fw.framework_from_profile(
                profile_with({"verification_preference": other}))["verification_nodes"],
                other)

    def test_reason_attributes_the_signal_that_actually_fired(self):
        """The reason must cite the person's real basis: a graph phrase only
        when graph_preference produced the shape, a visual phrase when the
        visual_preference backstop did — never a graph habit the person
        never stated, paired with a dashboard surface."""
        graph = fw.framework_from_profile(profile_with({"graph_preference": "high"}))
        self.assertIn("you plan in graphs", graph["reason"])
        visual = fw.framework_from_profile(profile_with({"visual_preference": "high"}))
        self.assertEqual(visual["lead_surface"], "dashboard")
        self.assertIn("you think visually", visual["reason"])
        self.assertNotIn("graphs", visual["reason"])

    def test_shaped_text_first_output_never_claims_to_be_standard(self):
        """graph/visual 'low' deviates from the generic 'balanced', so the
        reason must show a basis rather than the 'standard starting point'
        fallback — a shaped payload denying its shaping reads as the product
        being weird at the person."""
        for signals in ({"graph_preference": "low"}, {"visual_preference": "low"}):
            out = fw.framework_from_profile(profile_with(signals))
            self.assertEqual(out["diagram_forward"], "text_first", signals)
            self.assertIn("you plan in prose first", out["reason"])
            self.assertNotIn("standard starting point", out["reason"])

    def test_visual_high_is_cited_even_when_diagram_stays_balanced(self):
        """graph=medium + visual=high shapes the SURFACE (dashboard lead)
        while diagram_forward stays balanced — the reason must still cite
        the visual signal, not fall back to 'standard starting point'."""
        out = fw.framework_from_profile(profile_with(
            {"graph_preference": "medium", "visual_preference": "high"}))
        self.assertEqual(out["lead_surface"], "dashboard")
        self.assertEqual(out["diagram_forward"], "balanced")
        self.assertIn("you think visually", out["reason"])
        self.assertNotIn("standard starting point", out["reason"])

    def test_fallback_appears_only_on_unshaped_lead_and_diagram(self):
        """Enumerate every workspace x graph x visual combination: the
        'standard starting point' fallback may appear only when both
        lead_surface and diagram_forward equal their generic values —
        anything shaped must carry a visible basis."""
        workspaces = (None, "canvas", "graph_and_chat", "dashboard",
                      "chat_first", "balanced")
        levels = (None, "low", "medium", "high")
        for w in workspaces:
            for g in levels:
                for v in levels:
                    signals = {}
                    if w:
                        signals["preferred_workspace"] = w
                    if g:
                        signals["graph_preference"] = g
                    if v:
                        signals["visual_preference"] = v
                    out = fw.framework_from_profile(profile_with(signals))
                    if "standard starting point" in out["reason"]:
                        self.assertEqual(
                            out["lead_surface"],
                            fw.GENERIC_FRAMEWORK["lead_surface"], signals)
                        self.assertEqual(
                            out["diagram_forward"],
                            fw.GENERIC_FRAMEWORK["diagram_forward"], signals)

    def test_systems_thinker_flagship_shape(self):
        """The v1 flagship: canvas-led, graph-forward, evidence-checked."""
        out = fw.framework_from_profile(profile_with({
            "preferred_workspace": "graph_and_chat",
            "role_tendency": "analyzer",
            "graph_preference": "high",
            "delegation_style": "human_checkpoint_before_final",
            "interface_density": "detailed",
            "verification_preference": "evidence_first",
        }))
        self.assertEqual(out["lead_surface"], "canvas")
        self.assertEqual(out["diagram_forward"], "graph_first")
        self.assertEqual(out["role_view"], "graph")
        self.assertEqual(out["approval_density"], "checkpoint_final")
        self.assertEqual(out["node_density"], "detailed")
        self.assertTrue(out["verification_nodes"])
        self.assertTrue(out["personalized"])


class TestScenarioWins(EnvHermeticCase):

    def test_revealed_delegation_beats_stated(self):
        """A stage-2 scenario choice overrides the stage-1 answer, exactly as
        adaptation applies it everywhere else ('the scenario wins')."""
        p = profile_with({"delegation_style": "agent_autonomous"})
        p["scenarios"] = {"replies": "human_reviews_every_step"}
        out = fw.framework_from_profile(p)
        self.assertEqual(out["approval_density"], "checkpoint_every_step")

    def test_revealed_workspace_beats_stated(self):
        p = profile_with({"preferred_workspace": "chat_first"})
        p["scenarios"] = {"firstglance": "canvas"}
        out = fw.framework_from_profile(p)
        self.assertEqual(out["lead_surface"], "canvas")


class TestKillSwitchAndDefaults(EnvHermeticCase):

    def _wildly_different_profiles(self):
        return [
            stypes.empty_profile(),
            profile_with({"preferred_workspace": "canvas", "role_tendency": "analyzer",
                          "graph_preference": "high", "delegation_style": "agent_autonomous",
                          "interface_density": "detailed",
                          "verification_preference": "evidence_first"}),
            profile_with({"preferred_workspace": "dashboard", "role_tendency": "manager",
                          "visual_preference": "high",
                          "delegation_style": "human_reviews_every_step"}),
            None,
        ]

    def test_kill_switch_output_is_byte_identical_for_every_profile(self):
        with mock.patch.dict(os.environ, {"PERSONALIZATION_MODE": "off"}):
            blobs = {json.dumps(fw.framework_from_profile(p), sort_keys=False)
                     for p in self._wildly_different_profiles()}
        self.assertEqual(len(blobs), 1)
        self.assertEqual(json.loads(next(iter(blobs))), fw.GENERIC_FRAMEWORK)

    def test_kill_switch_is_read_at_call_time(self):
        p = profile_with({"preferred_workspace": "canvas"})
        with mock.patch.dict(os.environ, {"PERSONALIZATION_MODE": "off"}):
            self.assertFalse(fw.framework_from_profile(p)["personalized"])
        self.assertTrue(fw.framework_from_profile(p)["personalized"])

    def test_simple_mode_forced_still_personalizes(self):
        """Only 'off' erases the profile; forced-simple is the normal mode."""
        p = profile_with({"preferred_workspace": "canvas"},
                         simple_mode_forced=True)
        out = fw.framework_from_profile(p)
        self.assertTrue(out["personalized"])
        self.assertEqual(out["lead_surface"], "canvas")

    def test_empty_and_none_profiles_get_generic_shaped_defaults(self):
        for p in (stypes.empty_profile(), None, {}):
            out = fw.framework_from_profile(p)
            self.assertTrue(out["personalized"], repr(p))
            for key in ("lead_surface", "diagram_forward", "approval_density",
                        "node_density", "role_view", "verification_nodes"):
                self.assertEqual(out[key], fw.GENERIC_FRAMEWORK[key], key)

    def test_generic_framework_constant_is_never_mutated_by_callers(self):
        with mock.patch.dict(os.environ, {"PERSONALIZATION_MODE": "off"}):
            out = fw.framework_from_profile(None)
            out["lead_surface"] = "hacked"
            self.assertEqual(fw.GENERIC_FRAMEWORK["lead_surface"], "chat")


class TestInvariants(EnvHermeticCase):

    def test_never_negative_on_every_reachable_output(self):
        """No framework payload may carry deficit words — including the
        vocabulary constants themselves and every reason line this suite
        generates."""
        self.assertEqual(stypes.assert_positive(fw.GENERIC_FRAMEWORK), [])
        for const in (fw.LEAD_SURFACES, fw.DIAGRAM_FORWARD, fw.APPROVAL_DENSITY,
                      fw.NODE_DENSITY, fw.ROLE_VIEWS):
            self.assertEqual(stypes.assert_positive(list(const)), [])
        signals_grid = [
            {"preferred_workspace": w} for w in ("canvas", "graph_and_chat",
                                                 "dashboard", "chat_first")
        ] + [
            {"graph_preference": l} for l in ("low", "medium", "high")
        ] + [
            {"visual_preference": l} for l in ("low", "medium", "high")
        ] + [
            {"role_tendency": r} for r in ("prototyper", "analyzer", "manager",
                                           "human_facing", "technical_specialist")
        ] + [
            {"delegation_style": d} for d in ("agent_autonomous",
                                              "human_checkpoint_before_final",
                                              "human_reviews_every_step")
        ] + [
            {"verification_preference": v} for v in ("evidence_first", "speed_first")
        ] + [
            {"interface_density": d} for d in ("minimal", "balanced", "detailed")
        ]
        for signals in signals_grid:
            out = fw.framework_from_profile(profile_with(signals))
            self.assertEqual(stypes.assert_positive(out), [], signals)

    def test_workspace_phrasing_stays_in_step_with_adaptation(self):
        """framework._reason mirrors adaptation._reason's 'you asked for …'
        phrasing. Both modules keep their own copy (adaptation's is keyed to
        its surface argument), so this pins them together: for a profile
        stating only a workspace, the two sentences must be identical, or
        the product speaks about the same choice in two voices."""
        from surveyor import adaptation
        for workspace in ("canvas", "graph_and_chat", "dashboard",
                          "chat_first", "balanced"):
            p = profile_with({"preferred_workspace": workspace})
            ours = fw.framework_from_profile(p)["reason"]
            theirs = adaptation._reason(p, adaptation.surface_defaults(p))
            self.assertEqual(ours, theirs, workspace)

    def test_deterministic_and_input_unmutated(self):
        p = profile_with({"preferred_workspace": "canvas",
                          "graph_preference": "low"})
        snapshot = copy.deepcopy(p)
        a = fw.framework_from_profile(p)
        b = fw.framework_from_profile(p)
        self.assertEqual(a, b)
        self.assertIsNot(a, b)
        self.assertEqual(p, snapshot)

    def test_output_values_stay_inside_the_vocabulary(self):
        for signals in ({}, {"preferred_workspace": "canvas"},
                        {"role_tendency": "prototyper", "graph_preference": "medium"}):
            out = fw.framework_from_profile(profile_with(signals))
            self.assertIn(out["lead_surface"], fw.LEAD_SURFACES)
            self.assertIn(out["diagram_forward"], fw.DIAGRAM_FORWARD)
            self.assertIn(out["approval_density"], fw.APPROVAL_DENSITY)
            self.assertIn(out["node_density"], fw.NODE_DENSITY)
            self.assertIn(out["role_view"], fw.ROLE_VIEWS)
            self.assertIsInstance(out["verification_nodes"], bool)


if __name__ == "__main__":
    unittest.main()
