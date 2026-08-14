"""Canonical, inspectable workspace state shared by people and Cordia agents."""
from __future__ import annotations
from copy import deepcopy
from datetime import datetime, timezone
from .artifacts import connector_catalog

def empty(workspace_id):
 return {'id':workspace_id,'title':'','description':'','surface':{},'workflow':{},'windows':[],'connectors':[],'skills':[],'agents':[],'permissions':{},'context_sources':[],'automations':[],'mutations':[],'provenance':[]}

def from_interface(workspace_id, definition, connector_states=None):
 d=definition or {}; state=empty(workspace_id)
 state['title']=str(d.get('name') or '')
 state['description']=str(d.get('description') or '')
 state['surface']=deepcopy(d.get('surface') or {})
 state['workflow']=deepcopy(d.get('workflow') or {})
 state['agents']=deepcopy(d.get('agents') or [])
 state['skills']=deepcopy(d.get('tools') or [])
 state['connectors']=_connectors(connector_states or {})
 state['windows']=[_agent_window(a, index) for index,a in enumerate(state['agents'])]
 state['windows'].extend(_connector_windows(connector_states or {}))
 state['permissions']={'mode':'compiled','source':'runtime/permissions.md'}
 state['context_sources']=[{'kind':'artifact','ref':'runtime/fde-tasks.md'}]
 state['provenance']=[{'actor':'system','kind':'derived_from_interface','at':_now()}]
 return state

def merge_interface(state, definition):
 """Apply builder-owned fields without replacing live workspace decisions."""
 out=deepcopy(state); d=definition or {}
 out['title']=str(d.get('name') or out.get('title') or '')
 out['description']=str(d.get('description') or out.get('description') or '')
 out['surface']=deepcopy(d.get('surface') or {})
 out['workflow']=deepcopy(d.get('workflow') or {})
 out['agents']=deepcopy(d.get('agents') or [])
 out['skills']=deepcopy(d.get('tools') or [])
 agent_windows=[_agent_window(a, index) for index,a in enumerate(out['agents'])]
 out['windows']=[window for window in out.get('windows', [])
                 if window.get('derived_by')!='interface_builder' and window.get('id')!='cordia-agent']
 out['windows'][0:0]=agent_windows
 out['provenance'].append({'actor':'human','kind':'builder_definition_merged','at':_now()})
 return out

def apply_mutation(state, mutation, actor):
 out=deepcopy(state); m=deepcopy(mutation or {})
 if m.get('kind')=='add_context_source':
  changed=add_context_source(out, m.get('source'))
  if actor!='human':
   changed['provenance'][-1]['actor']=actor
  return changed
 if m.get('kind')=='remove_context_source':
  changed=remove_context_source(out, m.get('source_kind'), m.get('source_id'))
  if actor!='human':
   changed['provenance'][-1]['actor']=actor
  return changed
 if m.get('kind')!='add_window' or not isinstance(m.get('window'),dict): raise ValueError('Unsupported workspace mutation.')
 window=m['window']
 if not window.get('id') or any(x.get('id')==window['id'] for x in out['windows']): raise ValueError('Window id must be new.')
 out['windows'].append(window); event={'actor':actor,'kind':'add_window','at':_now(),'window_id':window['id']}
 out['mutations'].append(event); out['provenance'].append(event)
 return out

def refresh_connectors(state, connector_states):
 """Refresh system-derived connector windows while preserving human/agent edits."""
 out=deepcopy(state)
 observed={connector.get('id'):connector for connector in out.get('connectors',[])}
 out['connectors']=_connectors(connector_states or {})
 for connector in out['connectors']:
  prior=observed.get(connector['id'],{})
  if prior.get('runtime_status') in {'live','needs_attention'}:
   connector['runtime_status']=prior['runtime_status']
   connector['lifecycle']='live' if prior['runtime_status']=='live' else 'failed'
 out['windows']=[window for window in out.get('windows', [])
                 if window.get('derived_by')!='connector_registry']
 out['windows'].extend(_connector_windows(connector_states or {}))
 out['provenance'].append({'actor':'system','kind':'connector_windows_refreshed','at':_now()})
 return out

def record_connector_runtime(state, connector_id, runtime_status):
 """Record observed runtime health without changing explicit connection consent."""
 if runtime_status not in {'live','needs_attention'}: raise ValueError('Unknown connector runtime status.')
 out=deepcopy(state)
 for connector in out.get('connectors',[]):
  if connector.get('id')==connector_id:
   connector['runtime_status']=runtime_status
   connector['lifecycle']='live' if runtime_status=='live' else 'failed'
 out['provenance'].append({'actor':'system','kind':'connector_runtime_observed',
                           'connector_id':connector_id,'status':runtime_status,'at':_now()})
 return out

def add_context_source(state, source):
 """Add an inspectable context reference without adding connector credentials or content."""
 source=deepcopy(source or {})
 if source.get('kind')!='github_repository' or not str(source.get('id') or '').strip():
  raise ValueError('Unsupported context source.')
 source={'kind':'github_repository','id':str(source['id']).strip()[:240],
         'label':str(source.get('label') or source['id']).strip()[:240]}
 out=deepcopy(state)
 if not any(item.get('kind')==source['kind'] and item.get('id')==source['id']
            for item in out.get('context_sources', [])):
  out['context_sources'].append(source)
  out['provenance'].append({'actor':'human','kind':'context_source_added',
                            'source_id':source['id'],'at':_now()})
 return out

def remove_context_source(state, source_kind, source_id):
 """Remove an explicit non-artifact context reference and record the choice."""
 source_kind=str(source_kind or '').strip(); source_id=str(source_id or '').strip()
 if not source_kind or not source_id: raise ValueError('Context source kind and id are required.')
 out=deepcopy(state)
 prior=len(out.get('context_sources', []))
 out['context_sources']=[item for item in out.get('context_sources', [])
                         if not (item.get('kind')==source_kind and item.get('id')==source_id)]
 if len(out['context_sources'])==prior: raise ValueError('Context source was not found.')
 out['provenance'].append({'actor':'human','kind':'context_source_removed',
                           'source_id':source_id,'at':_now()})
 return out

def _connector_windows(connector_states):
 """Windows only appear where Cordia has a native renderer for live data."""
 if connector_states.get('github') != 'confirmed': return []
 return [{'id':'github-repositories','kind':'connector','connector_id':'github',
          'view':'repositories','title':'GitHub repositories',
          'derived_by':'connector_registry'}]

def _agent_window(agent, index):
 """Give each builder agent a stable workspace window identity."""
 agent_id=str(agent.get('id') or 'agent-' + str(index + 1)).strip() or 'agent-' + str(index + 1)
 return {'id':'agent-' + agent_id,'kind':'agent','agent_id':agent_id,
         'title':agent.get('name','Cordia Agent'),'derived_by':'interface_builder'}

def _connectors(connector_states):
 """Project consent and adapter readiness into one reconstructable record."""
 catalog=connector_catalog()
 return [{'id':cid,'status':status,
          'implementation_status':catalog.get(cid,{}).get('implementation_status','planned'),
          'lifecycle':'proposed' if status=='suggested' else 'needs_handoff'}
         for cid,status in sorted(connector_states.items())]

def _now(): return datetime.now(timezone.utc).isoformat()
