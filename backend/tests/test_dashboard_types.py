#!/usr/bin/env python3
"""Tests for dashboard.types — the Interface Definition contract.

Stdlib unittest only, no DB, no network. Run from backend/:
    python3 -m unittest tests.test_dashboard_types -v
"""
import copy
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import types as dtypes
from surveyor import adaptation
from surveyor import types as stypes
from surveyor.hitl_policy import requires_approval


def builder_definition():
    """A fully-valid definition shaped exactly like the web builder's output."""
    return {
        "name": "Analysis workspace",
        "description": "Evidence-checked analysis with a written result.",
        "surface": {"type": "graph_and_chat", "theme": "visual"},
        "agents": [
            {"id": "intake", "name": "Intake", "role": "clarify",
             "instructions": "Restate the request before work starts."},
            {"id": "evidence", "name": "Evidence Checker", "role": "check",
             "instructions": "Cite the specific input each conclusion came from."},
        ],
        "tools": [
            {"id": "summarize", "name": "Summarizer", "type": "summarize"},
            {"id": "compare", "name": "Comparator", "type": "compare"},
        ],
        "workflow": {"steps": [
            {"agentId": "intake", "toolIds": ["summarize"],
             "instruction": "Restate the request.", "requiresApproval": False},
            {"agentId": "evidence", "toolIds": ["summarize", "compare"],
             "instruction": "Check the claims.", "requiresApproval": True},
        ]},
        "futureHooks": {"langGraphCompatible": True, "cordiaCompilerCompatible": True,
                        "durableStateReady": False, "humanInLoopReady": True},
    }


class TestRoundTrip(unittest.TestCase):
    def test_valid_builder_definition_passes_through_unchanged(self):
        d = builder_definition()
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(d)), d)

    def test_adaptation_defaults_round_trip(self):
        """The definitions the adaptation layer generates (with step ids and
        no futureHooks) must survive validation unchanged — the two modules
        speak the same contract or the starting canvas silently mutates."""
        defaults = adaptation.builder_defaults(stypes.empty_profile())
        d = {"surface": defaults["surface"], "agents": defaults["agents"],
             "tools": defaults["tools"], "workflow": defaults["workflow"]}
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(d)), d)

    def test_validation_is_idempotent(self):
        junk = {"agents": [{"id": "a"}, "noise", {"id": "a"}],
                "tools": [{"id": "t", "type": "bogus"}],
                "workflow": {"steps": [{"agentId": "a", "requiresApproval": "yes"},
                                       {"agentId": "ghost"}]},
                "surface": {"type": "spreadsheet"}, "extra": object}
        once = dtypes.validate_definition(junk)
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(once)), once)

    def test_input_is_not_mutated(self):
        d = builder_definition()
        snapshot = copy.deepcopy(d)
        dtypes.validate_definition(d)
        self.assertEqual(d, snapshot)


