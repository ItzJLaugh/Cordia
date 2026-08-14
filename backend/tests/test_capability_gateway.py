import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import capability_gateway


class TestCapabilityGateway(unittest.TestCase):
 def test_exposes_github_read_as_a_typed_capability(self):
  capability = capability_gateway.describe('github.read_repositories')
  self.assertEqual(capability['connector'], 'github')
  self.assertEqual(capability['permission'], 'ALLOW')
  self.assertEqual(capability['transport'], 'direct_api')

 def test_hides_unregistered_capabilities(self):
  self.assertIsNone(capability_gateway.describe('github.arbitrary_request'))

 def test_exposes_only_typed_local_git_capabilities_with_their_permission_posture(self):
  status = capability_gateway.describe('desktop.git.status')
  pull = capability_gateway.describe('desktop.git.pull')
  push = capability_gateway.describe('desktop.git.push')
  self.assertEqual(status['connector'], 'desktop.local_repository')
  self.assertEqual(status['transport'], 'local_bridge')
  self.assertEqual(status['permission'], 'ALLOW')
  self.assertEqual(pull['permission'], 'ASK')
  self.assertEqual(push['permission'], 'ASK')

 def test_executes_only_an_allowed_registered_capability(self):
  result = capability_gateway.execute('github.read_repositories', {'github': 'confirmed'},
                                      lambda: {'repositories': []})
  self.assertTrue(result['ok'])
  self.assertEqual(result['result'], {'repositories': []})

 def test_blocks_an_unconfirmed_connector_before_credential_or_network_work(self):
  credential_or_network_work = []
  result = capability_gateway.execute('github.read_repositories', {},
                                      lambda: credential_or_network_work.append(True))
  self.assertFalse(result['ok'])
  self.assertEqual(credential_or_network_work, [])


if __name__ == '__main__': unittest.main()
