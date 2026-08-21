# Task 4B report: Coordinated-Clause Truth Guard Correction

## Scope and correction

Task 4B corrects the remaining coordinated-subclause truth bypass only. The
Cordia Agent speak validator now splits each punctuation/newline clause at the
standard coordinating delimiters `and`, `but`, `or`, `nor`, `yet`, and `so`
before it classifies a fragment. Agent-completion detection therefore runs on
each coordinated subclause before the catalog/approval backend-status exception
can be considered.

No action, provider, connector, state, endpoint, schema, prompt, or ownership
behavior changed. No provider or connector operation was invoked.

## Independent RED/GREEN

The production validator regression was added first in
`backend/tests/test_cordia_agent.py`.

- RED command: `py -3 -m unittest discover -s tests -p test_cordia_agent.py -v`
- RED result: 14 tests ran, with the new coordinated-subclause test failing for
  the catalog + Assistant-deployed form and both straight/curly `We've`
  approval + completion forms. The newline-delimited forms were already
  protected by the prior punctuation/newline classifier.
- GREEN result: 14/14 passed after the minimal classifier correction.

The regression matrix rejects the required catalog/approval coordinated forms,
straight and curly contractions, and their newline-coordinated equivalents.
The existing safe cases remain covered and passing: catalog availability,
availability after approval, a conditional connection statement, a question,
and `The action plan is connected to your goals.`

## Verification

Focused and Task 4-adjacent backend discovery, all passing:

- Cordia Agent: 14/14.
- Operator profile safety boundary: 13/13.
- Workspace-turn route: 6/6.
- Workspace-turn store comparison/compare-and-save boundary: 5/5.
- Focused/adjacent total: 38/38.

Full dashboard: `node --test --test-reporter=spec` passed 88/88. The Node test
process emitted `WebSocket server error: Port 24678 is already in use`, but the
rendered Assistant test and every dashboard test passed.

Full backend: 236/237 passed. The sole failure remains the pre-existing optional
embedding runtime test, `test_embedding_runtime.TestEmbeddingRuntime.test_declared_runtime_can_import_the_shadow_scorer`, because `sentence_transformers` is not installed (`ModuleNotFoundError`). This task neither changes that runtime nor its dependencies. The run also emitted the pre-existing NumPy reload and unavailable-local-PostgreSQL notices.

`git diff --check` passed after this report and the code/test change.

## Self-review and boundary

- The exception remains exact-tail only and is evaluated per subclause.
- Completion detection is checked before backend-entity/status exceptions for
  every subclause.
- No safe case was removed, and no new agent action or external execution path
  was added.
- Provider evidence remains `Not yet verified`; no provider or connector call
  was made.

## Review-fix round 1 of 5

### Corrections

- Every punctuation/newline fragment now removes a leading coordinating word
  (`and`, `but`, `or`, `nor`, `yet`, or `so`) before agent-completion
  classification. A newline before the coordinator therefore cannot hide a
  later completion claim behind a catalog or approval clause.
- False-speech validation now runs for all five exact Cordia Agent envelopes
  before kind-specific proposal processing. A proposal cannot carry a false
  completion claim into a pending action.
- Added `store.mutate_workspace`, a reusable server-derived mutation primitive.
  It locks the owner workspace, reads the current canonical state, recomputes
  the requested projection from that state, retains pending actions, and
  increments revision once per changed projection. Client-authored
  `save_workspace` expected-revision CAS remains unchanged.
- Interface merges, connector preference/token refreshes, and connector runtime
  projections use the primitive. Their successful routes now stop with a 409
  rather than reporting success when the canonical projection cannot be stored.
  The legacy workspace materialization route returns the stored truth on a
  concurrent save instead of returning its stale candidate.

### Independent RED/GREEN

- Cordia Agent RED: 15 tests ran with seven expected failures: three
  newline-leading coordinator bypasses and four proposal-envelope false-speech
  bypasses. GREEN: 15/15.
- Production-store RED: the new locked mutation regression reached the missing
  `mutate_workspace` API. GREEN: 6/6; it commits an intervening agent proposal,
  then independently proves fresh interface and connector projections retain
  the pending action and increment revision once per projection.