class TestMalformed(unittest.TestCase):
    def test_non_dict_degrades_to_empty(self):
        for bad in (None, [], "definition", 42, 3.14, True, b"bytes", ("a",)):
            self.assertEqual(dtypes.validate_definition(bad),
                             dtypes.empty_definition(), repr(bad))

    def test_never_raises_on_hostile_grab_bag(self):
        hostile = {
            "agents": [None, 7, "x", [], {"id": None}, {"id": ""}, {"id": " "},
                       {"id": "ok", "name": 9, "role": [], "instructions": {}},
                       {"id": "<script>"}, {"id": "-leading-dash"},
                       {"id": "ok"}],                     # duplicate: first wins
            "tools": "not-a-list",
            "workflow": {"steps": [{"agentId": "ok", "toolIds": "not-a-list"}]},
            "surface": {"type": "chat", "theme": object()},
            "futureHooks": {"langGraphCompatible": "yes", "unknownHook": True},
            "name": float("nan"), "description": ["x"],
        }
        out = dtypes.validate_definition(hostile)
        # the duplicate declared id is repaired by suffix, not deleted
        self.assertEqual([a["id"] for a in out["agents"]], ["ok", "ok-2"])
        self.assertEqual(out["agents"][0]["name"], "ok")       # bad name -> id
        self.assertEqual(out["workflow"]["steps"],
                         [{"agentId": "ok", "toolIds": [], "instruction": "",
                           "requiresApproval": False}])
        self.assertEqual(out["tools"], [])
        self.assertEqual(out["surface"], {"type": "chat", "theme": "minimal"})
        self.assertEqual(out["futureHooks"], {"langGraphCompatible": True})
        self.assertNotIn("name", out)
        self.assertNotIn("description", out)

    def test_unknown_keys_are_dropped(self):
        out = dtypes.validate_definition({"agents": [], "evil": {"deep": [1]},
                                          "__proto__": "x"})
        self.assertEqual(set(out), {"agents", "tools", "workflow"})

    def test_wellformed_dangling_references_are_kept_malformed_dropped(self):
        """Dangling references are legal — the builder emits them today (it
        re-slugs ids from names at save without remapping steps) and the
        renderer falls back to the raw id. Deleting the step would be silent
        data loss on real stored rows. Malformed references still cost the
        part."""
        d = {"agents": [{"id": "a"}],
             "tools": [{"id": "t1", "type": "search"}],
             "workflow": {"steps": [
                 {"agentId": "a", "toolIds": ["t1", "ghost-tool", 5, "bad id"]},
                 {"agentId": "ghost-agent", "toolIds": ["t1"]},
             ]}}
        out = dtypes.validate_definition(d)
        self.assertEqual(len(out["workflow"]["steps"]), 2)
        self.assertEqual(out["workflow"]["steps"][0]["toolIds"],
                         ["t1", "ghost-tool"])                 # 5, 'bad id' dropped
        self.assertEqual(out["workflow"]["steps"][1]["agentId"], "ghost-agent")

    def test_builder_reslugged_default_template_survives_intact(self):
        """The exact production shape the sweep caught: the untouched
        personalized default, saved through the builder, whose save-time
        re-slug leaves steps referencing the old catalogue ids. Both steps
        must survive validation, and the graph must resolve the dangle with
        a placeholder node instead of losing the step."""
        d = {"surface": {"type": "chat", "theme": "formal"},
             "agents": [
                 {"id": "intake", "name": "Intake", "role": "clarify",
                  "instructions": "Restate the request."},
                 {"id": "report-drafter", "name": "Report Drafter", "role": "draft",
                  "instructions": "Write the result up clearly."},
             ],
             "tools": [{"id": "summarizer", "name": "Summarizer", "type": "summarize"}],
             "workflow": {"steps": [
                 {"id": "s1", "agentId": "intake", "toolIds": ["summarize"],
                  "instruction": "Restate the request.", "requiresApproval": False},
                 {"id": "s2", "agentId": "reporter", "toolIds": ["summarize"],
                  "instruction": "Write the result.", "requiresApproval": False},
             ]}}
        out = dtypes.validate_definition(copy.deepcopy(d))
        self.assertEqual(out, d)                       # nothing lost, nothing changed
        g = dtypes.as_graph(out)
        self.assertEqual([n["id"] for n in g["nodes"]],
                         ["intake", "report-drafter", "reporter"])
        self.assertTrue(g["nodes"][2].get("placeholder"))
        self.assertEqual(len(g["edges"]), 2)

    def test_duplicate_display_name_agents_repaired_not_deleted(self):
        """Two agents whose names slug to the same id must both survive —
        the second one's instructions are a person's work. Deterministic
        suffix, idempotent under re-validation."""
        d = {"agents": [{"id": "checker", "name": "Checker", "instructions": "A"},
                        {"id": "checker", "name": "Checker", "instructions": "B"}]}
        out = dtypes.validate_definition(d)
        self.assertEqual([a["id"] for a in out["agents"]], ["checker", "checker-2"])
        self.assertEqual([a["instructions"] for a in out["agents"]], ["A", "B"])
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(out)), out)

    def test_repair_never_steals_a_later_declared_id(self):
        """Agents named 'Checker', 'Checker', 'Checker 2' slug to ids
        [checker, checker, checker-2]. The repaired duplicate must NOT take
        'checker-2' — that id has a declared owner, and stealing it would
        silently rebind an unambiguous step reference to the wrong agent."""
        d = {"agents": [{"id": "checker", "instructions": "A"},
                        {"id": "checker", "instructions": "B"},
                        {"id": "checker-2", "instructions": "C"}],
             "workflow": {"steps": [{"agentId": "checker-2"}]}}
        out = dtypes.validate_definition(d)
        self.assertEqual([a["id"] for a in out["agents"]],
                         ["checker", "checker-3", "checker-2"])
        by_id = {a["id"]: a["instructions"] for a in out["agents"]}
        self.assertEqual(by_id["checker-2"], "C")      # declared owner keeps it
        g = dtypes.as_graph(out)
        target = g["edges"][0]["target"]
        node = next(n for n in g["nodes"] if n["id"] == target)
        self.assertEqual(node["instructions"], "C")
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(out)), out)

    def test_tool_repair_never_steals_a_later_declared_id(self):
        d = {"tools": [{"id": "t", "type": "search"},
                       {"id": "t", "type": "search"},
                       {"id": "t-2", "type": "compare"}]}
        out = dtypes.validate_definition(d)
        self.assertEqual([(t["id"], t["type"]) for t in out["tools"]],
                         [("t", "search"), ("t-3", "search"), ("t-2", "compare")])

    def test_suffix_ladder_payload_is_linear_not_quadratic(self):
        """40 duplicates against a declared a-2…a-N suffix ladder must not
        rescan the ladder from n=2 per repair — the per-base counter resumes
        where the last search ended, with byte-identical output. Guarded by
        wall-clock generously above linear cost but far below the ~1.3s the
        quadratic rescan measured on this shape."""
        import time
        n = 20000
        agents = ([{"id": "a"}] * 40) + [{"id": f"a-{k}"} for k in range(2, n)]
        t0 = time.monotonic()
        out = dtypes.validate_definition({"agents": agents})
        elapsed = time.monotonic() - t0
        self.assertLess(elapsed, 0.5)
        ids = [a["id"] for a in out["agents"]]
        self.assertEqual(ids[0], "a")
        self.assertEqual(ids[1:], [f"a-{k}" for k in range(n, n + 39)])

    def test_repair_dodges_ids_declared_beyond_the_item_cap(self):
        """The declared-id set spans the FULL incoming list. An id declared
        by item 41 is cap-dropped, but a repair still must not take it — the
        reference should dangle to a placeholder, not silently bind to a
        repaired duplicate."""
        agents = ([{"id": "a", "instructions": "first"},
                   {"id": "a", "instructions": "second"}]
                  + [{"id": f"filler{i}"} for i in range(38)]
                  + [{"id": "a-2", "instructions": "beyond-cap owner"}])
        d = {"agents": agents, "workflow": {"steps": [{"agentId": "a-2"}]}}
        out = dtypes.validate_definition(d)
        self.assertEqual(len(out["agents"]), 40)
        self.assertEqual(out["agents"][1]["id"], "a-3")   # skipped a-2
        g = dtypes.as_graph(out)
        target_node = next(n for n in g["nodes"] if n["id"] == "a-2")
        self.assertTrue(target_node.get("placeholder"))

    def test_id_length_cap_clears_builder_slugs(self):
        """The builder mints ids from uncapped display names; the cap must
        clear any name a person would type (86-char slugs are real) while
        still bounding hostile input."""
        real_slug = "checks-every-claim-against-the-original-sources-and-flags-anything-unsupported-by-them"
        self.assertLessEqual(len(real_slug), 200)
        out = dtypes.validate_definition({"agents": [{"id": real_slug}]})
        self.assertEqual(out["agents"][0]["id"], real_slug)
        kept = dtypes.validate_definition({"agents": [{"id": "a" * 200}]})
        self.assertEqual(len(kept["agents"]), 1)
        dropped = dtypes.validate_definition({"agents": [{"id": "a" * 201}]})
        self.assertEqual(dropped["agents"], [])

    def test_newlines_in_ids(self):
        """Trailing whitespace is normalised away by the strip; an embedded
        newline is not an id at all. (\\Z in _ID_RE keeps the second truth
        even if the strip ever moved.)"""
        out = dtypes.validate_definition({"agents": [{"id": "abc\n"}]})
        self.assertEqual(out["agents"][0]["id"], "abc")
        out = dtypes.validate_definition({"agents": [{"id": "abc\ndef"}]})
        self.assertEqual(out["agents"], [])

    def test_unhashable_references_drop_the_part_not_the_request(self):
        """agentId/toolIds are matched against sets; an unhashable value must
        cost the step or the entry, never raise TypeError out of a validator
        that promises never to."""
        d = {"agents": [{"id": "a"}],
             "tools": [{"id": "t", "type": "search"}],
             "workflow": {"steps": [
                 {"agentId": ["a"]},
                 {"agentId": {"id": "a"}},
                 {"agentId": "a", "toolIds": [["t"], {"t": 1}, "t"]},
             ]}}
        out = dtypes.validate_definition(d)
        self.assertEqual(len(out["workflow"]["steps"]), 1)
        self.assertEqual(out["workflow"]["steps"][0]["toolIds"], ["t"])
        g = dtypes.as_graph({"agents": [{"id": "a"}],
                             "workflow": {"steps": [{"agentId": ["a"]},
                                                    {"agentId": "a"}]}})
        self.assertEqual(len(g["edges"]), 1)

    def test_tool_with_unknown_type_is_dropped_not_coerced(self):
        out = dtypes.validate_definition(
            {"tools": [{"id": "t", "type": "telepathy"},
                       {"id": "u", "type": "search"}]})
        self.assertEqual([t["id"] for t in out["tools"]], ["u"])

    def test_step_ids_kept_when_valid_never_invented(self):
        d = {"agents": [{"id": "a"}],
             "workflow": {"steps": [{"id": "s1", "agentId": "a"},
                                    {"id": "??", "agentId": "a"},
                                    {"agentId": "a"}]}}
        steps = dtypes.validate_definition(d)["workflow"]["steps"]
        self.assertEqual(steps[0]["id"], "s1")
        self.assertNotIn("id", steps[1])
        self.assertNotIn("id", steps[2])

    def test_duplicate_step_ids_lose_the_id_not_the_step(self):
        d = {"agents": [{"id": "a"}],
             "workflow": {"steps": [{"id": "s1", "agentId": "a"},
                                    {"id": "s1", "agentId": "a"}]}}
        steps = dtypes.validate_definition(d)["workflow"]["steps"]
        self.assertEqual(len(steps), 2)
        self.assertEqual(steps[0]["id"], "s1")
        self.assertNotIn("id", steps[1])

    def test_string_toolids_costs_the_field_not_char_scanned(self):
        """A string where the toolIds list belongs must not char-iterate into
        phantom references to single-character tool ids."""
        d = {"agents": [{"id": "a"}],
             "tools": [{"id": "t", "type": "search"}],
             "workflow": {"steps": [{"agentId": "a", "toolIds": "tx"}]}}
        out = dtypes.validate_definition(d)
        self.assertEqual(out["workflow"]["steps"][0]["toolIds"], [])

    def test_truncation_at_whitespace_is_idempotent(self):
        """If the length cap lands on whitespace, re-validation must be a
        fixed point — not a slow trim that changes the payload every pass."""
        d = {"name": "n" * 119 + " z",
             "agents": [{"id": "a", "instructions": "x" * 1999 + " y"}]}
        once = dtypes.validate_definition(d)
        self.assertEqual(dtypes.validate_definition(copy.deepcopy(once)), once)
        self.assertEqual(once["name"], "n" * 119)
        self.assertEqual(once["agents"][0]["instructions"], "x" * 1999)


