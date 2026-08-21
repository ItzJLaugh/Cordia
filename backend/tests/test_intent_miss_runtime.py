import copy
import json
import os
import sys
import types as module_types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import store, types, workspace_state

with patch.object(store, 'init_schema'), \
        patch.dict(sys.modules, {'cordia_auth': module_types.ModuleType('cordia_auth')}):
    import training_backend


class TestIntentMissRuntime(unittest.TestCase):
    def test_raw_intent_miss_never_enters_a_workspace_turn_prompt_before_memory_compilation(self):
        email = 'owner@example.test'
        workspace_id = 'workspace_1'
        profile = types.empty_profile()
        profile['freeform'] = {'automate': 'Prepare reports.'}
        state = {
            'profile': profile,
            'artifacts': {'source/memory.md': 'Compiled profile memory.'},
            'workspace': workspace_state.empty(workspace_id),
            'runs': {},
        }
        systems = []

        def save_profile(owner, saved_profile):
            self.assertEqual(owner, email)
            state['profile'] = copy.deepcopy(saved_profile)

        def save_artifacts(owner, artifacts):
            self.assertEqual(owner, email)
            state['artifacts'] = copy.deepcopy(artifacts)

        def get_workspace(owner, requested_id):
            if (owner, requested_id) != (email, workspace_id):
                return None
            return copy.deepcopy(state['workspace'])

        def get_run(owner, requested_id, key):
            return copy.deepcopy(state['runs'].get((owner, requested_id, key)))

        def commit_workspace_turn(owner, requested_id, revision, key, _message, result, next_state):
            if (owner, requested_id) != (email, workspace_id):
                return {'status': 'missing'}
            if revision != state['workspace']['revision']:
                return {'status': 'conflict'}
            prior = state['runs'].get((owner, requested_id, key))
            if prior:
                return {'status': 'prior', 'result': copy.deepcopy(prior)}
            state['workspace'] = copy.deepcopy(next_state)
            state['runs'][(owner, requested_id, key)] = copy.deepcopy(result)
            return {'status': 'committed', 'result': copy.deepcopy(result)}

        def deterministic_model(system, _user, max_tokens=900):
            self.assertEqual(max_tokens, 700)
            systems.append(system)
            return json.dumps({'kind': 'speak', 'speech': 'I can help with that.'})

        def post(path, body):
            handler = object.__new__(training_backend.H)
            handler.path = path
            handler._body = lambda: body
            handler._surv_guard = lambda: (email, None)
            handler.response = None
            handler._json = lambda payload, status=200: setattr(
                handler, 'response', (payload, status))
            handler.do_POST()
            return handler.response

        with patch.object(training_backend, 'rate_ok', return_value=True), \
                patch.object(training_backend.surveyor.llm, 'call', side_effect=deterministic_model), \
                patch.object(store, 'get_profile', side_effect=lambda owner: copy.deepcopy(state['profile'])), \
                patch.object(store, 'save_profile', side_effect=save_profile), \
                patch.object(store, 'get_connector_states', return_value={}), \
                patch.object(store, 'save_artifacts', side_effect=save_artifacts), \
                patch.object(store, 'get_artifacts', side_effect=lambda owner: copy.deepcopy(state['artifacts'])), \
                patch.object(store, 'get_workspace', side_effect=get_workspace), \
                patch.object(store, 'get_run_by_idempotency', side_effect=get_run), \
                patch.object(store, 'recent_workspace_turns', return_value=[]), \
                patch.object(store, 'commit_workspace_turn', side_effect=commit_workspace_turn), \
                patch.object(store, 'log_event'):
            before, before_status = post('/surveyor/run', {
                'id': workspace_id, 'revision': 0,
                'message': 'Draft the inspection summary.', 'idempotency_key': 'before_1',
            })
            correction, correction_status = post('/surveyor/intent-miss', {
                'category': 'needs_evidence',
                'correction': 'The draft did not cite the inspection photographs.',
                'effect': 'Include source links in every future draft.',
            })
            after, after_status = post('/surveyor/run', {
                'id': workspace_id, 'revision': 0,
                'message': 'Draft the inspection summary.', 'idempotency_key': 'after_1',
            })

        self.assertEqual((before_status, correction_status, after_status), (200, 200, 200))
        self.assertEqual(before['action'], None)
        self.assertEqual(after['action'], None)
        self.assertIn('The draft did not cite the inspection photographs.',
                      correction['artifacts']['source/intent-misses.md'])
        self.assertIn('Include source links in every future draft.',
                      correction['artifacts']['runtime/fde-tasks.md'])
        self.assertEqual(len(state['profile']['intent_misses']), 1)
        self.assertEqual(len(state['runs']), 2)
        for system in systems:
            self.assertNotIn('The draft did not cite the inspection photographs.', system)
            self.assertNotIn('Include source links in every future draft.', system)


if __name__ == '__main__':
    unittest.main()
