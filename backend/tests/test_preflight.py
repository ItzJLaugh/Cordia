import os, sys, unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import preflight


@patch.dict(os.environ, {
 'LLM_BASE_URL': 'https://api.openai.com/v1/chat/completions',
 'LLM_MODEL': 'gpt-cordia',
 'LLM_KEY': 'test-secret',
})
class TestPreflight(unittest.TestCase):
 def test_reports_missing_openai_provider_as_named_not_ready_check_without_calling_it(self):
  with patch.dict(os.environ, {}, clear=True), \
       patch('surveyor.model_provider.call', side_effect=AssertionError('no provider call')):
   result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                              'CORDIA_DEV_2FA': '1'}, has_cryptography=True, has_psycopg2=True,
                             database_ready=True, dependency_available=lambda _module: True)
  self.assertFalse(result['ok'])
  self.assertIn('OpenAI model provider', result['missing'])
  self.assertEqual(result['checks']['model_provider'],
                   {'provider': 'openai', 'configured': False, 'model': ''})

 def test_reports_configured_openai_provider_as_ready_without_calling_it(self):
  environment = {'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                 'CORDIA_DEV_2FA': '1',
                 'LLM_BASE_URL': 'https://api.openai.com/v1/chat/completions',
                 'LLM_MODEL': 'gpt-cordia', 'LLM_KEY': 'test-secret'}
  with patch.dict(os.environ, environment, clear=True), \
       patch('surveyor.model_provider.call', side_effect=AssertionError('no provider call')):
   result = preflight.report(environment, has_cryptography=True, has_psycopg2=True,
                             database_ready=True, dependency_available=lambda _module: True)
  self.assertTrue(result['ok'])
  self.assertEqual(result['checks']['model_provider'],
                   {'provider': 'openai', 'configured': True, 'model': 'gpt-cordia'})
  self.assertNotIn('test-secret', repr(result))
 def test_reports_missing_live_requirements_without_reading_values(self):
  result = preflight.report({}, has_cryptography=True, has_psycopg2=True,
                            dependency_available=lambda _module: True)
  self.assertFalse(result['ok'])
  self.assertEqual(result['missing'], ['CORDIA_PG_DSN', 'CORDIA_VAULT_KEY',
                                       'GMAIL_USER/GMAIL_APP_PASSWORD or CORDIA_DEV_2FA=1'])

 def test_marks_live_requirements_ready_when_present(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                             'GMAIL_USER': 'ops@example.com', 'GMAIL_APP_PASSWORD': 'secret'},
                            has_cryptography=True, has_psycopg2=True, database_ready=True,
                            dependency_available=lambda _module: True)
  self.assertTrue(result['ok'])

 def test_reports_missing_encryption_dependency(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key'},
                            has_cryptography=False, database_ready=True,
                            dependency_available=lambda _module: True)
  self.assertFalse(result['ok'])
  self.assertIn('cryptography', result['missing'])

 def test_reports_missing_postgres_driver(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                             'GMAIL_USER': 'ops@example.com', 'GMAIL_APP_PASSWORD': 'secret'},
                            has_cryptography=True, has_psycopg2=False, database_ready=True)
  self.assertFalse(result['ok'])
  self.assertIn('psycopg2', result['missing'])
  self.assertFalse(result['checks']['postgres_connection'])

 def test_reports_optional_embedding_dependencies_without_blocking_readiness(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                             'CORDIA_DEV_2FA': '1'}, has_cryptography=True, has_psycopg2=True,
                            database_ready=True,
                            dependency_available=lambda module: module != 'faiss')
  self.assertTrue(result['ok'])
  self.assertFalse(result['checks']['faiss'])
  self.assertEqual(result['optional_missing'], ['faiss'])

 def test_requires_email_2fa_configuration_unless_explicit_dev_mode(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key'},
                            has_cryptography=True, has_psycopg2=True, database_ready=True,
                            dependency_available=lambda _module: True)
  self.assertFalse(result['ok'])
  self.assertIn('GMAIL_USER/GMAIL_APP_PASSWORD or CORDIA_DEV_2FA=1', result['missing'])

 def test_accepts_explicit_dev_2fa_for_local_startup(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://example', 'CORDIA_VAULT_KEY': 'key',
                             'CORDIA_DEV_2FA': '1'}, has_cryptography=True, has_psycopg2=True,
                            database_ready=True, dependency_available=lambda _module: True)
  self.assertTrue(result['ok'])

 def test_reports_an_unreachable_database_without_disclosing_the_dsn(self):
  result = preflight.report({'CORDIA_PG_DSN': 'postgres://secret-host', 'CORDIA_VAULT_KEY': 'key',
                             'CORDIA_DEV_2FA': '1'}, has_cryptography=True, has_psycopg2=True,
                            database_ready=False, dependency_available=lambda _module: True)
  self.assertFalse(result['ok'])
  self.assertIn('PostgreSQL connection', result['missing'])
  self.assertNotIn('secret-host', str(result))

 def test_health_view_exposes_only_readiness_not_configuration_details(self):
  view = preflight.health_view({'ok': False, 'missing': ['CORDIA_PG_DSN']})
  self.assertEqual(view, {'ok': False})


if __name__ == '__main__': unittest.main()
