import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import skills, capability_gateway


class TestSkills(unittest.TestCase):
 def test_github_review_skill_declares_its_capability_boundary(self):
  skill = skills.describe('github_repository_review')
  self.assertEqual(skill['required_capabilities'], ['github.read_repositories'])
  self.assertEqual(skill['required_connectors'], ['github'])

 def test_unregistered_skill_is_not_available(self):
  self.assertIsNone(skills.describe('click_random_button'))

 def test_local_git_skills_declare_only_registered_desktop_capabilities(self):
  status = skills.describe('local_git_status_wait')
  pull = skills.describe('local_git_pull')
  push = skills.describe('local_git_push')
  self.assertEqual(status['required_capabilities'], ['desktop.git.status', 'desktop.git.wait'])
  self.assertEqual(status['permission'], 'ALLOW')
  self.assertEqual(pull['required_capabilities'], ['desktop.git.pull'])
  self.assertEqual(pull['permission'], 'ASK')
  self.assertEqual(push['required_capabilities'], ['desktop.git.push'])
  self.assertEqual(push['permission'], 'ASK')

 def test_executes_the_declared_capability_and_rejects_unknown_skills(self):
  result = skills.execute('github_repository_review', {'github': 'confirmed'},
                          lambda name: capability_gateway.execute(name, {'github': 'confirmed'},
                                                                  lambda: {'repositories': []}))
  self.assertTrue(result['ok'])
  self.assertEqual(result['result'], {'repositories': []})
  self.assertEqual(skills.execute('click_random_button', {}, lambda _name: None)['error'],
                   'skill is not registered')

 def test_unconfirmed_connector_blocks_skill_before_its_executor_runs(self):
  calls = []
  result = skills.execute(
   'github_repository_review', {'github': 'suggested'},
   lambda name: calls.append(name) or {'ok': True, 'result': {'repositories': []}},
  )
  self.assertFalse(result['ok'])
  self.assertEqual(calls, [])
  self.assertIn('Confirm GitHub', result['error'])

 def test_ask_capability_blocks_skill_before_its_executor_runs(self):
  calls = []
  result = skills.execute(
   'local_git_pull', {'desktop.local_repository': 'confirmed'},
   lambda name: calls.append(name) or {'ok': True, 'result': {'completed': True}},
  )
  self.assertFalse(result['ok'])
  self.assertEqual(calls, [])
  self.assertIn('explicit approval', result['error'])


if __name__ == '__main__': unittest.main()
