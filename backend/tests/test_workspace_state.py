import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from surveyor import workspace_state

class TestWorkspaceState(unittest.TestCase):
 def test_derives_single_canonical_workspace_from_interface(self):
   state=workspace_state.from_interface('w1',{'name':'Research','surface':{'type':'chat'},'agents':[{'id':'a','name':'Researcher'}],'tools':[{'id':'search','name':'Search'}]}, {'github':'confirmed'})
   self.assertEqual(state['id'],'w1'); self.assertEqual(state['title'],'Research'); self.assertEqual(state['surface']['type'],'chat'); self.assertEqual(state['connectors'][0]['id'],'github'); self.assertEqual(state['connectors'][0]['implementation_status'],'live'); self.assertEqual(state['windows'][0]['kind'],'agent'); self.assertIn('permissions',state); self.assertIn('provenance',state)

 def test_adds_a_native_window_for_a_confirmed_connector(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  github_window=[w for w in state['windows'] if w.get('connector_id')=='github'][0]
  self.assertEqual(github_window['kind'],'connector')
  self.assertEqual(github_window['view'],'repositories')

 def test_assigns_a_distinct_window_to_each_builder_agent(self):
  state=workspace_state.from_interface('w1',{'agents':[{'id':'research'},{'id':'writer'}]})
  windows=[window for window in state['windows'] if window['kind']=='agent']
  self.assertEqual([window['id'] for window in windows],['agent-research','agent-writer'])

 def test_refreshes_derived_connector_windows_without_losing_manual_windows(self):
  state=workspace_state.from_interface('w1',{}, {})
  state=workspace_state.apply_mutation(state,{'kind':'add_window','window':{'id':'notes','kind':'connector','connector_id':'notes','title':'Notes'}},'human')
  changed=workspace_state.refresh_connectors(state,{'github':'confirmed'})
  self.assertTrue(any(w.get('connector_id')=='github' for w in changed['windows']))
  self.assertTrue(any(w.get('id')=='notes' for w in changed['windows']))

 def test_refresh_keeps_observed_connector_runtime_health(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  state=workspace_state.record_connector_runtime(state,'github','live')
  changed=workspace_state.refresh_connectors(state,{'github':'confirmed','notion':'suggested'})
  github=[item for item in changed['connectors'] if item['id']=='github'][0]
  self.assertEqual(github['runtime_status'],'live')
  self.assertEqual(github['lifecycle'],'live')

 def test_records_connector_runtime_health_in_canonical_state(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  self.assertEqual(state['connectors'][0]['lifecycle'],'needs_handoff')
  changed=workspace_state.record_connector_runtime(state,'github','live')
  connector=[c for c in changed['connectors'] if c['id']=='github'][0]
  self.assertEqual(connector['runtime_status'],'live')
  self.assertEqual(connector['lifecycle'],'live')

 def test_rejects_unknown_connector_runtime_health(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  with self.assertRaisesRegex(ValueError,'Unknown connector runtime status'):
   workspace_state.record_connector_runtime(state,'github','invented')

 def test_adds_selected_repository_as_context_with_provenance(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  changed=workspace_state.add_context_source(state,{'kind':'github_repository','id':'ItzJLaugh/Cordia','label':'Cordia'})
  self.assertEqual(changed['context_sources'][-1]['id'],'ItzJLaugh/Cordia')
  self.assertEqual(changed['provenance'][-1]['kind'],'context_source_added')

 def test_removes_selected_context_with_provenance(self):
  state=workspace_state.from_interface('w1',{}, {'github':'confirmed'})
  state=workspace_state.add_context_source(state,{'kind':'github_repository','id':'ItzJLaugh/Cordia'})
  changed=workspace_state.remove_context_source(state,'github_repository','ItzJLaugh/Cordia')
  self.assertFalse(any(item.get('id')=='ItzJLaugh/Cordia' for item in changed['context_sources']))
  self.assertEqual(changed['provenance'][-1]['kind'],'context_source_removed')

 def test_carries_workflow_needed_to_reconstruct_runtime(self):
  workflow={'steps':[{'agentId':'a','requiresApproval':True}]}
  state=workspace_state.from_interface('w1',{'workflow':workflow})
  self.assertEqual(state['workflow'],workflow)
 def test_merges_builder_fields_without_losing_runtime_edits(self):
  state=workspace_state.from_interface('w1',{'name':'Before'}, {'github':'confirmed'})
  state=workspace_state.add_context_source(state,{'kind':'github_repository','id':'ItzJLaugh/Cordia'})
  state=workspace_state.apply_mutation(state,{'kind':'add_window','window':{'id':'notes','kind':'derived'}},'human')
  merged=workspace_state.merge_interface(state,{'name':'After','workflow':{'steps':[]},'tools':[{'id':'review'}]})
  self.assertEqual(merged['title'],'After')
  self.assertEqual(merged['workflow'],{'steps':[]})
  self.assertEqual(merged['skills'],[{'id':'review'}])
  self.assertTrue(any(item.get('id')=='ItzJLaugh/Cordia' for item in merged['context_sources']))
  self.assertTrue(any(window.get('id')=='notes' for window in merged['windows']))
 def test_migrates_legacy_builder_agent_windows_on_merge(self):
  state=workspace_state.empty('w1')
  state['windows']=[{'id':'cordia-agent','kind':'agent','agent_id':'old'}]
  merged=workspace_state.merge_interface(state,{'agents':[{'id':'new'}]})
  self.assertEqual([window['id'] for window in merged['windows'] if window['kind']=='agent'],['agent-new'])
 def test_records_agent_mutation_without_changing_unrelated_state(self):
  state=workspace_state.empty('w1'); changed=workspace_state.apply_mutation(state,{'kind':'add_window','window':{'id':'github','kind':'connector','connector_id':'github'}},'agent')
  self.assertEqual(changed['windows'][0]['id'],'github'); self.assertEqual(changed['mutations'][0]['actor'],'agent'); self.assertEqual(changed['provenance'][0]['kind'],'add_window')
if __name__=='__main__': unittest.main()
