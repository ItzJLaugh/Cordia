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