- Route RED: 9 tests ran with three expected failures: stale interface and
  connector projections were silently dropped, and derived conflicts still
  returned 200. GREEN: 9/9.

### Final verification

- Task 4/4B focused and adjacent backend: Cordia Agent 15/15, operator profile
  13/13, workspace-turn route 9/9, and workspace-turn comparison 6/6
  (43/43 total).
- Full dashboard: 88/88 passed.
- Full backend: 241/242 passed. The sole unchanged failure remains
  `test_embedding_runtime.TestEmbeddingRuntime.test_declared_runtime_can_import_the_shadow_scorer` because the optional `sentence_transformers` package is absent.
- No live provider or connector operation was invoked. Provider evidence remains
  `Not yet verified`.

## Review-fix round 2 of 5

### Corrections

- Absent-row `save_workspace` creation now uses `INSERT ... ON CONFLICT DO
  NOTHING RETURNING`. A raced creator can no longer overwrite an existing
  owner’s revision or pending actions; same-owner and cross-owner id collisions
  return a bounded conflict.
- Replaced the generic derived-workspace callback with three bounded store
  transactions: interface plus workspace projection, connector preferences plus
  optional sealed secret plus all workspace projections, and runtime-only
  multi-workspace projection. A write failure raises through the transaction so
  all precursor and prior workspace writes roll back.
- Connector preference merging now occurs under an owner advisory transaction
  lock and reads the current preference row before recomputing every locked
  canonical workspace projection. Interface creation reads the current
  connector preference state inside its own transaction.
- The derived routes now return success only after these transactions commit.
  External GitHub token validation and vault sealing still occur before any
  database mutation; no provider or connector operation was invoked.

### Independent RED/GREEN

- RED production-store test: 4 tests ran; the absent-row race incorrectly
  returned `saved`, and the three required bounded transaction APIs were absent.
  GREEN: 5/5, covering same-owner and cross-owner create races, full rollback
  after the first workspace update, and locked preference merging.
- RED route test: 10 tests ran with the new derived transaction failure route
  returning 200. GREEN: 10/10, with no partial fake-store state and no success
  response after a transaction failure.

### Final verification

- Focused Task 4/4B and adjacent backend: Cordia Agent 15/15, operator profile
  13/13, workspace state 13/13, workspace generation 8/8, transaction store
  5/5, workspace-turn store 5/5, workspace-turn route 10/10, GitHub route 4/4,
  and intent-miss runtime 1/1 (74/74 total).
- Full dashboard: `npm.cmd test` passed 88/88.
- Full backend comparison: 246/247 passed. The sole unchanged failure is
  `test_embedding_runtime.TestEmbeddingRuntime.test_declared_runtime_can_import_the_shadow_scorer` because the optional `sentence_transformers` package is not installed.
- `git diff --check` passed. Provider evidence remains `Not yet verified`; no
  provider or connector call was made.

## Review-fix round 3 of 5

- Added one normalized owner workspace-set advisory lock used before every
  workspace creation/materialization and before bulk connector/runtime row
  discovery. Initial generation and calibration creation now re-read connector
  preferences under that lock rather than trusting the route-time snapshot.
- Assistant retries retain the same idempotency key after ambiguous transport or
  5xx-style failures, clear it after definitive 4xx responses or a material
  edit, and reuse it on retry. A rendered lost-response regression proves one
  proposal/revision refresh with the same key.
- Expanded declarative truth rejection across all five envelopes for connector
  live/enabled/active/ready and agent configured/finished claims, while keeping
  questions and conditional clauses allowed.

### Verification

- Strict RED: 16 Agent tests exposed 21 new status/completion bypasses; the
  shared-lock regression found no workspace-set locks; retry state had no key.
  GREEN: Agent 16/16, transaction store 6/6, generation 8/8, route 10/10,
  GitHub route 4/4, and rendered dashboard retry/controller tests passed.
- Full dashboard: 90/90 passed.
- Full backend comparison: 248/249 passed. The sole unchanged optional failure
  is missing `sentence_transformers` for the embedding runtime import test.
- `git diff --check` passed. No provider or connector execution occurred.
