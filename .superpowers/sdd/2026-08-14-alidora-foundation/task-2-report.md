# Task 2 Report: Authenticated Read-only Alidora Map

## Scope

- Added `GET /surveyor/alidora/map?id=<workspace_id>` in `backend/training_backend.py`.
- The handler authenticates through `_surv_guard()`, reads only with
  `surveyor.store.get_workspace(email, workspace_id)`, and returns the safe
  projection from `surveyor.alidora.map_payload(state)`.
- Added endpoint coverage in `backend/tests/test_alidora.py` for missing IDs,
  cross-user isolation, safe output, and no-write/no-execute behavior.

## TDD evidence

### Red

```powershell
& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -p 'test_alidora.py' -v
```

Result before the endpoint implementation: exit code 1; 8 existing mapper
tests passed and 4 new endpoint tests errored with the expected missing
`_surv_alidora_map` handler.

### Green

```powershell
& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -p 'test_alidora.py' -v
```

Result: exit code 0; 12 tests passed.

```powershell
& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -m unittest discover -s backend/tests -p 'test_fde_registry_endpoint.py' -v
```

Result: exit code 0; 3 tests passed.

```powershell
git -C C:\Users\jacks\.codex\.chatgpt-projects\g-p-6a7ba4e731b481919a357f044572274b\Cordia\.worktrees\alidora-foundation diff --check
```

Result: exit code 0; no whitespace errors.

## Commit

`feat: expose authenticated Alidora system map`

## Concerns

The focused tests run with the module's normal soft-unavailable Surveyor startup
message because no PostgreSQL DSN is configured; each endpoint test replaces
the module-level Surveyor dependency with an in-memory, contract-specific
fixture before invoking the handler.
