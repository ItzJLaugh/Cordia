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
