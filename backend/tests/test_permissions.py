import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import permissions


class TestPermissions(unittest.TestCase):
 def test_local_git_status_and_wait_require_a_confirmed_local_repository(self):
  states = {'desktop.local_repository': 'confirmed'}
  self.assertEqual(permissions.decide('desktop.git.status', states)['decision'], 'ALLOW')
  self.assertEqual(permissions.decide('desktop.git.wait', states)['decision'], 'ALLOW')
  self.assertEqual(permissions.decide('desktop.git.status', {})['decision'], 'ASK')

 def test_local_git_pull_and_push_always_require_approval(self):
  states = {'desktop.local_repository': 'confirmed'}
  self.assertEqual(permissions.decide('desktop.git.pull', states)['decision'], 'ASK')
  self.assertEqual(permissions.decide('desktop.git.push', states)['decision'], 'ASK')


if __name__ == '__main__': unittest.main()
