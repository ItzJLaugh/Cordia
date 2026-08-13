#!/usr/bin/env python3
"""Tests for dashboard.skills — the catalogue and deterministic retrieval.

Stdlib unittest only, no DB, no network. Run from backend/:
    python3 -m unittest tests.test_dashboard_skills -v
"""
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import framework as fw
from dashboard import skills
from surveyor import types as stypes
from tests.envhermetic import EnvHermeticCase


def systems_thinker_framework():
    return fw.framework_from_profile({"signals": {
        "preferred_workspace": "graph_and_chat",
        "role_tendency": "analyzer",
        "graph_preference": "high",
        "verification_preference": "evidence_first",
    }})


class TestCatalogueShape(EnvHermeticCase):
    def test_records_are_complete_and_legal(self):
        seen = set()
        for s in skills.SKILLS:
            for key in ("id", "name", "description", "kind",
                        "profile_affinity", "tags", "inputs", "outputs"):
                self.assertIn(key, s, s.get("id"))
            self.assertIn(s["kind"], skills.KINDS, s["id"])
            self.assertNotIn(s["id"], seen, "duplicate id")
            seen.add(s["id"])
            for tag in s["profile_affinity"]:
                self.assertIn(tag, skills.AFFINITY_TAGS,
                              f"{s['id']}: unknown affinity {tag!r}")

    def test_affinity_vocabulary_matches_framework_vocabulary(self):
        """A framework value that could never match any affinity tag would be
        a silent dead row in the mapping — pin the vocabularies together."""
        for v in fw.ROLE_VIEWS + fw.LEAD_SURFACES + fw.DIAGRAM_FORWARD:
            self.assertIn(v, skills.AFFINITY_TAGS, v)

    def test_catalogue_copy_is_isolated(self):
        a = skills.all_skills()
        a[0]["name"] = "hacked"
        a[0]["tags"].append("hacked")
        b = skills.all_skills()
        self.assertNotEqual(b[0]["name"], "hacked")
        self.assertNotIn("hacked", b[0]["tags"])

    def test_never_negative_catalogue_and_results(self):
        self.assertEqual(stypes.assert_positive(list(skills.SKILLS)), [])
        out = skills.retrieve(systems_thinker_framework(), "map my system")
        self.assertEqual(stypes.assert_positive(out), [])


class TestRetrieval(EnvHermeticCase):
    def test_systems_thinker_pulls_systems_thinker_skills(self):
        out = skills.retrieve(systems_thinker_framework(), "")
        ids = [s["id"] for s in out]
        self.assertGreaterEqual(len(ids), 3)
        self.assertEqual(ids[0], "system-map")
        self.assertIn("dependency-trace", ids[:3])
        self.assertIn("evidence-audit", ids)

    def test_oversight_framework_pulls_oversight_skills(self):
        f = fw.framework_from_profile({"signals": {
            "preferred_workspace": "dashboard",
            "role_tendency": "manager",
        }})
        ids = [s["id"] for s in skills.retrieve(f, "")]
        self.assertIn("status-board", ids[:2])

    def test_intent_words_pull_matching_skills(self):
        f = fw.framework_from_profile(None)
        out = skills.retrieve(f, "compare the options against our criteria")
        self.assertEqual(out[0]["id"], "option-compare")

    def test_ranking_is_stable_and_ties_resolve_by_declaration_order(self):
        f = systems_thinker_framework()
        first = skills.retrieve(f, "map dependencies")
        for _ in range(5):
            self.assertEqual(skills.retrieve(f, "map dependencies"), first)
        # system-map and dependency-trace share affinity; with no intent
        # words their scores tie and declaration order must decide.
        ids = [s["id"] for s in skills.retrieve(f, "")]
        self.assertLess(ids.index("system-map"), ids.index("dependency-trace"))

    def test_no_match_returns_empty_not_noise(self):
        self.assertEqual(skills.retrieve({}, ""), [])
        self.assertEqual(skills.retrieve(None, None), [])
        self.assertEqual(skills.retrieve({"role_view": "bogus"}, "zzzqqq"), [])

    def test_empty_library_degrades_to_empty(self):
        with mock.patch.object(skills, "SKILLS", ()):
            self.assertEqual(skills.retrieve(systems_thinker_framework(), "map"), [])

    def test_hostile_intent_is_inert(self):
        f = systems_thinker_framework()
        for intent in ("' OR 1=1; --", "<script>alert(1)</script>",
                       ".*+?[](){}|\\^$", "\x00\x01", "🤖" * 100, 12345, ["map"]):
            out = skills.retrieve(f, intent)          # must not raise
            self.assertIsInstance(out, list, repr(intent))
        # regex metacharacters never widen matching: 'map' via ['map'] list
        # is not a string and contributes nothing
        base = skills.retrieve(f, "")
        self.assertEqual(skills.retrieve(f, ["map"]), base)

    def test_oversized_intent_is_capped_not_fatal(self):
        f = systems_thinker_framework()
        out = skills.retrieve(f, "map " * 100_000)
        self.assertIsInstance(out, list)
        # words beyond the cap cannot influence ranking
        beyond = "zzz " * 200 + "compare"
        self.assertEqual([s["id"] for s in skills.retrieve(f, beyond)],
                         [s["id"] for s in skills.retrieve(f, "zzz " * 200)])

    def test_limit_is_honoured_and_defensive(self):
        f = systems_thinker_framework()
        self.assertLessEqual(len(skills.retrieve(f, "", limit=2)), 2)
        self.assertEqual(skills.retrieve(f, "", limit=0), [])
        self.assertIsInstance(skills.retrieve(f, "", limit="x"), list)
        self.assertIsInstance(skills.retrieve(f, "", limit=float("inf")), list)
        self.assertIsInstance(skills.retrieve(f, "", limit=float("nan")), list)

    def test_results_carry_scores_and_do_not_alias_catalogue(self):
        out = skills.retrieve(systems_thinker_framework(), "")
        self.assertTrue(all(isinstance(s.get("score"), float) for s in out))
        out[0]["tags"].append("hacked")
        self.assertNotIn("hacked", skills.all_skills()[0]["tags"])


if __name__ == "__main__":
    unittest.main()
