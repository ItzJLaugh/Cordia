import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import preflight


class TestPreflight(unittest.TestCase):
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
