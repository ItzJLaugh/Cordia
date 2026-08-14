import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import hitl_policy


class TestHitlPolicy(unittest.TestCase):
 def test_creates_a_pending_checkpoint_for_an_approval_step(self):
  checkpoint = hitl_policy.create_checkpoint(
      'run-1', {'id': 'publish', 'requiresApproval': True}, 'Publish report draft.')
  self.assertEqual(checkpoint['status'], 'pending')
  self.assertEqual(checkpoint['run_id'], 'run-1')
  self.assertEqual(checkpoint['step_id'], 'publish')

 def test_rejects_a_checkpoint_for_non_approval_step(self):
  self.assertIsNone(hitl_policy.create_checkpoint('run-1', {'id': 'read'}, 'Read data.'))

 def test_records_an_approval_decision_without_exposing_the_draft(self):
  decision = hitl_policy.decide({'status': 'pending', 'run_id': 'run-1', 'step_id': 'publish'},
                                'person@example.com', True, 'Looks good.')
  self.assertEqual(decision['status'], 'approved')
  self.assertEqual(decision['approver'], 'person@example.com')
  self.assertNotIn('draft', decision)

 def test_approved_checkpoint_can_create_a_resume_instruction(self):
  checkpoint = {'id': 'approval-1', 'run_id': 'run-1', 'step_id': 'publish', 'status': 'pending'}
  decision = hitl_policy.decide(checkpoint, 'person@example.com', True)
  resume = hitl_policy.resume_instruction(checkpoint, decision)
  self.assertEqual(resume, {'approval_id': 'approval-1', 'run_id': 'run-1', 'step_id': 'publish'})

 def test_declined_checkpoint_cannot_resume(self):
  checkpoint = {'id': 'approval-1', 'run_id': 'run-1', 'step_id': 'publish', 'status': 'pending'}
  decision = hitl_policy.decide(checkpoint, 'person@example.com', False)
  self.assertIsNone(hitl_policy.resume_instruction(checkpoint, decision))

 def test_resume_instruction_never_accepts_a_checkpoint_without_run_or_step(self):
  checkpoint = {'id': 'approval-1', 'run_id': '', 'step_id': '', 'status': 'pending'}
  decision = hitl_policy.decide(checkpoint, 'person@example.com', True)
  self.assertIsNone(hitl_policy.resume_instruction(checkpoint, decision))


if __name__ == '__main__': unittest.main()