class TestApprovalSemantics(unittest.TestCase):
    def test_truthiness_matches_hitl_policy_exactly(self):
        """The validator and the runtime must never disagree on whether a
        step carries a human checkpoint. hitl_policy uses bool(); so do we —
        including the ugly case where the string 'false' means True, because
        adding an unwanted checkpoint is the safe failure and dropping one a
        person set is not."""
        for v in (True, False, "yes", "false", "", 0, 1, None, [], ["x"], {}):
            raw = {"agentId": "a", "requiresApproval": v}
            out = dtypes.validate_definition(
                {"agents": [{"id": "a"}], "workflow": {"steps": [raw]}})
            self.assertEqual(out["workflow"]["steps"][0]["requiresApproval"],
                             requires_approval(raw), repr(v))

    def test_absent_flag_is_false(self):
        out = dtypes.validate_definition(
            {"agents": [{"id": "a"}], "workflow": {"steps": [{"agentId": "a"}]}})
        self.assertIs(out["workflow"]["steps"][0]["requiresApproval"], False)


class TestUnicodeAndSize(unittest.TestCase):
    def test_unicode_text_kept_unicode_ids_dropped(self):
        d = {"agents": [{"id": "ok", "name": "Aidê 分析 🤖", "instructions": "Résumé — 分析"},
                        {"id": "análise"}, {"id": "分析"}, {"id": "a b"}]}
        out = dtypes.validate_definition(d)
        self.assertEqual([a["id"] for a in out["agents"]], ["ok"])
        self.assertEqual(out["agents"][0]["name"], "Aidê 分析 🤖")

    def test_oversized_payload_is_capped_not_fatal(self):
        d = {"agents": [{"id": f"a{i}"} for i in range(1000)],
             "tools": [{"id": f"t{i}", "type": "search"} for i in range(1000)],
             "workflow": {"steps": [{"agentId": "a0", "toolIds": [f"t{i}" for i in range(1000)]}
                                    for _ in range(1000)]},
             "name": "n" * 10_000, "description": "d" * 10_000}
        out = dtypes.validate_definition(d)
        self.assertEqual(len(out["agents"]), 40)
        self.assertEqual(len(out["tools"]), 40)
        self.assertEqual(len(out["workflow"]["steps"]), 40)
        self.assertEqual(len(out["workflow"]["steps"][0]["toolIds"]), 40)
        self.assertEqual(len(out["name"]), 120)
        self.assertEqual(len(out["description"]), 600)

    def test_long_instructions_truncate(self):
        d = {"agents": [{"id": "a", "instructions": "x" * 5000}]}
        self.assertEqual(len(dtypes.validate_definition(d)["agents"][0]["instructions"]),
                         2000)


