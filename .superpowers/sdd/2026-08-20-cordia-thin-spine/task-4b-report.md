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
