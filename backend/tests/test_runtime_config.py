import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import runtime_config


class TestRuntimeConfig(unittest.TestCase):
 def test_secure_cookie_is_the_production_default(self):
  self.assertEqual(runtime_config.cookie_secure({}), 'Secure; ')

 def test_localhost_cookie_exception_requires_explicit_opt_in(self):
  self.assertEqual(runtime_config.cookie_secure({'CORDIA_COOKIE_SECURE': '0'}), '')


if __name__ == '__main__': unittest.main()
