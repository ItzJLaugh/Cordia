# Cordia — state of the system

**As of 2026-08-04.** Written to be handed to an agent with no prior context.
Everything below was verified against the running system, not recalled. Where
something is unproven it says so — treat those lines as the most important ones.

---

## The thesis

**Intent cannot be measured, but it can be surveyed.**

AI adoption fails on what people *ask for*, not on model capability. Cordia's
bet is that the differentiator is the operator: how a given person already
thinks, and whether their setup matches that. So the product asks people how
they work, and returns a setup recommendation built around the answer.

Corollary that governs the whole codebase: **the same content must serve a
nurse, an electrician and a controller.** Anything domain-specific is a course,
not a measurement.

---

## What is actually live

**Surveyor** — the current product and the only thing worth sending traffic to.
A three-stage conversational survey behind a modal, reachable from any page.

| Stage | Content | Capture |
|---|---|---|
| 1. Preferences | 13 scripted questions, stops at 9 signals | Tappable chips + free text |
| 2. Scenarios | 4 situations with a real trade-off | Chips only, no right answers |
| 3. Open text | 3 questions about the work itself | Free text, stored verbatim |

Output is a **Cordia profile**: exactly three positive identifiers (from a
catalogue of 10), each with a one-line "use AI this way", plus a setup
recommendation — where to work, which roles to set up, where to keep a human
checkpoint, what to automate first.

Two structural rules, both enforced in code:

- **Never negative.** Only the top three identifiers are ever shown; there is no
  bottom half to be wrong about. `types.assert_positive()` regex-checks every
  user-facing payload against a banned-word list. Verified 0 violations across
  thousands of randomised profiles. This is ship-blocking, not cosmetic.
- **The scenario wins.** Where a stage-2 choice contradicts a stage-1 statement,
  the revealed choice drives the recommendation (`adaptation._level`, single
  enforcement point). The disagreement itself is surfaced as the one output that
  can tell someone something they did not say — stated as fact, interpretation
  explicitly hedged.

**Certification (CordiaAIE-1)** — a 12-item free-text exam, $79, live and
sellable. Scored by `cordaie_scoring.py`.

**Exit survey** — six questions, taken *after* the exam and enforced as such
(`/train/survey` returns 409 `exam_required` otherwise). Three of its answers
are scored alongside the 6S matrix by `sixs/selfreport.py` — intent clarity,
interpretation alignment, and calibration — giving the assessment nine measures
rather than six. The other three (effort source, role, free text) are carried as
context and deliberately not scored: neither answer to "what vs how" is better,
so scoring it would invent a direction the question does not have.

**Who decides the agentic setup.** The survey decides *behaviour* — how much rope
each agent gets and where a human looks — read from the Surveyor profile with
stage-2 scenario choices layered over stated answers. The exam decides *reach* —
tier ceiling, hop budget, and whether a dimension has enough measurement to leave
shadow. Before 2026-08-07 `agent_manifest` derived oversight from the bottom two
6S dimensions **by rank**, so a learner strong across the board still got two
supervised agents. `profile_compiler` now classifies against absolute thresholds
(`STRONG_FLOOR`, `DEVELOPING_CEILING`) and never ranks a learner against
themselves. `sixs/test_selfreport.py` holds that line.

**Courses** — 16 domain tracks under Training. Domains are *courses*, not
certifications.

Pricing: $0 / $79 / $399.

---

## Architecture

Python stdlib + static HTML + Postgres. **No Node, no framework, no ORM, no ML.**

- `backend/training_backend.py` — one `ThreadingHTTPServer` on :9995, plain
  if/elif routing. Serves `/train/*`, `/auth/*`, `/pay/*`, `/surveyor/*`.
- `backend/cordia_auth.py` — accounts, PBKDF2 (200k rounds), hashed session
  tokens, email 2FA.
- `backend/surveyor/` — 19 modules: `types` (schema + the never-negative guard),
  `question_strategy`, `scenarios`, `freeform`, `extractor`, `scorer`,
  `identifiers`, `recommendation`, `adaptation`, `store`, `pipeline`.
- Apache terminates TLS and reverse-proxies to 127.0.0.1.
- 21 static pages sharing `cordia-shell.js` + `cordia-ui.css`.

Three agent services (`hive_bus` :9999, `soul_orchestrator` :9992,
`cordia_engineer`) run alongside. They are internal infrastructure, bound to
loopback, not publicly proxied.

