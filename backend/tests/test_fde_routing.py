import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import fde_routing


class TestFdeRouting(unittest.TestCase):
 def base_context(self, **overrides):
  context = {
   'mission_tags': ['developer', 'repository'],
   'connector_states': {'github': 'confirmed', 'desktop.local_repository': 'confirmed'},
   'capability_states': {
    'github.read_repositories': 'confirmed',
    'desktop.git.status': 'confirmed', 'desktop.git.wait': 'confirmed',
    'desktop.git.pull': 'confirmed', 'desktop.git.push': 'confirmed',
   },
   'evidence': {'local_repository': ['repo-17']},
   'preference_tags': ['monitoring'],
   'personalization_mode': 'simple',
  }
  context.update(overrides)
  return context

 def by_id(self, result):
  return {item['id']: item for item in result['recommendations']}

 def test_blocks_unconfirmed_connectors_and_missing_local_evidence(self):
  result = fde_routing.recommend(self.base_context(
   connector_states={'github': 'confirmed', 'desktop.local_repository': 'available'},
   evidence={},
  ))
  self.assertEqual([item['id'] for item in result['recommendations']], ['github_repository_review'])
  blocked = {item['id']: item['blocked_prerequisites'] for item in result['blocked']}
  self.assertIn('connector: desktop.local_repository', blocked['local_git_status_wait'])
  self.assertIn('evidence: local_repository', blocked['local_git_status_wait'])

 def test_blocks_capability_dependent_records_without_explicit_capability_state(self):
  context = self.base_context()
  del context['capability_states']
  result = fde_routing.recommend(context)
  self.assertEqual(result['recommendations'], [])
  blocked = {item['id']: item['blocked_prerequisites'] for item in result['blocked']}
  self.assertIn('capability: github.read_repositories', blocked['github_repository_review'])
  self.assertIn('capability: desktop.git.status', blocked['local_git_status_wait'])

 def test_filters_denied_records_without_exposing_them_as_candidates(self):
  original = fde_routing._records
  try:
   fde_routing._records = lambda: [{
    'id': 'denied', 'kind': 'skill', 'summary': 'Denied.', 'tags': ['developer'],
    'required_capabilities': [], 'required_connectors': [], 'required_evidence': [],
    'permission': 'DENY', 'result_fields': [], 'maturity': 'live', 'test_evidence': [],
   }]
   result = fde_routing.recommend(self.base_context())
  finally:
   fde_routing._records = original
  self.assertEqual(result['recommendations'], [])
  self.assertEqual(result['blocked'][0]['id'], 'denied')
  self.assertEqual(result['blocked'][0]['blocked_prerequisites'], ['permission: DENY'])

 def test_applies_candidate_limit_after_ranking(self):
  result = fde_routing.recommend(self.base_context(), limit=1)
  self.assertEqual(len(result['recommendations']), 1)
  self.assertEqual(result['recommendations'][0]['id'], 'local_git_status_wait')

 def test_uses_stable_id_to_break_equal_scores(self):
  original = fde_routing._records
  try:
   fde_routing._records = lambda: [
    {'id': 'zulu', 'kind': 'skill', 'summary': 'Z.', 'tags': ['developer'], 'required_capabilities': [], 'required_connectors': [], 'required_evidence': [], 'permission': 'ALLOW', 'result_fields': [], 'maturity': 'live', 'test_evidence': []},
    {'id': 'alpha', 'kind': 'skill', 'summary': 'A.', 'tags': ['developer'], 'required_capabilities': [], 'required_connectors': [], 'required_evidence': [], 'permission': 'ALLOW', 'result_fields': [], 'maturity': 'live', 'test_evidence': []},
   ]
   result = fde_routing.recommend(self.base_context(preference_tags=[]))
  finally:
   fde_routing._records = original
  self.assertEqual([item['id'] for item in result['recommendations']], ['alpha', 'zulu'])

 def test_applies_visible_risk_and_latency_penalties(self):
  result = self.by_id(fde_routing.recommend(self.base_context()))
  read = result['github_repository_review']['score_breakdown']
  write = result['local_git_pull']['score_breakdown']
  self.assertEqual(read['risk_cost'], 0)
  self.assertEqual(write['risk_cost'], 1)
  self.assertLess(read['latency_cost'], write['latency_cost'])
  self.assertEqual(write['score'], sum(write[key] for key in (
   'mission_relevance', 'evidence_support', 'explicit_preference', 'observed_success',
  )) - write['risk_cost'] - write['latency_cost'])

 def test_off_mode_suppresses_evidence_and_preference_scoring(self):
  simple = self.by_id(fde_routing.recommend(self.base_context()))['local_git_status_wait']
  off = self.by_id(fde_routing.recommend(self.base_context(personalization_mode='off')))['local_git_status_wait']
  self.assertGreater(simple['score_breakdown']['evidence_support'], 0)
  self.assertGreater(simple['score_breakdown']['explicit_preference'], 0)
  self.assertEqual(off['score_breakdown']['evidence_support'], 0)
  self.assertEqual(off['score_breakdown']['explicit_preference'], 0)

 def test_registry_outcomes_do_not_automatically_adjust_routing(self):
  before = fde_routing.recommend(self.base_context())
  after = fde_routing.recommend(self.base_context(outcome_events=[
   {'record_id': 'github_repository_review', 'outcome': 'useful'},
   {'record_id': 'local_git_status_wait', 'outcome': 'not_useful'},
  ]))
  self.assertEqual(after, before)

 def test_returns_bounded_safe_reason_trace(self):
  result = self.by_id(fde_routing.recommend(self.base_context()))['local_git_status_wait']
  self.assertEqual(result['permission'], 'ALLOW')
  self.assertEqual(result['matched_evidence'], {'local_repository': ['repo-17']})
  self.assertEqual(result['why'], [
   'Matched mission tags: developer, repository.',
   'Matched evidence: local_repository.',
   'Matched preference tags: monitoring.',
  ])
  self.assertNotIn('required_capabilities', result)
  self.assertNotIn('required_connectors', result)

 def test_does_not_echo_local_paths_as_evidence_identifiers(self):
  result = self.by_id(fde_routing.recommend(self.base_context(
   evidence={'local_repository': ['C:/users/example/private-repo', 'repo-17']},
  )))['local_git_status_wait']
  self.assertEqual(result['matched_evidence'], {'local_repository': ['repo-17']})


if __name__ == '__main__': unittest.main()
