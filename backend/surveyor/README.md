# Cordia Surveyor — Agentic Interface Builder (MVP)

A conversational intake agent that turns a chat into an inspectable profile, and
uses that profile to shape an agentic workspace the user builds and runs.

The premise: **intent cannot be measured, but it can be surveyed.**

---

## What this is

A working vertical slice:

1. **Surveyor** — a chat agent that asks adaptively about how you work.
2. **Profile** — what it learns, stored and inspectable.
3. **Cordia profile** — three positive identifiers telling you how to use AI.
4. **Builder** — create/edit agents, tools and workflow steps, pre-shaped by the profile.
5. **Runtime** — run an interface and see output.
6. **Kill switch** — turn personalization off globally or per user.

## What this is **not**

- Not a form. Profiling happens only through conversation.
- Not multi-agent orchestration. A run is one prompted call built from the definition.
- Not machine learning. See "No ML" below — this is deliberate and load-bearing.
- Not enterprise billing or a general-purpose multi-agent orchestrator.
- Not a grading system. Surveyor scores never touch the certification result.

---

## Running it

It is already running. This is not a separate app — it lives inside the existing
Cordia backend and docroot.

```
backend/surveyor/          the module
backend/training_backend.py  routes (/surveyor/*), imported softly
web/surveyor.html …        pages
```

Restart after a backend change:

```bash
systemctl restart cordia-backend.service     # optional embedding shadow runtime loads softly
```

Schema is created at startup by `store.init_schema()`. Safe to run repeatedly.

### Environment variables

| Variable | Purpose | Default |
|---|---|---|
| `CORDIA_PG_DSN` | Reachable Postgres, shared with accounts | required |
| `CORDIA_VAULT_KEY` | Fernet key for encrypted connector secrets | required |
| `GMAIL_USER` / `GMAIL_APP_PASSWORD` | Production email-2FA SMTP credentials | required in production |
| `CORDIA_DEV_2FA` | Explicit development-only replacement for SMTP 2FA | unset |
| `PERSONALIZATION_MODE` | `off` / `simple` / `adaptive` | `simple` |
| `CORDIA_ADMINS` | comma-separated emails allowed to see `/admin.html` | empty |
| `SURVEYOR_LLM` | set to `mock` to force deterministic responses | unset |

There is no `OPENAI_API_KEY`. Cordia already had a provider wrapper (`call_llm`
in `training_backend.py`), and Surveyor uses it through `llm.caller()` rather
than introducing a second one.

---

## Personalization Kill Switch

**PERSONALIZATION_MODE=off**
- disables adaptation
- all users get generic defaults

**PERSONALIZATION_MODE=simple**
- default MVP mode
- uses explicit profile fields and simple heuristics

**PERSONALIZATION_MODE=adaptive**
- reserved for future use
- must fallback to simple mode

Resolution order, re-checked on every call (`adaptation.effective_mode`):

1. `PERSONALIZATION_MODE=off` → profile ignored entirely
2. `profile.simple_mode_forced` → simple mode for that user
3. `simple` → explicit fields + rules
4. `adaptive` → calls simple and returns

The env var is read at call time, not captured at import, so changing it takes a
restart rather than a redeploy. The **per-user flag needs no restart** — it is a
column, and the builder's *Turn personalization off* button writes it live.

Verified: with `off`, a rich profile and an empty profile produce byte-identical
builder defaults. With `adaptive`, output is identical to `simple`.

---

## Surveyor

A chat agent, not a questionnaire. It asks one question at a time, adapts to what
it already knows, and stops when it has enough.

Pipeline, one turn (`pipeline.turn`):

```
store user message
  → extract observations   (LLM → strict JSON → allow-list validation)
  → merge into profile
  → rescore hidden criteria (rules)
  → rebuild identifiers     (top three, positive only)
  → choose next question    (rules)
  → store reply
```

**Extraction is allowed to fail.** Malformed JSON, truncation, prose, an invented
signal name — all return an empty observation with a reason. The previous profile
is kept, `profile_extraction_failed` is logged, and the next question is asked.
A person mid-conversation never loses what they already said because a model
returned bad JSON. This is covered by tests driving four malformed shapes.

**Shallow keyword matching is not the scoring path.** `"charts" → graphPreference
high` is explicitly out. Scoring reads validated signals plus how much evidence
backs each. This matters because this codebase already shipped a keyword
substring scorer once, and it scored a real user 0/3 for quoting the question
back at it.

---

## Profile data

Two halves, deliberately separated.

### Internal — `signals`, `scores`, `evidence`

Ten hidden criteria scored 0..1, each with evidence and confidence:
`intent_clarity, gap_detection, constraint_setting, risk_boundary_awareness,
delegation_readiness, visual_systems_thinking, verification_instinct,
domain_specificity, workflow_decomposition, human_checkpoint_judgment`.

Admin-only. Data for the next scoring layer. **Never a grade, never shown as a
result, never part of certification.**

Unobserved criteria are *absent*, not zero. "Not asked yet" and "asked and low"
are different facts, and conflating them would let a criterion nobody probed look
like a measured weakness.

### User-facing — `identifiers`

Exactly three, always positive, each with a concrete recommendation:

```json
{ "name": "Visual systems thinker",
  "meaning": "You reason about work as a map of connected parts.",
  "use_ai_this_way": "Ask the agent for a diagram of its plan before it writes prose." }
```

**Nothing negative is ever surfaced.** No bottom-ranked list, no "weak"
dimension, no gaps section. This is not politeness — the older profile compiler
in this repo assigns strong/weak by *rank*, so a learner scoring 95 on everything
is still told they are weak at two things. Taking only the top three and never
naming a bottom makes that failure structurally impossible.

