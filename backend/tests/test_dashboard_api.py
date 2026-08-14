#!/usr/bin/env python3
"""Tests for dashboard.api — the pure half of the /dashboard/* routes.

The route adapters in training_backend.py are thin (guard, store call,
JSON writer) and are exercised against the running local backend during
manual verification; everything with decision content lives in
dashboard.api and is tested here without a server, session, or database.

Stdlib unittest only. Run from backend/:
    python3 -m unittest tests.test_dashboard_api -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dashboard import api, framework as fw, types as dtypes
from surveyor import types as stypes
from tests.envhermetic import EnvHermeticCase


class TestSaveInterfaceRequest(EnvHermeticCase):
    def _valid_body(self):
        return {"name": "My workspace", "description": "For checks.",
                "definition": {"agents": [{"id": "a", "name": "A"}],
                               "tools": [],
                               "workflow": {"steps": [{"agentId": "a"}]}}}

    def test_valid_body_shapes_cleanly(self):
        err, cleaned = api.save_interface_request(self._valid_body())
        self.assertIsNone(err)
        self.assertIsNone(cleaned["id"])
        self.assertEqual(cleaned["name"], "My workspace")
        self.assertEqual(cleaned["definition"],
                         dtypes.validate_definition(self._valid_body()["definition"]))

    def test_non_dict_body_and_definition_are_rejected(self):
        for bad in (None, [], "x", 7):
            err, cleaned = api.save_interface_request(bad)
            self.assertEqual(err, "invalid request", repr(bad))
            self.assertIsNone(cleaned)
        for bad in (None, [], "x", 7, True):
            err, cleaned = api.save_interface_request({"definition": bad})
            self.assertEqual(err, "definition must be an object", repr(bad))

    def test_null_id_means_create_not_the_string_none(self):
        """The _surv_save_interface lesson: str(None) is truthy 'None'."""
        body = self._valid_body()
        for null_id in (None, "", "   "):
            body["id"] = null_id
            err, cleaned = api.save_interface_request(body)
            self.assertIsNone(err)
            self.assertIsNone(cleaned["id"], repr(null_id))
        body["id"] = 42
        err, cleaned = api.save_interface_request(body)
        self.assertEqual(cleaned["id"], "42")

    def test_name_and_description_caps_match_surveyor_route(self):
        body = self._valid_body()
        body["name"] = "n" * 500
        body["description"] = "d" * 5000
        err, cleaned = api.save_interface_request(body)
        self.assertEqual(len(cleaned["name"]), 120)
        self.assertEqual(len(cleaned["description"]), 600)

    def test_name_falls_back_to_definition_then_untitled(self):
        body = self._valid_body()
        body["name"] = "   "
        body["definition"]["name"] = "From the definition"
        err, cleaned = api.save_interface_request(body)
        self.assertEqual(cleaned["name"], "From the definition")
        del body["definition"]["name"]
        err, cleaned = api.save_interface_request(body)
        self.assertEqual(cleaned["name"], "Untitled interface")

    def test_theme_must_be_a_dict_or_is_dropped(self):
        body = self._valid_body()
        body["theme"] = {"accent": "moss"}
        self.assertEqual(api.save_interface_request(body)[1]["theme"],
                         {"accent": "moss"})
        body["theme"] = "dark; drop table"
        self.assertIsNone(api.save_interface_request(body)[1]["theme"])

    def test_definition_is_canonicalised_before_storage(self):
        body = self._valid_body()
        body["definition"]["agents"].append("junk")
        body["definition"]["workflow"]["steps"].append({"agentId": ["boom"]})
        err, cleaned = api.save_interface_request(body)
        self.assertIsNone(err)
        self.assertEqual(cleaned["definition"],
                         dtypes.validate_definition(cleaned["definition"]))

    def test_never_negative_on_shaped_output(self):
        err, cleaned = api.save_interface_request(self._valid_body())
        self.assertEqual(stypes.assert_positive(cleaned), [])

    def test_lossy_definitions_are_refused_not_truncated(self):
        """The sweep's confirmed ship-blocker: a save must never silently
        delete well-formed data. Over-cap lists, unsupported tool types and
        unknown top-level keys refuse with a plain-English error."""
        body = self._valid_body()
        body["definition"]["agents"] = [{"id": f"a{i}"} for i in range(201)]
        err, cleaned = api.save_interface_request(body)
        self.assertIsNone(cleaned)
        self.assertIn("more than 200 agents", err)
        self.assertEqual(stypes.assert_positive(err), [])

        body = self._valid_body()
        body["definition"]["junkTop"] = "another surface's data"
        err, cleaned = api.save_interface_request(body)
        self.assertIsNone(cleaned)
        self.assertIn("junkTop", err)

    def test_large_but_legal_definition_saves_without_loss(self):
        body = self._valid_body()
        body["definition"] = {
            "agents": [{"id": f"a{i}"} for i in range(45)],
            "workflow": {"steps": [{"agentId": f"a{i}"} for i in range(45)]},
        }
        err, cleaned = api.save_interface_request(body)
        self.assertIsNone(err)
        self.assertEqual(len(cleaned["definition"]["agents"]), 45)
        self.assertEqual(len(cleaned["definition"]["workflow"]["steps"]), 45)


class TestStoredRowConflict(EnvHermeticCase):
    """The second half of the write guard: an edit must refuse when the
    STORED row holds content the dashboard cannot represent — the read path
    canonicalises, so the incoming payload always looks clean."""

    def test_clean_stored_rows_do_not_conflict(self):
        self.assertIsNone(api.stored_row_conflict(
            {"agents": [{"id": "a"}], "workflow": {"steps": []}}))
        self.assertIsNone(api.stored_row_conflict(None))
        self.assertIsNone(api.stored_row_conflict("junk"))

    def test_blocked_stored_rows_refuse_with_builder_pointer(self):
        stored = {"agents": [{"id": f"a{i}"} for i in range(201)],
                  "customTopLevel": "another surface's data"}
        msg = api.stored_row_conflict(stored)
        self.assertIn("more than 200 agents", msg)
        self.assertIn("open it in the builder instead", msg)
        self.assertEqual(stypes.assert_positive(msg), [])


class TestRunRequest(EnvHermeticCase):
    def test_valid_run_request(self):
        err, req = api.run_request({"id": " abc ", "input": " do the thing "})
        self.assertIsNone(err)
        self.assertEqual(req, {"id": "abc", "input": "do the thing"})

    def test_missing_id_and_input_are_distinct_errors(self):
        self.assertEqual(api.run_request({"input": "x"})[0], "id required")
        self.assertEqual(api.run_request({"id": "a"})[0], "input required")
        self.assertEqual(api.run_request({"id": None, "input": "x"})[0], "id required")
        self.assertEqual(api.run_request("junk")[0], "invalid request")

    def test_input_capped_at_run_limit(self):
        err, req = api.run_request({"id": "a", "input": "x" * 100_000})
        self.assertEqual(len(req["input"]), api.MAX_RUN_INPUT)

    def test_whitespace_only_input_rejected_even_when_long(self):
        self.assertEqual(api.run_request({"id": "a", "input": " " * 50})[0],
                         "input required")


class TestSkillsSearchRequest(EnvHermeticCase):
    def test_client_framework_wins_when_dict(self):
        req = api.skills_search_request({"framework": {"role_view": "graph"},
                                         "intent": "map"}, {"role_view": "oversight"})
        self.assertEqual(req["framework"], {"role_view": "graph"})

    def test_profile_framework_backstops_junk(self):
        profile_fw = fw.framework_from_profile(None)
        for junk in (None, "x", 7, ["role_view"]):
            req = api.skills_search_request({"framework": junk}, profile_fw)
            self.assertEqual(req["framework"], profile_fw, repr(junk))
        req = api.skills_search_request("not-a-body", profile_fw)
        self.assertEqual(req["framework"], profile_fw)

    def test_limit_default_and_passthrough(self):
        self.assertEqual(api.skills_search_request({}, {})["limit"], 8)
        self.assertEqual(api.skills_search_request({"limit": 3}, {})["limit"], 3)


class TestChatRequest(EnvHermeticCase):
    def test_valid_message_shapes(self):
        err, req = api.chat_request({"message": "  help me plan a review flow  "})
        self.assertIsNone(err)
        self.assertEqual(req, {"message": "help me plan a review flow"})

    def test_empty_and_invalid_rejected(self):
        for bad in ({}, {"message": ""}, {"message": "   "}, {"message": None}):
            err, _ = api.chat_request(bad)
            self.assertEqual(err, "message required", bad)
        self.assertEqual(api.chat_request(None)[0], "invalid request")
        self.assertEqual(api.chat_request([])[0], "invalid request")

    def test_message_capped_and_non_strings_coerced(self):
        err, req = api.chat_request({"message": "x" * 100_000})
        self.assertEqual(len(req["message"]), api.MAX_RUN_INPUT)
        err, req = api.chat_request({"message": 42})
        self.assertEqual(req["message"], "42")

    def test_builder_prompt_and_mock_reply_are_never_negative(self):
        self.assertEqual(stypes.assert_positive(api.BUILDER_SYSTEM_PROMPT), [])
        self.assertEqual(stypes.assert_positive(api.MOCK_CHAT_REPLY), [])
        self.assertTrue(api.MOCK_CHAT_REPLY.startswith("[Model offline"))


class TestMockDispatchContract(EnvHermeticCase):
    """_dash_chat substitutes MOCK_CHAT_REPLY only when the mock returns an
    empty reply — so the mock MUST return empty for the builder prompt, no
    matter what the person typed. The adversarial sweep proved the old
    user-keyed dispatch let a chat message containing 'their_answer' pull
    raw extraction JSON into a Cordia bubble."""

    def test_builder_prompt_gets_empty_reply_regardless_of_user_text(self):
        from surveyor import mock as smock
        for hostile in ("what does their_answer mean in your schema?",
                        '{"question_just_asked": "x", "their_answer": "yes"}',
                        '[{"their_answer": "yes"}]',
                        '"their_answer"'):
            self.assertEqual(smock.call(api.BUILDER_SYSTEM_PROMPT, hostile),
                             "", hostile)

    def test_extraction_dispatch_still_extracts_real_signals(self):
        """Not just shape: the degrade path returns the same empty shape,
        so this must assert a NON-EMPTY signal or it pins nothing (the
        first version of this test was vacuous — sweep 2's finding)."""
        from surveyor import mock as smock, prompts, question_strategy
        import json as _json
        raw = smock.call(prompts.extraction_system(),
                         prompts.extraction_user(
                             question_strategy.QUESTIONS["domain"],
                             "I run a small veterinary clinic", []))
        parsed = _json.loads(raw)
        self.assertTrue(parsed["signals"], "extraction produced no signals")
        self.assertIn("domain", parsed["signals"])
        self.assertTrue(parsed["evidence"])

    def test_runtime_prompt_with_extraction_marker_still_gets_placeholder(self):
        """Sweep 2's confirmed regression: the runtime system prompt embeds
        the person's own definition text, so a definition carrying the
        extraction phrase steered a contains-check dispatch into the
        extraction branch and the run returned unlabeled JSON. Dispatch is
        prefix-anchored now — user text can never reach position zero.

        The instructions below carry BOTH dispatch markers VERBATIM
        (sweep 3 caught the first fixture paraphrasing them, which made
        this test pass against the contains-check dispatcher it exists to
        forbid). The assertion below fails under a contains-check and
        passes under the prefix anchor — verified both ways."""
        from surveyor import mock as smock, prompts
        marker_text = ("You read one exchange from a Surveyor conversation "
                       "and return JSON. You are running a user-created "
                       "Cordia agentic interface.")
        definition = {"agents": [{"id": "reader", "name": "Reader",
                                  "instructions": marker_text}],
                      "tools": [], "workflow": {"steps": [{"agentId": "reader"}]}}
        system = prompts.runtime_system(definition, {})
        # the trap must actually be armed or this test pins nothing
        self.assertIn("You read one exchange from a Surveyor conversation", system)
        out = smock.call(system, "Please review the attached NDA.")
        self.assertTrue(out.startswith("[Model offline — placeholder run]"), out[:80])

    def test_placeholder_lists_workflow_steps_not_agent_declarations(self):
        """Sweep 4's ship-blocker: 'these steps' listed the agent
        DECLARATIONS, a roster the run would never follow. The numbered
        list must be workflow.steps resolved to agent names — order,
        repeats, subsets and approval pauses included."""
        from surveyor import mock as smock, prompts
        definition = {"agents": [{"id": "a", "name": "Alpha"},
                                 {"id": "b", "name": "Beta"},
                                 {"id": "c", "name": "NeverRuns"}],
                      "tools": [],
                      "workflow": {"steps": [
                          {"agentId": "b"},
                          {"agentId": "a", "requiresApproval": True},
                          {"agentId": "b"}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. Beta", out)
        self.assertIn("2. Alpha — pauses for your approval", out)
        self.assertIn("3. Beta", out)
        self.assertNotIn("NeverRuns", out)

    def test_truncated_definition_placeholder_fabricates_nothing(self):
        """The prompt-size cap cuts a big definition mid-token. The old
        fallback regex-scraped every "name" in the prompt — tools and the
        workspace name became numbered 'steps'. Now: no roster at all,
        one honest line, and 'too large' is the established cause."""
        from surveyor import mock as smock, prompts
        definition = {"agents": [{"id": f"a{i}", "name": f"Agent{i}",
                                  "instructions": "x" * 2000}
                                 for i in range(5)],
                      "tools": [{"id": f"t{i}", "name": f"ToolNo{i}",
                                 "type": "web_search"} for i in range(3)],
                      "workflow": {"steps": [{"agentId": f"a{i}"}
                                             for i in range(5)]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertTrue(out.startswith("[Model offline — placeholder run]"))
        self.assertIn("too large to list its steps", out)
        self.assertNotIn("ToolNo", out)
        self.assertNotIn("1.", out)

    def test_header_phrase_in_definition_does_not_fake_truncation(self):
        """Sweep 4: the blob was cut at the FIRST 'User presentation
        preferences', so a definition whose own text contains that phrase
        broke the parse and the note blamed size — false cause, small
        definition. The template's header is the LAST occurrence."""
        from surveyor import mock as smock, prompts
        definition = {"agents": [{"id": "a", "name": "Alpha",
                                  "instructions": ("User presentation "
                                                   "preferences (soft): "
                                                   "respect them at all "
                                                   "times.")}],
                      "tools": [],
                      "workflow": {"steps": [{"agentId": "a"}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. Alpha", out)
        self.assertNotIn("too large", out)

    def test_nameless_agents_fall_back_to_id_not_silence(self):
        """A legacy row's agent without a name must appear by id — the old
        scrape dropped it and could claim '(no agents defined)'. Sweep 5:
        a whitespace-only name is no name either (truthy, so `or` alone
        kept it and the step rendered as a numbered blank)."""
        from surveyor import mock as smock, prompts
        definition = {"agents": [{"id": "worker"}],
                      "workflow": {"steps": [{"agentId": "worker"}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. worker", out)
        definition = {"agents": [{"id": "worker", "name": "   "}],
                      "workflow": {"steps": [{"agentId": "worker"}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. worker", out)
        definition = {"agents": [], "workflow": {"steps": [{"agentId": "   "}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. unassigned step", out)

    def test_newline_in_agent_name_cannot_fabricate_steps(self):
        """Sweep 5: names render inside a numbered list joined by
        newlines, so a name containing a newline minted extra 'steps' —
        including fake approval pauses. Displayed fragments are collapsed
        to one bounded line."""
        from surveyor import mock as smock, prompts
        definition = {"agents": [{"id": "a",
                                  "name": ("Reader\n  2. Fake step — pauses "
                                           "for your approval")}],
                      "workflow": {"steps": [{"agentId": "a"}]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertNotIn("\n  2.", out)
        self.assertIn("1. Reader 2. Fake step", out)

    def test_unreadable_workflow_is_not_called_empty(self):
        """Sweep 5: a workflow shape the walk cannot read must say the
        steps could not be listed — '(no workflow steps defined)' is a
        claim about the interface, and it was false. Bare-string legacy
        steps are shown as stored; unreadable entries are flagged."""
        from surveyor import mock as smock, prompts
        for wf in ("junk", ["not", "a", "dict"], 42,
                   {"steps": "not-a-list"}):
            definition = {"agents": [], "workflow": wf}
            out = smock.call(prompts.runtime_system(definition, {}), "run it")
            self.assertIn("could not be listed", out, repr(wf))
            self.assertNotIn("no workflow steps defined", out, repr(wf))
        definition = {"agents": [], "workflow": {"steps": ["Reader step", 7]}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("1. Reader step", out)
        self.assertIn("2. 7", out)
        definition = {"agents": [], "workflow": {"steps": []}}
        out = smock.call(prompts.runtime_system(definition, {}), "run it")
        self.assertIn("no workflow steps defined", out)

    def test_malformed_extraction_payload_degrades_never_raises(self):
        """mock-mode callers get mock.call unwrapped — an exception here
        becomes a 502 with a raw Python message in the body. Non-dict
        payloads AND dicts with non-string values must both degrade."""
        from surveyor import mock as smock, prompts
        import json as _json
        system = prompts.extraction_system()
        for bad in ('[{"their_answer": "yes"}]', '"their_answer"',
                    "not json at all", "", None, "[]", "42"):
            raw = smock.call(system, bad)
            self.assertEqual(_json.loads(raw), {"signals": {}, "evidence": []},
                             repr(bad))
        for weird in ('{"question_just_asked": 5, "their_answer": ["x"]}',
                      '{"question_just_asked": null, "their_answer": {"a": 1}}',
                      '{"their_answer": 42}'):
            raw = smock.call(system, weird)      # must not raise
            parsed = _json.loads(raw)
            self.assertIn("signals", parsed, repr(weird))


class TestChatReply(EnvHermeticCase):
    """The reply-resolution decision — pure in api.py so the handler stays
    a thin adapter (sweep 2: the substitution decision was untestable while
    it lived inline in _dash_chat)."""

    def test_real_replies_pass_through(self):
        self.assertEqual(api.chat_reply("Here is a plan.", False), "Here is a plan.")
        self.assertEqual(api.chat_reply("Here is a plan.", True), "Here is a plan.")

    def test_empty_on_mock_says_offline(self):
        for empty in ("", "   ", None, 0, [], {}):
            self.assertEqual(api.chat_reply(empty, False), api.MOCK_CHAT_REPLY,
                             repr(empty))

    def test_empty_on_live_commits_to_nothing_it_cannot_know(self):
        """live=True + empty is ambiguous: a genuine empty reply, or an
        upstream failure the seam silently mocked away (sweep 3's
        ship-blocker: the first copy asserted 'the model returned an empty
        reply' — false in the failure case — and told the person to
        resend, walking them into the rate limit against a dead upstream).
        The copy may claim neither 'offline' nor that the model returned
        anything, and must not instruct a resend.

        Sweep 6: substring checks alone were evadable ('returned nothing',
        'Send it again' at sentence start), so both placeholder texts are
        pinned VERBATIM — rewriting the copy must consciously rewrite this
        test, with the docstring above stating what any new copy must
        still honour. The case-folded class checks stay as documentation
        of the forbidden claims."""
        for empty in ("", "   ", None):
            self.assertEqual(api.chat_reply(empty, True), api.EMPTY_LIVE_REPLY,
                             repr(empty))
        self.assertEqual(
            api.EMPTY_LIVE_REPLY,
            "[No reply came back] Cordia could not get a model reply for "
            "that message just now. The canvas beside this chat keeps "
            "working either way.")
        self.assertEqual(
            api.MOCK_CHAT_REPLY,
            "[Model offline — placeholder reply] Once the model is "
            "connected, Cordia will help you shape this workspace from "
            "what you describe here. The canvas beside this chat is fully "
            "usable in the meantime.")
        lowered = api.EMPTY_LIVE_REPLY.lower()
        self.assertNotIn("offline", lowered)
        self.assertNotIn("the model returned", lowered)
        self.assertNotIn("send it again", lowered)

    def test_placeholders_announce_themselves_and_are_never_negative(self):
        self.assertTrue(api.EMPTY_LIVE_REPLY.startswith("["))
        self.assertEqual(stypes.assert_positive(api.EMPTY_LIVE_REPLY), [])


class TestOutcomeRequest(EnvHermeticCase):
    def test_interface_id_required(self):
        """The verdict must attach to the interface the person ran — a
        'newest row' target writes false pairings the moment someone owns
        two interfaces."""
        for bad in ({}, {"interface_id": ""}, {"interface_id": "  "},
                    {"interface_id": None}):
            err, req = api.outcome_request(dict({"worked": True}, **bad))
            self.assertEqual(err, "interface_id required", bad)
        err, req = api.outcome_request({"interface_id": " abc123 ", "worked": True})
        self.assertIsNone(err)
        self.assertEqual(req["interface_id"], "abc123")

    def test_explicit_boolean_required(self):
        """'Did this help?' is a person's explicit yes/no — truthy strings
        must not be coerced into a verdict."""
        for bad in ("yes", "true", 1, 0, None, [], {}):
            err, req = api.outcome_request({"interface_id": "i1", "worked": bad})
            self.assertEqual(err, "worked must be true or false", repr(bad))
        for good in (True, False):
            err, req = api.outcome_request({"interface_id": "i1", "worked": good})
            self.assertIsNone(err)
            self.assertIs(req["worked"], good)

    def test_description_optional_capped_and_cleaned(self):
        base = {"interface_id": "i1", "worked": True}
        err, req = api.outcome_request(dict(base, description="  helped  "))
        self.assertEqual(req["description"], "helped")
        err, req = api.outcome_request(dict(base, description="d" * 5000))
        self.assertEqual(len(req["description"]), 600)
        for absent in ({}, {"description": None}, {"description": 7},
                       {"description": "   "}):
            err, req = api.outcome_request(dict(base, **absent))
            self.assertIsNone(req["description"], absent)

    def test_non_dict_body_and_error_copy(self):
        err, req = api.outcome_request(None)
        self.assertEqual(err, "invalid request")
        for bad_body in ({"worked": "maybe", "interface_id": "i1"},
                         {"worked": True}):
            err, _ = api.outcome_request(bad_body)
            self.assertEqual(stypes.assert_positive(err), [], bad_body)


class TestPublicInterface(EnvHermeticCase):
    def test_definition_is_canonicalised(self):
        row = {"id": "i1", "name": "W", "definition": {"agents": [{"id": "a"}, "junk"],
                                                       "workflow": {"steps": "bad"}}}
        out = api.public_interface(row)
        self.assertEqual(out["definition"],
                         dtypes.validate_definition(row["definition"]))
        self.assertEqual(out["id"], "i1")

    def test_non_dict_rows_pass_through_untouched(self):
        self.assertIsNone(api.public_interface(None))
        self.assertEqual(api.public_interface("x"), "x")

    def test_input_row_is_not_mutated(self):
        row = {"id": "i1", "definition": {"agents": [{"id": "a"}, "junk"]}}
        api.public_interface(row)
        self.assertIn("junk", row["definition"]["agents"])


if __name__ == "__main__":
    unittest.main()
