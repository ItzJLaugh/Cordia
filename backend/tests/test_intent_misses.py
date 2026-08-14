import os, sys, unittest
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import intent_misses, pipeline, store


class TestIntentMisses(unittest.TestCase):
 def test_records_a_bounded_structured_correction(self):
  miss = intent_misses.build('needs_evidence', 'Cite the inspection photos.',
                             'Include source links in report drafts.')
  self.assertEqual(miss['category'], 'needs_evidence')
  self.assertEqual(miss['correction'], 'Cite the inspection photos.')
  self.assertEqual(miss['effect'], 'Include source links in report drafts.')

 def test_rejects_unknown_or_empty_corrections(self):
  self.assertIsNone(intent_misses.build('invented', 'Use diagrams.', 'Add diagrams.'))
  self.assertIsNone(intent_misses.build('wrong_format', '', 'Use a table.'))

 def test_builds_a_bounded_registry_outcome_for_a_known_record(self):
  outcome = intent_misses.build_outcome('local_git_status_wait', 'useful')
  self.assertEqual(outcome['record_id'], 'local_git_status_wait')
  self.assertEqual(outcome['outcome'], 'useful')
  self.assertIn('date', outcome)

 def test_rejects_unknown_records_and_unbounded_outcomes(self):
  self.assertIsNone(intent_misses.build_outcome('not-a-registry-record', 'useful'))
  self.assertIsNone(intent_misses.build_outcome('local_git_status_wait', 'excellent'))

 def test_pipeline_records_an_inspectable_registry_outcome_with_its_record_id(self):
  with patch.object(pipeline.store, 'record_registry_outcome', return_value=True) as record:
   result = pipeline.record_fde_outcome('me@example.com', 'local_git_status_wait', 'not_useful')
  self.assertTrue(result['ok'])
  self.assertEqual(result['outcome']['record_id'], 'local_git_status_wait')
  self.assertEqual(result['outcome']['outcome'], 'not_useful')
  record.assert_called_once_with('me@example.com', result['outcome'])

 def test_store_persists_only_the_bounded_registry_outcome_payload(self):
  outcome = {'date': '2026-08-13', 'record_id': 'local_git_status_wait', 'outcome': 'useful'}
  with patch.object(store, 'log_event') as event:
   self.assertTrue(store.record_registry_outcome('me@example.com', outcome))
  event.assert_called_once_with('me@example.com', 'fde_registry_outcome_recorded', {
   'record_id': 'local_git_status_wait', 'outcome': 'useful',
  })

 def test_pipeline_appends_a_correction_and_recompiles_artifacts(self):
  profile = {'intent_misses': []}
  with patch.object(pipeline, 'load_profile', return_value=profile), \
       patch.object(pipeline.store, 'save_profile') as save, \
       patch.object(pipeline.store, 'log_event') as event, \
       patch.object(pipeline, 'artifact_bundle', return_value={'runtime/fde-tasks.md': 'updated'}) as compile:
   result = pipeline.record_intent_miss('me@example.com', 'needs_evidence',
                                        'Cite photos.', 'Include source links.')
  self.assertTrue(result['ok'])
  self.assertEqual(profile['intent_misses'][0]['correction'], 'Cite photos.')
  save.assert_called_once_with('me@example.com', profile)
  event.assert_called_once()
  compile.assert_called_once_with('me@example.com')


if __name__ == '__main__': unittest.main()
