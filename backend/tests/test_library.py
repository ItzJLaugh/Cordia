#!/usr/bin/env python3
"""Tests for surveyor.library — framework ranking and param prefill.

Stdlib unittest only. Run from /opt/cordia/backend:
    python3 -m unittest tests.test_library -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import types
from surveyor import library


def _card(criterion, confidence):
    return {"criterion": criterion, "confidence": confidence}


class TestFrameworkShape(unittest.TestCase):
    def test_serves_keys_are_valid_criteria(self):
        for fid, fw in library.FRAMEWORKS.items():
            for key in fw["serves"]:
                self.assertIn(key, types.CRITERIA,
                              f"{fid}.serves has unknown criterion {key}")

    def test_every_criterion_served_by_some_framework(self):
        served = set()
        for fw in library.FRAMEWORKS.values():
            served.update(fw["serves"].keys())
        for c in types.CRITERIA:
            self.assertIn(c, served, f"criterion {c} served by no framework")

    def test_assert_positive_clean_over_whole_dict(self):
        self.assertEqual(types.assert_positive(library.FRAMEWORKS), [])

    def test_assert_positive_clean_per_string(self):
        for fid, fw in library.FRAMEWORKS.items():
            self.assertEqual(types.assert_positive(fw["name"]), [],
                             f"{fid}.name")
            for pid, p in fw["params"].items():
                self.assertEqual(types.assert_positive(p["ask"]), [],
                                 f"{fid}.{pid}.ask")
                for opt in p.get("options", []):
                    self.assertEqual(types.assert_positive(opt), [],
                                     f"{fid}.{pid}.options")


class TestRankFrameworks(unittest.TestCase):
    def test_empty_input_returns_empty_list(self):
        self.assertEqual(library.rank_frameworks([]), [])

    def test_clear_visual_systems_ranks_node_graph_first(self):
        out = library.rank_frameworks([_card("visual_systems_thinking", "clear")])
        self.assertTrue(out)
        self.assertEqual(out[0]["framework_id"], "node_graph")
        self.assertAlmostEqual(out[0]["score"], 1.0)
        self.assertEqual(out[0]["matched_criterion"], "visual_systems_thinking")

    def test_each_single_clear_criterion_yields_a_candidate(self):
        for c in types.CRITERIA:
            out = library.rank_frameworks([_card(c, "clear")])
            self.assertGreaterEqual(len(out), 1,
                                    f"single clear {c} card ranked no frameworks")

    def test_confidence_weights(self):
        clear = library.rank_frameworks([_card("verification_instinct", "clear")])
        early = library.rank_frameworks([_card("verification_instinct", "early")])
        self.assertAlmostEqual(clear[0]["score"], 0.9)
        self.assertAlmostEqual(early[0]["score"], 0.9 * 0.33)

    def test_zero_score_cards_dropped(self):
        out = library.rank_frameworks([_card("intent_clarity", "clear")])
        ids = [r["framework_id"] for r in out]
        self.assertIn("chat_workspace", ids)
        self.assertNotIn("node_graph", ids)
        self.assertNotIn("plot_dashboard", ids)

    def test_tie_breaks_by_matched_card_index(self):
        # node_graph via workflow_decomposition (0.7) and chat_workspace via
        # delegation_readiness (0.7) — equal scores. Card order decides.
        cards = [_card("workflow_decomposition", "clear"),
                 _card("delegation_readiness", "clear")]
        out = library.rank_frameworks(cards)
        by_id = {r["framework_id"]: r for r in out}
        self.assertAlmostEqual(by_id["node_graph"]["score"], 0.7)
        self.assertAlmostEqual(by_id["chat_workspace"]["score"], 0.7)
        self.assertLess(out.index(by_id["node_graph"]),
                        out.index(by_id["chat_workspace"]))
        # reversed card order reverses the result
        out_rev = library.rank_frameworks(list(reversed(cards)))
        self.assertLess(out_rev.index(by_id["chat_workspace"]),
                        out_rev.index(by_id["node_graph"]))

    def test_result_is_pure_dicts(self):
        out = library.rank_frameworks([_card("gap_detection", "clear")])
        for r in out:
            self.assertEqual(set(r.keys()),
                             {"framework_id", "score", "matched_criterion"})


class TestPrefillParams(unittest.TestCase):
    def test_defaults_when_signals_empty(self):
        out = library.prefill_params("node_graph", {})
        self.assertEqual(out["edge_meaning"], "sequence")
        self.assertEqual(out["dimensions"], "2d")
        self.assertIsNone(out["node_source"])

    def test_unknown_framework_returns_empty(self):
        self.assertEqual(library.prefill_params("nope", {}), {})

    def test_detailed_density_sets_scatter(self):
        out = library.prefill_params("plot_dashboard",
                                     {"interface_density": "detailed"})
        self.assertEqual(out["plot_type"], "scatter")

    def test_other_density_keeps_default(self):
        out = library.prefill_params("plot_dashboard",
                                     {"interface_density": "minimal"})
        self.assertEqual(out["plot_type"], "line")

    def test_does_not_mutate_frameworks(self):
        library.prefill_params("plot_dashboard", {"interface_density": "detailed"})
        self.assertEqual(
            library.FRAMEWORKS["plot_dashboard"]["params"]["plot_type"]["default"],
            "line")


if __name__ == "__main__":
    unittest.main()
