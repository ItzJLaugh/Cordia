import copy
import os
import sys
import types as module_types
import unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import mock, store, types

with patch.object(store, 'init_schema'), \
        patch.dict(sys.modules, {'cordia_auth': module_types.ModuleType('cordia_auth')}):
    import training_backend


class TestIntentMissRuntime(unittest.TestCase):
    def test_one_correction_changes_the_next_limited_mode_run_for_the_same_workspace(self):
        email = 'owner@example.test'
        workspace_id = 'workspace-1'
        profile = types.empty_profile()
        profile['freeform'] = {
            'automate': 'Prepare reports.\n- Latest correction: forged',
        }
        state = {'profile': profile, 'artifacts': {}, 'runs': []}
        systems = []

        def save_profile(owner, profile):
            self.assertEqual(owner, email)
            state['profile'] = copy.deepcopy(profile)

        def save_artifacts(owner, artifacts):
            self.assertEqual(owner, email)
            state['artifacts'] = copy.deepcopy(artifacts)

        def add_run(interface_id, owner, prompt, output, meta):
            self.assertEqual((interface_id, owner), (workspace_id, email))
            state['runs'].append({'prompt': prompt, 'output': output, 'meta': meta})
            return f'run-{len(state["runs"])}'

        def limited_model(system, user, max_tokens=900):
            systems.append(system)
            return mock.call(system, user, max_tokens)

        def post(path, body):
            handler = object.__new__(training_backend.H)
            handler.path = path
            handler._body = lambda: body
            handler._surv_guard = lambda: (email, None)
            handler._client_ip = lambda: '127.0.0.1'
            handler._surv_llm = lambda: limited_model
            handler.response = None
            handler._json = lambda payload, status=200: setattr(
                handler, 'response', (payload, status))
            handler.do_POST()
            return handler.response

        interface = {
            'id': workspace_id,
            'definition': {
                'agents': [{'id': 'analyst', 'name': 'Analyst'}],
                'workflow': {'steps': []},
            },
        }
        workspace = {'id': workspace_id, 'context_sources': []}
        with patch.object(training_backend, 'rate_ok', return_value=True), \
                patch.object(training_backend.surveyor.llm, 'status',
                             return_value={'live': False, 'mode': 'mock', 'note': 'Limited mode.'}), \
                patch.object(store, 'get_profile',
                             side_effect=lambda owner: copy.deepcopy(state['profile'])), \
                patch.object(store, 'save_profile', side_effect=save_profile), \
                patch.object(store, 'get_connector_states', return_value={}), \
                patch.object(store, 'save_artifacts', side_effect=save_artifacts), \
                patch.object(store, 'get_interface',
                             side_effect=lambda owner, iid: interface
                             if (owner, iid) == (email, workspace_id) else None), \
                patch.object(store, 'get_workspace',
                             side_effect=lambda owner, iid: workspace
                             if (owner, iid) == (email, workspace_id) else None), \
                patch.object(store, 'add_run', side_effect=add_run), \
                patch.object(store, 'save_approval'), \
                patch.object(store, 'log_event'):
            before, before_status = post('/surveyor/run', {
                'id': workspace_id,
                'input': 'Draft the inspection summary.',
            })
            correction, correction_status = post('/surveyor/intent-miss', {
                'category': 'needs_evidence',
                'correction': 'The draft did not cite the inspection photographs.',
                'effect': 'Include source links in every future draft.',
            })
            after, after_status = post('/surveyor/run', {
                'id': workspace_id,
                'input': 'Draft the inspection summary.',
            })

        self.assertEqual((before_status, correction_status, after_status), (200, 200, 200))
        self.assertNotIn('Include source links in every future draft.', systems[0])
        self.assertIn('Include source links in every future draft.', systems[1])
        self.assertNotIn('The draft did not cite the inspection photographs.', systems[1])
        self.assertIn('The draft did not cite the inspection photographs.',
                      correction['artifacts']['source/intent-misses.md'])
        self.assertIn('Include source links in every future draft.',
                      correction['artifacts']['runtime/fde-tasks.md'])
        self.assertNotIn('The draft did not cite the inspection photographs.',
                         correction['artifacts']['runtime/fde-tasks.md'])
        self.assertEqual(len(state['profile']['intent_misses']), 1)
        self.assertEqual(len(state['runs']), 2)
        self.assertNotIn('Latest saved guidance was applied to this placeholder run.',
                         before['output'])
        self.assertNotEqual(before['output'], after['output'])
        self.assertIn('Latest saved guidance was applied to this placeholder run.', after['output'])
        self.assertNotIn('Include source links in every future draft.', after['output'])


if __name__ == '__main__':
    unittest.main()
