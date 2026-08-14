import os, sys, unittest
from copy import deepcopy

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import fde_registry


class TestFdeRegistry(unittest.TestCase):
 def test_catalog_returns_a_safe_copy_of_seeded_records(self):
  catalog = fde_registry.catalog()
  catalog['github_repository_review']['summary'] = 'changed outside the registry'
  self.assertEqual(fde_registry.describe('github_repository_review')['summary'],
                   'Review GitHub repositories for delivery context.')

 def test_describe_rejects_unknown_record_ids(self):
  self.assertIsNone(fde_registry.describe('unregistered_record'))

 def test_validate_rejects_duplicate_or_unknown_record_references(self):
  duplicate = {'id': 'github_repository_review', 'kind': 'skill',
               'summary': 'Duplicate.', 'tags': ['developer'],
               'required_capabilities': ['github.read_repositories'],
               'required_connectors': ['github'], 'required_evidence': [],
               'permission': 'ALLOW', 'result_fields': ['repositories'],
               'maturity': 'live', 'test_evidence': ['test_skills'],
               'skill_id': 'github_repository_review'}
  unknown_skill = {**duplicate, 'id': 'ghost_review', 'skill_id': 'ghost_skill'}
  self.assertEqual(fde_registry.validate(duplicate)['error'], 'record ID is already registered')
  self.assertEqual(fde_registry.validate(unknown_skill)['error'], 'skill is not registered')

 def test_validate_rejects_unsafe_record_fields_and_unknown_capabilities(self):
  unsafe = {'id': 'unsafe', 'kind': 'skill', 'summary': 'Unsafe.', 'tags': ['developer'],
            'required_capabilities': ['github.arbitrary_request'], 'required_connectors': ['github'],
            'required_evidence': [], 'permission': 'ALLOW', 'result_fields': ['repositories'],
            'maturity': 'planned', 'test_evidence': ['test'], 'shell': 'git status'}
  result = fde_registry.validate(unsafe)
  self.assertFalse(result['ok'])
  self.assertIn('unsafe field: shell', result['errors'])
  self.assertIn('capability is not registered: github.arbitrary_request', result['errors'])

 def test_validate_rejects_unknown_sensitive_and_cross_kind_fields(self):
  skill = deepcopy(fde_registry.describe('github_repository_review'))
  skill['authorization'] = 'Bearer secret'
  skill['payload'] = {'method': 'delete'}
  skill['skill_ids'] = ['github_repository_review']
  result = fde_registry.validate(skill)
  self.assertFalse(result['ok'])
  self.assertIn('unsafe field: authorization', result['errors'])
  self.assertIn('unsafe field: payload', result['errors'])
  self.assertIn('field is only allowed for playbooks: skill_ids', result['errors'])

 def test_validate_rejects_playbook_with_cross_kind_or_empty_skill_references(self):
  playbook = deepcopy(fde_registry.describe('developer_delivery_loop'))
  playbook['skill_ids'] = []
  playbook['skill_id'] = 'github_repository_review'
  result = fde_registry.validate(playbook)
  self.assertFalse(result['ok'])
  self.assertIn('playbook skill_ids must not be empty', result['errors'])
  self.assertIn('field is only allowed for skills: skill_id', result['errors'])

 def test_validate_rejects_playbook_that_invents_or_omits_skill_prerequisites(self):
  playbook = deepcopy(fde_registry.describe('developer_delivery_loop'))
  playbook['required_capabilities'].remove('desktop.git.push')
  playbook['required_connectors'].append('slack')
  result = fde_registry.validate(playbook)
  self.assertFalse(result['ok'])
  self.assertIn('playbook capabilities must equal referenced skill capabilities', result['errors'])
  self.assertIn('playbook connectors must equal referenced skill connectors', result['errors'])

 def test_validate_rejects_playbook_permission_that_is_less_restrictive_than_a_skill(self):
  playbook = deepcopy(fde_registry.describe('developer_delivery_loop'))
  playbook['permission'] = 'ALLOW'
  result = fde_registry.validate(playbook)
  self.assertFalse(result['ok'])
  self.assertIn('playbook permission is less restrictive than a referenced skill', result['errors'])

 def test_validate_rejects_duplicate_playbook_prerequisites(self):
  playbook = deepcopy(fde_registry.describe('developer_delivery_loop'))
  playbook['required_capabilities'].append('desktop.git.push')
  playbook['required_connectors'].append('github')
  result = fde_registry.validate(playbook)
  self.assertFalse(result['ok'])
  self.assertIn('playbook capabilities must not contain duplicates', result['errors'])
  self.assertIn('playbook connectors must not contain duplicates', result['errors'])

 def test_validate_rejects_duplicate_playbook_skill_ids(self):
  playbook = deepcopy(fde_registry.describe('developer_delivery_loop'))
  playbook['skill_ids'].append('local_git_push')
  playbook['required_capabilities'].remove('desktop.git.push')
  result = fde_registry.validate(playbook)
  self.assertFalse(result['ok'])
  self.assertIn('playbook skill_ids must not contain duplicates', result['errors'])
  self.assertNotIn('playbook capabilities must equal referenced skill capabilities', result['errors'])

 def test_validate_rejects_skill_records_that_drift_from_their_skill_manifest(self):
  record = deepcopy(fde_registry.describe('local_git_status_wait'))
  record['required_capabilities'].reverse()
  record['required_connectors'] = ['github']
  record['permission'] = 'ASK'
  result = fde_registry.validate(record)
  self.assertFalse(result['ok'])
  self.assertIn('skill capabilities must equal its skill manifest', result['errors'])
  self.assertIn('skill connectors must equal its skill manifest', result['errors'])
  self.assertIn('skill permission must equal its skill manifest', result['errors'])

 def test_validate_rejects_result_fields_that_are_not_safe_identifiers(self):
  record = deepcopy(fde_registry.describe('github_repository_review'))
  record['result_fields'] = ['repositories', 'api_token', 'repository_path',
                             'request_payload', 'auth_state', 'agent_prompt', 'not-safe']
  result = fde_registry.validate(record)
  self.assertFalse(result['ok'])
  self.assertIn('result field is not a safe identifier: api_token', result['errors'])
  self.assertIn('result field is not a safe identifier: repository_path', result['errors'])
  self.assertIn('result field is not a safe identifier: request_payload', result['errors'])
  self.assertIn('result field is not a safe identifier: auth_state', result['errors'])
  self.assertIn('result field is not a safe identifier: agent_prompt', result['errors'])
  self.assertIn('result field is not a safe identifier: not-safe', result['errors'])

 def test_validate_rejects_malformed_schema_without_treating_strings_as_capabilities(self):
  malformed = {'id': 'malformed', 'kind': 'skill', 'summary': 'Malformed.', 'tags': 'developer',
               'required_capabilities': None, 'required_connectors': [], 'required_evidence': [],
               'permission': 'ALLOW', 'result_fields': [], 'maturity': 'planned',
               'test_evidence': [], 'skill_id': 'github_repository_review'}
  result = fde_registry.validate(malformed)
  self.assertFalse(result['ok'])
  self.assertIn('tags must be a list of strings', result['errors'])
  self.assertIn('required_capabilities must be a list of strings', result['errors'])

 def test_seeded_skills_and_developer_playbook_reference_registered_contracts(self):
  skill = fde_registry.describe('github_repository_review')
  local_status = fde_registry.describe('local_git_status_wait')
  local_pull = fde_registry.describe('local_git_pull')
  local_push = fde_registry.describe('local_git_push')
  playbook = fde_registry.describe('developer_delivery_loop')
  self.assertEqual(skill['skill_id'], 'github_repository_review')
  self.assertEqual(skill['required_capabilities'], ['github.read_repositories'])
  self.assertEqual(local_status['required_capabilities'], ['desktop.git.status', 'desktop.git.wait'])
  self.assertEqual(local_pull['permission'], 'ASK')
  self.assertEqual(local_push['permission'], 'ASK')
  self.assertEqual(local_pull['result_fields'], ['operation', 'branch', 'completed'])
  self.assertEqual(local_push['result_fields'], ['operation', 'branch', 'completed'])
  self.assertEqual(playbook['kind'], 'playbook')
  self.assertEqual(playbook['skill_ids'], ['github_repository_review', 'local_git_status_wait',
                                            'local_git_pull', 'local_git_push'])
  self.assertTrue(fde_registry.validate(skill)['ok'])
  self.assertTrue(fde_registry.validate(local_status)['ok'])
  self.assertTrue(fde_registry.validate(local_pull)['ok'])
  self.assertTrue(fde_registry.validate(local_push)['ok'])
  self.assertTrue(fde_registry.validate(playbook)['ok'])


if __name__ == '__main__': unittest.main()