class TestNeverNegative(unittest.TestCase):
    def test_module_vocabularies_and_defaults_are_clean(self):
        self.assertEqual(stypes.assert_positive(dtypes.empty_definition()), [])
        self.assertEqual(stypes.assert_positive(list(dtypes.SURFACE_TYPES)), [])
        self.assertEqual(stypes.assert_positive(list(dtypes.SURFACE_THEMES)), [])
        self.assertEqual(stypes.assert_positive(list(dtypes.TOOL_TYPES)), [])

    def test_validation_adds_no_negative_language(self):
        """The validator only ever keeps or drops caller text — it must never
        introduce words of its own that violate the never-negative rule."""
        out = dtypes.validate_definition({"agents": [{"id": "a"}], "tools": [],
                                          "workflow": {"steps": [{"agentId": "a"}]}})
        self.assertEqual(stypes.assert_positive(out), [])


class TestGraphProjection(unittest.TestCase):
    def test_chain_edges_with_start_sentinel(self):
        g = dtypes.as_graph(dtypes.validate_definition(builder_definition()))
        self.assertEqual([n["id"] for n in g["nodes"]], ["intake", "evidence"])
        self.assertEqual([(e["source"], e["target"]) for e in g["edges"]],
                         [(dtypes.START, "intake"), ("intake", "evidence")])
        self.assertEqual([e["requiresApproval"] for e in g["edges"]], [False, True])
        self.assertEqual([e["step"] for e in g["edges"]], [0, 1])

    def test_single_step_has_one_edge(self):
        d = dtypes.validate_definition(
            {"agents": [{"id": "solo"}], "workflow": {"steps": [{"agentId": "solo"}]}})
        g = dtypes.as_graph(d)
        self.assertEqual(len(g["edges"]), 1)
        self.assertEqual(g["edges"][0]["source"], dtypes.START)

    def test_revisiting_an_agent_is_legal(self):
        d = dtypes.validate_definition(
            {"agents": [{"id": "a"}, {"id": "b"}],
             "workflow": {"steps": [{"agentId": "a"}, {"agentId": "b"},
                                    {"agentId": "a"}]}})
        g = dtypes.as_graph(d)
        self.assertEqual([(e["source"], e["target"]) for e in g["edges"]],
                         [(dtypes.START, "a"), ("a", "b"), ("b", "a")])

    def test_empty_and_unvalidated_input_degrade_quietly(self):
        self.assertEqual(dtypes.as_graph(dtypes.empty_definition()),
                         {"nodes": [], "edges": []})
        self.assertEqual(dtypes.as_graph(None), {"nodes": [], "edges": []})
        g = dtypes.as_graph({"agents": [{"id": "a"}, "junk"],
                             "workflow": {"steps": [{"agentId": "a"},
                                                    {"agentId": "ghost"}, 7]}})
        self.assertEqual([n["id"] for n in g["nodes"]], ["a", "ghost"])
        self.assertTrue(g["nodes"][1].get("placeholder"))
        self.assertEqual(len(g["edges"]), 2)

    def test_as_graph_never_raises_on_hostile_shapes(self):
        """The projection promises a partial result, never an exception —
        including unhashable ids, non-list collections, and non-list
        toolIds."""
        hostile = [
            {"agents": [{"id": ["x"]}], "workflow": {"steps": []}},
            {"agents": 5},
            {"agents": "ab", "workflow": {"steps": "cd"}},
            {"workflow": {"steps": 9}},
            {"agents": [{"id": "a"}],
             "workflow": {"steps": [{"agentId": "a", "toolIds": 7}]}},
        ]
        for d in hostile:
            g = dtypes.as_graph(d)                       # must not raise
            self.assertEqual(set(g), {"nodes", "edges"}, repr(d))
        g = dtypes.as_graph(hostile[4])
        self.assertEqual(g["edges"][0]["toolIds"], [])


if __name__ == "__main__":
    unittest.main()
