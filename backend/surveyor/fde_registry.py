"""Static, safe FDE records that advise routing without changing execution."""
from __future__ import annotations

from copy import deepcopy
import re

from . import capability_gateway, skills


_REQUIRED_FIELDS = {
    'id', 'kind', 'summary', 'tags', 'required_capabilities',
    'required_connectors', 'required_evidence', 'permission',
    'result_fields', 'maturity', 'test_evidence',
}
_SAFE_KINDS = {'skill', 'playbook'}
_SAFE_PERMISSIONS = {'ALLOW', 'ASK', 'DENY'}
_SAFE_MATURITY = {'live', 'planned'}
_UNSAFE_FIELDS = {'command', 'path', 'paths', 'prompt', 'request', 'requests',
                  'secret', 'secrets', 'shell', 'url', 'authorization',
                  'authorizations', 'payload', 'payloads'}
_SKILL_FIELDS = _REQUIRED_FIELDS | {'skill_id'}
_PLAYBOOK_FIELDS = _REQUIRED_FIELDS | {'skill_ids'}
_PERMISSION_RANK = {'ALLOW': 0, 'ASK': 1, 'DENY': 2}
_SAFE_IDENTIFIER = re.compile(r'^[a-z][a-z0-9_]*$')
_UNSAFE_RESULT_TOKENS = ('auth', 'command', 'credential', 'file', 'path',
                         'payload', 'prompt', 'request', 'secret', 'shell',
                         'token', 'url')


_RECORDS = {
    'local_git_status_wait': {
        'id': 'local_git_status_wait',
        'kind': 'skill',
        'skill_id': 'local_git_status_wait',
        'summary': 'Monitor the status of a selected local Git repository.',
        'tags': ['developer', 'repository', 'monitoring'],
        'required_capabilities': ['desktop.git.status', 'desktop.git.wait'],
        'required_connectors': ['desktop.local_repository'],
        'required_evidence': ['local_repository'],
        'permission': 'ALLOW',
        'result_fields': ['branch', 'clean', 'ahead', 'behind'],
        'maturity': 'live',
        'test_evidence': ['backend/tests/test_skills.py'],
    },
    'local_git_pull': {
        'id': 'local_git_pull',
        'kind': 'skill',
        'skill_id': 'local_git_pull',
        'summary': 'Pull a selected local Git repository after approval.',
        'tags': ['developer', 'repository', 'delivery'],
        'required_capabilities': ['desktop.git.pull'],
        'required_connectors': ['desktop.local_repository'],
        'required_evidence': ['local_repository'],
        'permission': 'ASK',
        'result_fields': ['operation', 'branch', 'completed'],
        'maturity': 'live',
        'test_evidence': ['backend/tests/test_skills.py'],
    },
    'local_git_push': {
        'id': 'local_git_push',
        'kind': 'skill',
        'skill_id': 'local_git_push',
        'summary': 'Push a selected local Git repository after approval.',
        'tags': ['developer', 'repository', 'delivery'],
        'required_capabilities': ['desktop.git.push'],
        'required_connectors': ['desktop.local_repository'],
        'required_evidence': ['local_repository'],
        'permission': 'ASK',
        'result_fields': ['operation', 'branch', 'completed'],
        'maturity': 'live',
        'test_evidence': ['backend/tests/test_skills.py'],
    },
    'github_repository_review': {
        'id': 'github_repository_review',
        'kind': 'skill',
        'skill_id': 'github_repository_review',
        'summary': 'Review GitHub repositories for delivery context.',
        'tags': ['developer', 'repository', 'review'],
        'required_capabilities': ['github.read_repositories'],
        'required_connectors': ['github'],
        'required_evidence': [],
        'permission': 'ALLOW',
        'result_fields': ['repositories'],
        'maturity': 'live',
        'test_evidence': ['backend/tests/test_skills.py'],
    },
    'developer_delivery_loop': {
        'id': 'developer_delivery_loop',
        'kind': 'playbook',
        'skill_ids': ['github_repository_review', 'local_git_status_wait',
                      'local_git_pull', 'local_git_push'],
        'summary': 'Run a developer delivery loop with connected repository context.',
        'tags': ['developer', 'delivery'],
        'required_capabilities': ['github.read_repositories', 'desktop.git.status',
                                  'desktop.git.wait', 'desktop.git.pull', 'desktop.git.push'],
        'required_connectors': ['github', 'desktop.local_repository'],
        'required_evidence': ['local_repository'],
        'permission': 'ASK',
        'result_fields': ['repositories', 'operation', 'branch', 'clean', 'ahead', 'behind', 'completed'],
        'maturity': 'live',
        'test_evidence': ['backend/tests/test_skills.py'],
    },
}


def catalog():
    """Return a copy so callers cannot mutate static registry data."""
    return deepcopy(_RECORDS)


def describe(record_id):
    record = _RECORDS.get(str(record_id or ''))
    return deepcopy(record) if record else None


