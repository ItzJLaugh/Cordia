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
    def post(self, body, email='owner@example.test', path='/surveyor/skill/execute'):
        handler = object.__new__(training_backend.H)
        handler.path = path
        handler._body = lambda: body
        handler._surv_guard = lambda: (email, None) if email else (None, True)
        handler.response = None
        handler._json = lambda payload, status=200: setattr(
            handler, 'response', (payload, status))
        handler.do_POST()
        return handler.response

    def test_setup_then_allow_execution_keeps_secret_inside_runtime_boundary(self):
        sentinel = 'github_pat_SENTINEL_must_never_escape_the_adapter'
        owner = 'owner@example.test'
        secret_ref = 'secret_github_0123456789abcdef'
        ciphertext = b'encrypted-github-token'
        connector_states = {}
        stored_secret = {}
        events = []
        order = []

        class FakeVault:
            def seal(self, connector, value):
                order.append('seal')
                self_test.assertEqual((connector, value), ('github', sentinel))
                return secret_ref, ciphertext

            def open(self, value):
                order.append('open')
                self_test.assertEqual(value, ciphertext)
                return sentinel

        self_test = self

        def validate_token(token):
            order.append('validate')
            self.assertEqual(token, sentinel)
            return {'repositories': [{'name': 'owner/setup-proof'}],
                    'repository_limit': 30}

        def save_connector_projection(email, states, *, secret, runtime_status):
            order.append('save_connector_projection')
            self.assertEqual(email, owner)
            ref, connector, encrypted = secret
            self.assertEqual((ref, connector, runtime_status),
                             (secret_ref, 'github', 'live'))
            self.assertEqual(encrypted, ciphertext)
            self.assertNotIn(sentinel.encode(), encrypted)
            stored_secret['value'] = (ref, encrypted)
            connector_states.clear()
            connector_states.update(states)
            return {'status': 'committed', 'connector_states': dict(connector_states)}

        def save_connector_runtime_projection(email, connector, status):
            order.append('save_connector_runtime_projection')
            self.assertEqual((email, connector, status), (owner, 'github', 'live'))
            return {'status': 'committed'}

        def get_secret(email, connector):
            order.append('get_secret')
            self.assertEqual((email, connector), (owner, 'github'))
            return stored_secret.get('value')

        def list_repositories(token):
            order.append('adapter')
            self.assertEqual(token, sentinel)
            return {
                'repositories': [{
                    'name': f'owner/repository-{index}',
                    'description': r'C:\private\provider-detail',
                    'token': 'ghp_provider_row_must_not_escape',
                } for index in range(35)],
                'repository_limit': 30,
            }

        def log_event(email, kind, payload):
            events.append((email, kind, payload))
            if kind == 'connector_secret_used':
                order.append('secret_audit')

        with patch.object(training_backend.surveyor.github_connector, 'validate_token',
                          side_effect=validate_token), \
                patch.object(training_backend.surveyor.github_connector, 'list_repositories',
                             side_effect=list_repositories), \
                patch.object(training_backend.surveyor.vault, 'from_environment',
                             return_value=FakeVault()), \
                patch.object(training_backend.surveyor.store, 'get_secret',
                             side_effect=get_secret), \
                patch.object(training_backend.surveyor.store, 'get_connector_states',
                             side_effect=lambda _email: dict(connector_states)), \
                patch.object(training_backend.surveyor.store, 'save_connector_projection',
                             side_effect=save_connector_projection), \
                patch.object(training_backend.surveyor.store, 'save_connector_runtime_projection',
                             side_effect=save_connector_runtime_projection), \
                patch.object(training_backend.surveyor.store, 'workspaces', return_value=[]), \
                patch.object(training_backend.surveyor.store, 'log_event',
                             side_effect=log_event):
            setup, setup_status = self.post(
                {'token': sentinel}, owner, '/surveyor/github/token')
            response, status = self.post({'id': 'github_repository_review'}, owner)

        self.assertEqual(setup_status, 200)
        self.assertEqual(setup, {
            'ok': True,
            'secret_ref': secret_ref,
            'connector_state': 'confirmed',
            'repository_limit': 30,
        })
        self.assertEqual(status, 200)
        self.assertEqual(response, {
            'ok': True,
            'skill_id': 'github_repository_review',
            'result': {'repository_count': 30},
        })
        self.assertEqual(order, [
            'validate', 'seal', 'save_connector_projection',
            'get_secret', 'open', 'secret_audit', 'adapter',
            'save_connector_runtime_projection',
        ])
        self.assertEqual(events, [
            (owner, 'github_secret_configured', {
                'secret_ref': secret_ref,
                'repository_count': 1,
            }),
            (owner, 'connector_secret_used', {
                'connector': 'github',
                'secret_ref': secret_ref,
                'capability': 'github.read_repositories',
            }),
            (owner, 'skill_executed', {
                'id': 'github_repository_review',
                'repository_count': 30,
            }),
        ])
        public_trace = repr((setup, response, events))
        self.assertNotIn(sentinel, public_trace)
        self.assertNotIn(repr(ciphertext), public_trace)
        self.assertNotIn(r'C:\private\provider-detail', public_trace)
        self.assertNotIn('ghp_provider_row_must_not_escape', public_trace)

    def test_executes_confirmed_allow_skill_and_returns_only_bounded_receipt(self):
        events = []
        secret_ref = 'secret_github_fedcba9876543210'
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
                             return_value=(secret_ref, b'ciphertext')), \
                patch.object(training_backend.surveyor.vault, 'from_environment',
                             return_value=vault), \
                patch.object(training_backend.surveyor.github_connector, 'list_repositories',
                             return_value={'repositories': repositories, 'repository_limit': 30}), \
                patch.object(training_backend.surveyor.store, 'save_connector_runtime_projection',
                             return_value={'status': 'committed'}), \
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
        self.assertEqual(events, [
            ('owner@example.test', 'connector_secret_used', {
                'connector': 'github',
                'secret_ref': secret_ref,
                'capability': 'github.read_repositories',
            }),
            ('owner@example.test', 'skill_executed',
             {'id': 'github_repository_review', 'repository_count': 30}),
        ])
        rendered = repr(response)
        self.assertNotIn('private', rendered.lower())
        self.assertNotIn('token', rendered.lower())
        self.assertNotIn('secret-ref', rendered.lower())

    def test_malformed_secret_reference_stops_before_decryption_adapter_and_audit(self):
        events = []
        malicious_ref = r'C:\private\ghp_must_not_reach_audit'

        with patch.object(training_backend.surveyor.store, 'get_connector_states',
                          return_value={'github': 'confirmed'}), \
                patch.object(training_backend.surveyor.store, 'get_secret',
                             return_value=(malicious_ref, b'ciphertext')), \
                patch.object(training_backend.surveyor.vault, 'from_environment') as vault, \
                patch.object(training_backend.surveyor.github_connector, 'list_repositories') as adapter, \
                patch.object(training_backend.surveyor.store, 'workspaces', return_value=[]), \
                patch.object(training_backend.surveyor.store, 'log_event',
                             side_effect=lambda email, kind, payload: events.append(
                                 (email, kind, payload))):
            response, status = self.post({'id': 'github_repository_review'})

        self.assertEqual(status, 503)
        self.assertFalse(response['ok'])
        self.assertNotIn(malicious_ref, repr(response))
        self.assertNotIn('ghp_must_not_reach_audit', repr(events))
        vault.assert_not_called()
        adapter.assert_not_called()

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
