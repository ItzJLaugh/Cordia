import os, sys, unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

sys.modules['cordia_auth'] = SimpleNamespace()
import training_backend
from surveyor import fde_routing, skills


class TestFdeRegistryEndpoint(unittest.TestCase):
 def handler(self, email='person@example.test'):
  handler = object.__new__(training_backend.H)
  handler.path = '/surveyor/fde-recommendations'
  handler._surv_guard = lambda: (email, None) if email else (None, True)
  handler.response = None
  handler._json = lambda payload, status=200: setattr(handler, 'response', (payload, status))
  return handler

 def test_authenticated_endpoint_returns_safe_advisory_recommendations(self):
  handler = self.handler()
  profile = {
   'signals': {'domain': 'developer', 'primary_goal': 'repository delivery'},
   'evidence': [{'criterion': 'local_repository', 'summary': 'C:/private/repo',
                 'confidence': 'high'}],
  }
  surveyor = SimpleNamespace(
   pipeline=SimpleNamespace(load_profile=lambda _email: profile),
   store=SimpleNamespace(get_connector_states=lambda _email: {
    'github': 'confirmed', 'desktop.local_repository': 'confirmed'}),
   skills=skills, fde_routing=fde_routing,
  )
  with patch.object(training_backend, 'surveyor', surveyor):
   handler._surv_fde_recommendations()
  payload, status = handler.response
  self.assertEqual(status, 200)
  self.assertTrue(payload['ok'])
  self.assertIn('recommendations', payload)
  self.assertIn('blocked', payload)
  self.assertIn('local_git_status_wait', [item['id'] for item in payload['recommendations']])
  self.assertNotIn('C:/private/repo', repr(payload))
  self.assertNotIn('execute', payload)

 def test_unauthenticated_endpoint_returns_only_the_existing_guard_error(self):
  handler = self.handler(email=None)
  handler._surv_fde_recommendations()
  self.assertIsNone(handler.response)

 def test_endpoint_only_reads_routing_state_and_never_executes_or_writes(self):
  handler = self.handler()
  def forbidden(*_args, **_kwargs):
   raise AssertionError('recommendation endpoint must not mutate or execute')
  store = SimpleNamespace(
   get_connector_states=lambda _email: {'github': 'suggested'},
   save_connector_states=forbidden, save_secret=forbidden, log_event=forbidden,
  )
  surveyor = SimpleNamespace(
   pipeline=SimpleNamespace(load_profile=lambda _email: {'signals': {}, 'evidence': []}),
   store=store, skills=skills, fde_routing=fde_routing, execute=forbidden,
  )
  with patch.object(training_backend, 'surveyor', surveyor):
   handler._surv_fde_recommendations()
  payload, status = handler.response
  self.assertEqual(status, 200)
  self.assertTrue(payload['ok'])
  self.assertEqual(payload['recommendations'], [])


if __name__ == '__main__': unittest.main()