def validate(record):
    """Validate an untrusted declarative record against live allow-lists."""
    if not isinstance(record, dict):
        return _invalid('record must be an object')

    errors = []
    kind = record.get('kind')
    allowed_fields = _SKILL_FIELDS if kind == 'skill' else _PLAYBOOK_FIELDS if kind == 'playbook' else _REQUIRED_FIELDS
    missing = sorted(allowed_fields - set(record))
    errors.extend('missing required field: ' + field for field in missing)
    for field in sorted(set(record) - allowed_fields):
        if kind == 'skill' and field == 'skill_ids':
            errors.append('field is only allowed for playbooks: skill_ids')
        elif kind == 'playbook' and field == 'skill_id':
            errors.append('field is only allowed for skills: skill_id')
        elif _is_unsafe_field(field):
            errors.append('unsafe field: ' + field)
        else:
            errors.append('unknown field: ' + field)
    if kind not in _SAFE_KINDS:
        errors.append('kind must be skill or playbook')
    if record.get('permission') not in _SAFE_PERMISSIONS:
        errors.append('permission must be ALLOW, ASK, or DENY')
    if record.get('maturity') not in _SAFE_MATURITY:
        errors.append('maturity must be live or planned')

    for field in ('tags', 'required_capabilities', 'required_connectors',
                  'required_evidence', 'result_fields', 'test_evidence'):
        if field in record and not _is_string_list(record[field]):
            errors.append(field + ' must be a list of strings')
    for result_field in record.get('result_fields', []) if _is_string_list(record.get('result_fields')) else []:
        if not _is_safe_result_field(result_field):
            errors.append('result field is not a safe identifier: ' + result_field)

    record_id = record.get('id')
    if not isinstance(record_id, str) or not record_id:
        errors.append('id must be a non-empty string')
    elif record_id in _RECORDS and _RECORDS[record_id] != record:
        errors.append('record ID is already registered')

    capabilities = record.get('required_capabilities', [])
    for capability in capabilities if _is_string_list(capabilities) else []:
        if not capability_gateway.describe(capability):
            errors.append('capability is not registered: ' + str(capability))

    skill_ids = record.get('skill_ids', [])
    if kind == 'playbook' and not _is_string_list(skill_ids):
        errors.append('skill_ids must be a list of strings')
    elif kind == 'playbook' and not skill_ids:
        errors.append('playbook skill_ids must not be empty')
    elif kind == 'playbook' and len(skill_ids) != len(set(skill_ids)):
        errors.append('playbook skill_ids must not contain duplicates')
    referenced_skills = []
    for skill_id in skill_ids if _is_string_list(skill_ids) else []:
        skill = skills.describe(skill_id)
        if not skill:
            errors.append('skill is not registered: ' + str(skill_id))
        else:
            referenced_skills.append(skill)
    if kind == 'skill':
        skill_id = record.get('skill_id')
        skill = skills.describe(skill_id) if isinstance(skill_id, str) else None
        if not skill:
            errors.append('skill is not registered')
        else:
            _validate_skill_derivation(record, skill, errors)
    if (kind == 'playbook' and referenced_skills and len(referenced_skills) == len(skill_ids)
            and len(skill_ids) == len(set(skill_ids))
            and _is_string_list(capabilities)
            and _is_string_list(record.get('required_connectors'))
            and record.get('permission') in _PERMISSION_RANK):
        _validate_playbook_derivation(record, referenced_skills, errors)

    return {'ok': not errors, 'errors': errors, **({'error': errors[0]} if errors else {})}


def _invalid(error):
    return {'ok': False, 'errors': [error], 'error': error}


def _is_string_list(value):
    return isinstance(value, list) and all(isinstance(item, str) and item for item in value)


def _is_unsafe_field(field):
    lowered = field.lower()
    return lowered in _UNSAFE_FIELDS or any(token in lowered for token in
                                             ('path', 'prompt', 'authorization', 'payload'))


def _validate_playbook_derivation(record, referenced_skills, errors):
    expected_capabilities = {capability for skill in referenced_skills
                             for capability in skill['required_capabilities']}
    expected_connectors = {connector for skill in referenced_skills
                           for connector in skill['required_connectors']}
    if len(record['required_capabilities']) != len(set(record['required_capabilities'])):
        errors.append('playbook capabilities must not contain duplicates')
    if len(record['required_connectors']) != len(set(record['required_connectors'])):
        errors.append('playbook connectors must not contain duplicates')
    if set(record['required_capabilities']) != expected_capabilities:
        errors.append('playbook capabilities must equal referenced skill capabilities')
    if set(record['required_connectors']) != expected_connectors:
        errors.append('playbook connectors must equal referenced skill connectors')
    required_rank = max(_PERMISSION_RANK[skill['permission']] for skill in referenced_skills)
    if _PERMISSION_RANK.get(record['permission'], -1) < required_rank:
        errors.append('playbook permission is less restrictive than a referenced skill')


def _validate_skill_derivation(record, skill, errors):
    if (_is_string_list(record.get('required_capabilities'))
            and record['required_capabilities'] != skill['required_capabilities']):
        errors.append('skill capabilities must equal its skill manifest')
    if (_is_string_list(record.get('required_connectors'))
            and record['required_connectors'] != skill['required_connectors']):
        errors.append('skill connectors must equal its skill manifest')
    if record.get('permission') in _PERMISSION_RANK and record['permission'] != skill['permission']:
        errors.append('skill permission must equal its skill manifest')


def _is_safe_result_field(value):
    return bool(_SAFE_IDENTIFIER.fullmatch(value)) and not any(token in value for token in _UNSAFE_RESULT_TOKENS)
