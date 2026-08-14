import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from surveyor import prompts


class TestRuntimePrompt(unittest.TestCase):
 def test_includes_compiled_mission_and_permissions_without_source_transcript(self):
  system = prompts.runtime_system({'agents': []}, {}, {
      'runtime/fde-tasks.md': '# FDE Mission Brief\nPrepare a report.',
      'runtime/permissions.md': '# Permissions\n## ASK\nPause before sending.',
      'source/operator.md': 'do not include this',
  })
  self.assertIn('Prepare a report.', system)
  self.assertIn('Pause before sending.', system)
  self.assertNotIn('do not include this', system)

 def test_keeps_runtime_context_bounded(self):
  system = prompts.runtime_system({}, {}, {'runtime/fde-tasks.md': 'x' * 12000})
  self.assertLess(len(system), 9000)

 def test_includes_canonical_workspace_context_references(self):
  system = prompts.runtime_system({}, {}, {}, {'context_sources': [
      {'kind': 'github_repository', 'id': 'ItzJLaugh/Cordia', 'label': 'Cordia'}]})
  self.assertIn('ItzJLaugh/Cordia', system)


if __name__ == '__main__': unittest.main()