**The survey works with no model at all.** Chips make stage 1 and 2 exact, so
extraction quality is irrelevant to the recommendation. When an LLM is absent
the system says "Limited mode" rather than faking it.

---

## Data on hand

| | |
|---|---|
| Accounts | 18 |
| Surveyor profiles | 17 |
| Survey messages | 497 |
| Exam corpus | 280 rows, 13 learners |
| Rater agreement (κ) | **0 ratings — never run** |
| Entitlements | 0 |
| `outcomes` (did the advice help) | 0 |

**Nearly all of this is test data generated during development.** Treat every
number above as synthetic until real participants run through it.

---

## The three things most likely to be misunderstood

1. **The "77-item rater study" is not an exam and not a survey.** It is the
   two-rater calibration study at `rate.html`, restricted to two named accounts.
   The 77 items are real CordiaAIE-1 answers. Two humans grading them
   independently, and their Cohen's κ, is the *only* evidence the automated
   scorer works. It has never been run. **Do not delete it** — it is the sole
   route to validating a certification that is already being sold. It is hidden
   from the public catalogue because it read as a stray extra exam.

2. **The certification is unvalidated.** κ is undefined. Any claim that the
   score means something is currently unsupported. Running it is a config
   change and an afternoon of grading — `docs/RUNBOOK-kappa-study.md` has the
   steps, the pass bar, and the two things that make the result meaningless if
   you get them wrong. Start with its section 0: it prints whether the pool is
   even large enough before you spend the afternoon.

3. **The profile is composition, not inference.** Six of ten identifiers are
   ≥90% determined by a single answer — `risk_awareness = high` produces "Risk
   reader" 100% of the time. It reads as accurate because it is a mirror. The
   scenarios are the first attempt at genuine inference; whether stated and
   revealed answers actually diverge in real people is **unknown and is the
   single most interesting number the first 30–50 responses will produce.**

---

## Security posture

Audited 2026-08-03. Fixed and verified:

- Unauthenticated corpus writes with forgeable learner attribution — anyone
  could overwrite a learner's exam answers and change their certification
  result. Identity now comes from the session only.
- **Unauthenticated remote prompt injection into an agent with shell access.**
  `hive_bus` and `soul_orchestrator` had no auth on any route, were bound to
  0.0.0.0, publicly proxied, and `cordia_engineer` feeds bus messages into
  `claude -p` with `Read,Write,Edit,Bash`. Closed in four layers: proxies
  removed, loopback binds, ufw, shared-secret auth that fails closed.
- Account enumeration at signup; anonymous bulk corpus export; wildcard CORS;
  missing CSP.

Verified clean: SQL injection (all parameterized), XSS (including stored
XSS against admin), IDOR on every Surveyor route, session handling.

Still open: CSP carries `'unsafe-inline'` (44 inline blocks); the payment
webhook uses a bearer header rather than a body HMAC; `/irp/` (:9998) is
unaudited.

Auth: password + emailed code on **first sign-in per device**; afterwards
password only, device trusted 90 days via a hashed token scoped to token *and*
email. Password is always required.

---

## Standing constraints

- **No ML on the live learner path.** Rules plus at most one extraction call. If
  a *learner-visible* feature needs a model to work, delete it rather than grow
  one. The boundary is the authority, not the import list: `embedding_scoring.py`
  (sentence-transformers + FAISS) and the char n-gram TF-IDF half of
  `sixs/scorer.py` both exist and both run, but neither can certify or gate
  anyone. Anything that decides something a person sees stays stdlib and
  debuggable at 2am. The earlier flat "No ML" line no longer described the
  repository and was read as gospel at least once.
- **Never-negative is not negotiable.** Rename a card rather than loosen the guard.
- Host is 2 cores / ~7 GB / no GPU. Any real model must be hosted behind the
  `call_llm` seam.
- Nous API key expired 2026-08-01; the LLM path is currently mock.

---

## What to do next

1. **Put real people through the survey.** Everything downstream is blocked on
   this and nothing else. `GET /surveyor/export?what=profiles` is the analysis
   shape.
2. Watch the drop-off point and the stated-vs-revealed disagreement rate.
3. Phase 2 designs from that data — cluster co-occurring answers into archetypes.
4. Unblocked but unstarted: run the κ study; add a "did this help?" prompt so
   the `outcomes` table finally holds something.