Enforced by `types.assert_positive()`, which matches whole words (a substring
check flags "workflow" for containing "low"). Verified against 5000 randomised
profiles including deliberately low-scoring ones: **0 violations**.

Below a confidence floor an identifier is *withheld* and the UI asks the person
to keep talking. A withheld identifier is honest; an invented one is not.

---

## No ML

None is implemented, and none should be added.

- Question choice is a priority list.
- Extraction is one LLM call validated against allow-lists.
- Scoring is a lookup table.

If any of this starts to need a model to work, **delete the feature rather than
growing one**. Bookkeeping done by a model is bookkeeping you cannot debug at 2am.

---

## Model availability

The hosted model is **currently unreachable in production**, for two independent
reasons, both pre-existing and both outside this code:

1. `nous_key()` reads `/root/.hermes/auth.json`, mode 600 owned by `root`, while
   the service runs as `User=cordia`. The service cannot read it.
2. The endpoint returns HTTP 403 (Cloudflare 1010) even with a valid key.

So everything runs through `mock.py`, a deterministic stand-in. It announces
itself: the chat header shows "Limited mode", and the profile and runtime pages
carry a notice. The runtime returns a labelled placeholder rather than passing
fake output off as a result.

`mock.py` *is* keyword matching. That is acceptable there and only there, because
it is a declared placeholder. When the model comes back, `llm.real_available()`
starts returning true and nothing else changes.

---

## Cordia workspace vertical slice

Surveyor now compiles its evidence into inspectable source artifacts
(`operator.md`, `connectors.md`, and `intent-misses.md`) and concise runtime
artifacts (`fde-tasks.md`, `permissions.md`, and `workspace-plan.md`). The
workspace persists one canonical state shared by the human and Cordia.

The first durable connector capability is intentionally narrow:

- `github.read_repositories` reads at most 30 recently updated repository
  metadata records after the user stores a GitHub token in the encrypted vault.
- It runs only through the typed capability gateway after the shared permission
  check allows it; raw credentials never enter prompts or normal UI responses.
- The authenticated setup-to-skill route is regression-tested with a sentinel:
  setup persists only an opaque reference and ciphertext, execution resolves the
  token only inside the allowed capability closure, and the usage audit retains
  only the bounded connector, reference, and capability identifiers.
- GitHub writes remain approval-required and are not implemented. Other common
  services are listed as planned connector manifests, not live adapters.
- The workspace renders canonical connector lifecycle (`proposed`, `needs
  handoff`, `live`, or `failed`) beside adapter availability, so confirmation
  never masquerades as a successful connection.

See `../SURVEYOR_RUNTIME_SETUP.md` for required deployment configuration and
the live verification sequence.

### FDE registry feedback

Human feedback can record a known FDE registry record as `useful` or
`not_useful`. These inspectable events retain the registry record ID, but do
not automatically change routing weights or permission decisions. Any future
adjustment requires a reviewed, attributable policy.

## Extension points

Stubs only — each raises `NotImplementedError` and says so.

| File | For |
|---|---|
| `langgraph_adapter.py` | interface definition → LangGraph graph |
| `hitl_policy.py` | durable human-in-the-loop approval checkpoints |
| `cordia_compiler_adapter.py` | legacy Cordia language/compiler integration |
| `coding_model_provider.py` | custom hosted coding model |

The definition is already graph-shaped on purpose: agents are nodes, ordered
steps are edges, `requiresApproval` is an interrupt point.

**`coding_model_provider.py` records two measured constraints** worth reading
before planning that work: this host is 2 cores / ~7 GB RAM / no GPU, so a 27B
model cannot be served here at any quantization and must be hosted; and a
safety-ablated model is a poor fit behind a product whose premise is teaching
people to operate AI with guardrails and human checkpoints.

---

## Endpoints

All require a Bearer token (`auth.whoami`); all return 401 without one and 503 if
the module failed to import.

| Method | Path |
|---|---|
| GET | `/surveyor/profile` |
| GET | `/surveyor/conversation` |
| GET | `/surveyor/interfaces` |
| GET | `/surveyor/admin` (restricted to `CORDIA_ADMINS`) |
| POST | `/surveyor/message` |
| POST | `/surveyor/interface` |
| POST | `/surveyor/archive` |
| POST | `/surveyor/run` |
| POST | `/surveyor/personalization` |

Apache proxies `/surveyor/` to `127.0.0.1:9995` — see
`sites-available/000-default-le-ssl.conf`.

## Tables

`surveyor_conversations, surveyor_messages, surveyor_profiles,
surveyor_interfaces, surveyor_runs, surveyor_events`

Keyed by `email` to match `accounts.email`, so a profile sits beside the account,
the entitlement and the exam score rather than in a second database.

Creating an interface also writes into the pre-existing **`outcomes`** table
(`recommendation_given`), which had never held a row. `outcome_worked` stays NULL
until someone reports whether the workspace actually helped — that is the
measurement loop this is for. It only attaches for users with an exam submission,
because that table's foreign key requires one.

## Known limitations

- Approval steps create a durable pending approval record and can be
  approved or declined in the workspace. Runtime resume/external execution is
  intentionally not implemented yet, so an approval record cannot trigger a
  connector write by itself.
- GitHub repository metadata is the sole live, read-only connector capability.
  All other connector manifests and write capabilities remain planned.
- A run is one call, not an orchestrated graph.
- The model is offline; see above.
- `adaptive` mode is a passthrough to `simple`.
