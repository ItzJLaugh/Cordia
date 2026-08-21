import os
import sys
import types as module_types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import llm, model_provider, store

with patch.object(store, "init_schema"), \
        patch.dict(sys.modules, {"cordia_auth": module_types.ModuleType("cordia_auth")}):
    import training_backend


class TestAgentModelStatus(unittest.TestCase):
    def test_missing_configuration_has_honest_public_status(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(llm.status(), {
                "available": False,
                "mode": "unavailable",
                "message": "Cordia Agent is not configured.",
            })

    def test_workspace_agent_reports_unavailable_without_storing_a_run(self):
        email = "owner@example.test"
        handler = object.__new__(training_backend.H)
        handler._surv_guard = lambda: (email, None)
        handler._client_ip = lambda: "127.0.0.1"
        handler.response = None
        handler._json = lambda payload, status=200: setattr(handler, "response", (payload, status))
        interface = {"id": "workspace-1", "definition": {"workflow": {"steps": []}}}

        with patch.object(training_backend, "rate_ok", return_value=True), \
                patch.object(store, "get_interface", return_value=interface), \
                patch.object(store, "get_workspace", return_value={"id": "workspace-1"}), \
                patch.object(training_backend.surveyor.pipeline, "load_profile", return_value={}), \
                patch.object(training_backend.surveyor.pipeline, "artifact_bundle", return_value={}), \
                patch.object(store, "add_run") as add_run, \
                patch.object(store, "save_approval") as save_approval, \
                patch.object(store, "log_event") as log_event, \
                patch.object(training_backend.surveyor.llm, "call",
                             side_effect=model_provider.ModelUnavailable(
                                 "Cordia Agent is not configured.")):
            handler._surv_run({"id": "workspace-1", "input": "Connect my service"})

        self.assertEqual(handler.response, ({
            "ok": False,
            "error": "Cordia Agent is not configured.",
            "kind": "model_unavailable",
        }, 503))
        add_run.assert_not_called()
        save_approval.assert_not_called()
        log_event.assert_not_called()


if __name__ == "__main__":
    unittest.main()
