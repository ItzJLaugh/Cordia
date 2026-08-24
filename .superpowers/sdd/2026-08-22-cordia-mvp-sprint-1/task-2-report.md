# Sprint 1 Task 2 Report

## RED evidence

The initial `python -m unittest ...` invocation could not run because this
Windows checkout has no `python` command. The validated launcher command was:

```powershell
py -3 -m unittest discover -s tests -p test_model_provider.py -v
py -3 -m unittest discover -s tests -p test_preflight.py -v
```

The first focused RED run produced the expected missing-behavior failures:

- `test_status_reports_only_configured_openai_readiness` and
  `test_status_reports_missing_configuration_without_network_or_secret_echo`
  raised `AttributeError: module 'surveyor.model_provider' has no attribute
  'status'` (2 errors; provider test suite ran 9 tests).
- Preflight lacked `checks['model_provider']`; configured readiness raised
  `KeyError`, while missing provider configuration incorrectly left `ok` true
  (1 error, 1 failure; preflight test suite ran 11 tests).

The bounded-model case was also run RED after its test was added: one 121
character model name returned unbounded (1 failure; 10 provider tests ran).

## Minimal production change

- Added `model_provider.status()`, which uses `configuration()` as its only
  configuration parser. It catches `ModelUnavailable`, returns the exact safe
  unconfigured shape, and bounds the configured model value to 120 characters.
- Preflight calls `model_provider.status()` only; it records that safe object
  under the named `model_provider` check and adds `OpenAI model provider` when
  configuration is unavailable. It never calls `model_provider.call()`.
- Documented the three exact server-side OpenAI variables and the Task 4
  authenticated-observation boundary.

## GREEN evidence

Commands were run from `backend` using `py -3` outside the workspace sandbox,
which is required to execute the installed Python 3.13 runtime:

| Command | Result |
| --- | --- |
| `py -3 -m unittest discover -s tests -p test_model_provider.py -v` | 10 passed |
| `py -3 -m unittest discover -s tests -p test_preflight.py -v` | 11 passed |
| `git diff --check` | passed; no whitespace errors |

## Secret-boundary inspection

- `status()` returns exactly provider, configured, and model; it never returns
  the key or base URL.
- Provider and preflight tests use a sentinel key and assert it is absent from
  public output.
- Preflight tests patch `model_provider.call` to fail if invoked; both
  configured and missing-configuration paths pass without that call.
- No provider, connector, skill, network, credential, or live deployment was
  contacted or claimed.

## Documentation

`backend/SURVEYOR_RUNTIME_SETUP.md` now specifies:

```text
LLM_BASE_URL=https://api.openai.com/v1/chat/completions
LLM_MODEL=<approved OpenAI model identifier>
LLM_KEY=<stored only in /etc/cordia/cordia.env>
```

It also states that ChatGPT subscriptions do not supply the API credential and
that no real-provider claim exists before Sprint 1 Task 4 authenticated
observation.

## Self-review

- No new provider abstraction, gateway, queue, or second state owner.
- The existing `call(...)` interface and five-envelope behavior are untouched.
- The status/preflight projections contain no key or base URL.
- Only Task 2 production files, tests, documentation, and this report are
  included in the commit.

## Commit

`feat: expose safe OpenAI provider readiness`

## Review round 1/5

### RED evidence

The class-wide process-environment patch was removed. The following crossed
configuration tests were added and run with the focused preflight command:

- `test_uses_passed_missing_provider_configuration_over_a_configured_process`
  failed because the old implementation returned configured readiness from the
  global process environment.
- `test_uses_passed_configured_provider_configuration_over_a_missing_process`
  failed because the old implementation returned unavailable readiness from
  the global process environment.

The first run completed 13 tests with 6 failures. The two new failures were
the intended mapping-source mismatch; the remaining four exposed old tests
that had depended on the removed masking patch.

### Minimal correction

`configuration(environment=None)` and `status(environment=None)` retain their
normal zero-argument behavior while accepting the preflight report mapping.
`preflight.report(environment=...)` now calls `status(environment)`. The
configuration parser remains the single parser, and no global environment is
mutated.

### GREEN evidence

| Command | Result |
| --- | --- |
| `py -3 -m unittest discover -s tests -p test_model_provider.py -v` | 10 passed |
| `py -3 -m unittest discover -s tests -p test_preflight.py -v` | 13 passed |
| `git diff --check` | passed; no whitespace errors |

### Review conclusion

Preflight now uses one configuration source for its existing requirements and
provider readiness. The public status shape remains provider, configured, and
model only. No provider, network, credential, connector, skill, or live system
was called.
