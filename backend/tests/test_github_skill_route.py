import os
import sys
import types as module_types
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import store

with patch.object(store, 'init_schema'), \
        patch.dict(sys.modules, {'cordia_auth': module_types.ModuleType('cordia_auth')}):
    import training_backend


class TestGitHubSkillRoute(unittest.TestCase):
    def post(self, body, email='owner@example.test'):
        handler = object.__new__(training_backend.H)
        handler.path = '/surveyor/skill/execute'
        handler._body = lambda: body
        handler._surv_guard = lambda: (email, None) if email else (None, True)
        handler.response = None
        handler._json = lambda payload, status=200: setattr(
            handler, 'response', (payload, status))
        handler.do_POST()
        return handler.response

    def test_executes_confirmed_allow_skill_and_returns_only_bounded_receipt(self):
        events = []
        vault = SimpleNamespace(open=lambda ciphertext: 'ghp_private_execution_token')
        repositories = [
            {
                'name': f'owner/repository-{index}',
                'description': 'C:\\private\\provider-detail',
                'token': 'must-not-leak',
            }
            for index in range(35)
        ]

        with patch.object(training_backend.surveyor.store, 'get_connector_states',
                          return_value={'github': 'confirmed'}), \
                patch.object(training_backend.surveyor.store, 'get_secret',
                             return_value=('secret-ref-private', b'ciphertext')), \
                patch.object(training_backend.surveyor.vault, 'from_environment',
                             return_value=vault), \
                patch.object(training_backend.surveyor.github_connector, 'list_repositories',
                             return_value={'repositories': repositories, 'repository_limit': 30}), \
                patch.object(training_backend.surveyor.store, 'workspaces', return_value=[]), \
                patch.object(training_backend.surveyor.store, 'log_event',
                             side_effect=lambda email, kind, payload: events.append(
                                 (email, kind, payload))):
            response, status = self.post({'id': 'github_repository_review'})

        self.assertEqual(status, 200)
        self.assertEqual(response, {
            'ok': True,
            'skill_id': 'github_repository_review',
            'result': {'repository_count': 30},
        })
        self.assertEqual(events, [(
            'owner@example.test', 'skill_executed',
            {'id': 'github_repository_review', 'repository_count': 30},
        )])
        rendered = repr(response)
        self.assertNotIn('private', rendered.lower())
        self.assertNotIn('token', rendered.lower())
        self.assertNotIn('secret-ref', rendered.lower())

    def test_unconfirmed_github_stops_before_secret_resolution(self):
        with patch.object(training_backend.surveyor.store, 'get_connector_states',
                          return_value={'github': 'suggested'}), \
                patch.object(training_backend.surveyor.store, 'get_secret',
                             side_effect=AssertionError('secret must not be resolved')), \
                patch.object(training_backend.surveyor.store, 'workspaces', return_value=[]), \
                patch.object(training_backend.surveyor.store, 'log_event'):
            response, status = self.post({'id': 'github_repository_review'})

        self.assertEqual(status, 409)
        self.assertFalse(response['ok'])
        self.assertNotIn('secret', repr(response).lower())


if __name__ == '__main__':
    unittest.main()
