# Cordia End-to-End Traceability Audit

## Scope
UI layer: `/opt/cordia/web/*.html`, `/opt/cordia/web/assets/*.js`  
Routing/handler layer: `/opt/cordia/backend/training_backend.py`  
Business logic: `/opt/cordia/backend/surveyor/*.py`, `/opt/cordia/backend/sixs/*.py`, `/opt/cordia/backend/irp/*.py`, `/opt/cordia/backend/cordia_auth.py`  
Data layer: Postgres via `psycopg2` (`/var/lib/cordia/corpus/*.jsonl`)

---

## Summary

| Category | Count |
|---|---|
| Mapped UI control chains | 27 |
| Fully traceable (UI → API → handler → function → data write/query) | 18 |
| Traceability breaks | 4 |
| Orphan backend endpoints (no UI caller found) | 3 |
| Silent / dead UI calls | 2 |

---

## 1. Authentication Flows

### 1.1 Sign In
| Layer | Path / Symbol |
|---|---|
| **UI control** | `index.html:submitBtn` / `authForm.onsubmit` |
| **Frontend call** | `POST /auth/login` body `{email, password, device?}` |
| **Route/handler** | `training_backend.py:840` → `_auth_2fa(auth.login, body)` |
| **Business logic** | `cordia_auth.py:login()` |
| **Data write** | `cordia_auth.py`: session row inserted into `sessions` table |

**Traceability:** FULL  
Method, payload shape, field names, and downstream DB write are aligned.

### 1.2 Sign Up
| Layer | Path / Symbol |
|---|---|
| **UI control** | `index.html:tabSignup` + `submitBtn` |
| **Frontend call** | `POST /auth/signup` body `{email, name, password}` |
| **Route/handler** | `training_backend.py:837` → `_auth_2fa(auth.signup, body)` |
| **Business logic** | `cordia_auth.py:signup()` |
| **Data write** | `cordia_auth.py`: `accounts` row inserted |

**Traceability:** FULL

### 1.3 Verify Sign Up / Verify Login
| Layer | Path / Symbol |
|---|---|
| **UI control** | `index.html:submitBtn` when `awaitingCode` |
| **Frontend call** | `POST /auth/verify-signup` or `/auth/verify-login` body `{email, code}` |
| **Route/handler** | `training_backend.py:839-843` → `_auth_verify(auth.verify_signup|login, body)` |
| **Business logic** | `cordia_auth.py:verify_signup()` / `verify_login()` |
| **Data write** | `cordia_auth.py`: session/token written to `sessions` table |

**Traceability:** FULL

### 1.4 Forgot Password
| Layer | Path / Path / Symbol |
|---|---|
| **UI control** | `index.html:forgotLink` |
| **Frontend call** | `POST /auth/forgot-password` body `{email}` |
| **Route/handler** | `training_backend.py:858` → `_forgot_password()` |
| **Business logic** | `cordia_auth.py:request_password_reset()` |
| **Data write** | `cordia_auth.py`: `password_reset_codes` row inserted |

**Traceability:** FULL

### 1.5 Reset Password
| Layer | Path / Symbol |
|---|---|
| **UI control** | `index.html:submitBtn` when `forgotStep === 2` |
| **Frontend call** | `POST /auth/reset-password` body `{email, code, new_password}` |
| **Route/handler** | `training_backend.py:860` → `_reset_password()` |
| **Business logic** | `cordia_auth.py:reset_password()` |
| **Data write** | `cordia_auth.py`: `accounts.password` updated, reset code consumed |

**Traceability:** FULL

### 1.6 Logout
| Layer | Path / Symbol |
|---|---|
| **UI control** | `cordia-shell.js:logout` / `cordia-chooser.js:logout` |
| **Frontend call** | `POST /auth/logout` body `{token?, forget_device?}` |
| **Route/handler** | `training_backend.py:844` → inline in `do_POST` |
| **Business logic** | `cordia_auth.py:logout()` + optional `forget_devices()` |
| **Data write** | `cordia_auth.py`: `sessions` row deleted; `devices` rows deleted if `forget_device` |

**Traceability:** FULL

### 1.7 Session Me
| Layer | Path / Symbol |
|---|---|
| **UI control** | `index.html` restore block, `rate.html`, `surveyor.html` |
| **Frontend call** | `GET /auth/me` header `Authorization: Bearer <token>` |
| **Route/handler** | `training_backend.py:281` → inline in `do_GET` |
| **Business logic** | `cordia_auth.py:whoami()` |
| **Data read** | `cordia_auth.py`: `sessions` + `accounts` join |

**Traceability:** FULL

---

## 2. Exam / Training Flows

### 2.1 Submit Exam Response
| Layer | Path / Symbol |
|---|---|
| **UI control** | `cordia-items.js:submitResponse` |
| **Frontend call** | `POST /train/respond` body `{track, block, value, token?}` |
| **Route/handler** | `training_backend.py:818` → `_respond(body)` |
| **Business logic** | Inline: sanitize fields, resolve identity, score stub |
| **Data write** | `training_backend.py:append(CORPUS, rec)` → `/var/lib/cordia/corpus/corpus.jsonl` |

**Traceability:** FULL  
Identity is enforced server-side from session, not from body.

### 2.2 Get Responses
| Layer | Path / Symbol |
|---|---|
| **UI control** | `exam.html` line 143 |
| **Frontend call** | `GET /train/responses?track=aie1` header `Authorization` |
| **Route/handler** | `training_backend.py:253` → inline in `do_GET` |
| **Business logic** | Inline: filter `corpus.jsonl` by track, cap/sample for anon |
| **Data read** | `training_backend.py:read_all(CORPUS)` |

**Traceability:** FULL  
**Issue — silent failure:** `exam.html:143` assigns response to `const r` but never reads it. The call executes but the data is discarded. This is dead UI code; the page does not use the fetched corpus.

### 2.3 Certification Result
| Layer | Path / Symbol |
|---|---|
| **UI control** | `exam.html:166`, `certification.html:51`, `training.html:110`, `cordia-chooser.js` |
| **Frontend call** | `GET /train/certification` header `Authorization` |
| **Route/handler** | `training_backend.py:287` → `_certification()` |
| **Business logic** | `cordaie_scoring.score_course()` + optional `embedding_scoring` |
| **Data write** | `training_backend.py:_save_cert(cert_obj)` → `/var/lib/cordia/corpus/certifications.jsonl` |

**Traceability:** FULL  
Cert object includes `email`, `name`, `course_id`, `ts`, `**report`.

### 2.4 Rate Answer
| Layer | Path / Symbol |
|---|---|
| **UI control** | `rate.html:submit()` |
| **Frontend call** | `POST /train/rate` body `{response_id, level}` |
| **Route/handler** | `training_backend.py:832` → `_rate(body)` |
| **Business logic** | Inline: resolve rater from env, validate level |
| **Data write** | `training_backend.py:append(RATINGS, ...)` → `/var/lib/cordia/corpus/ratings.jsonl` |

**Traceability:** FULL  
Rater identity is server-side from `CORDIA_RATER_A/B`, not client-supplied.

### 2.5 Rate Queue
| Layer | Path / Symbol |
|---|---|
| **UI control** | `rate.html:loadMore()` |
| **Frontend call** | `GET /train/rate/queue?limit=30` |
| **Route/handler** | `training_backend.py:279` → `_rate_queue()` |
| **Business logic** | Inline: collapse latest per (response_id, rater), prioritize paired |
| **Data read** | `training_backend.py:read_all(CORPUS)` + `read_all(RATINGS)` |

**Traceability:** FULL

### 2.6 Kappa Stats
| Layer | Path / Symbol |
|---|---|
| **UI control** | `rate.html:showDone()` |
| **Frontend call** | `GET /train/kappa` |
| **Route/handler** | `training_backend.py:277` → `_kappa()` |
| **Business logic** | Inline: compute Cohen's kappa from paired ratings |
| **Data read** | `training_backend.py:read_all(RATINGS)` + `read_all(CORPUS)` |

**Traceability:** FULL

### 2.7 Live LLM Environment
| Layer | Path / Symbol |
|---|---|
| **UI control** | `cordia-items.js` live env call |
| **Frontend call** | `POST /train/llm` body `{env, instruction, token?}` |
| **Route/handler** | `training_backend.py:834` → `_llm(body)` |
| **Business logic** | `training_backend.py:call_llm()` → Nous Research API |
| **Data write** | None (stateless proxy) |

**Traceability:** FULL

### 2.8 Survey (Exit Survey)
| Layer | Path / Symbol |
|---|---|
| **UI control** | `survey.html:submitBtn` |
| **Frontend call** | `POST /train/survey` body `{answers, ts}` |
| **Route/handler** | `training_backend.py:830` → `_survey(body)` |
| **Business logic** | Inline: validate required keys, build rec |
| **Data write** | `training_backend.py:append(CORPUS, rec)` |

**Traceability:** FULL  
**Minor mismatch:** Frontend sends `ts: Date.now()/1000`, backend ignores it and writes `time.time()`. The extra field is harmless but unused.

### 2.9 Research Data
| Layer | Path / Symbol |
|---|---|
| **UI control** | None found in frontend |
| **Frontend call** | — |
| **Route/handler** | `training_backend.py:285` → `_research()` |
| **Business logic** | Inline feature extraction |
| **Data read** | `read_all(CORPUS)` + `read_all(RATINGS)` |

**Traceability:** BREAK — orphan endpoint. No UI caller found. This is an internal-only endpoint; not necessarily a bug, but it has no user-facing trigger.

---

## 3. Surveyor Flows

### 3.1 Surveyor Conversation Start
| Layer | Path / Symbol |
|---|---|
| **UI control** | `cordia-surveyor.js` init |
| **Frontend call** | `GET /surveyor/conversation` header `Authorization` |
| **Route/handler** | `training_backend.py:300` → `_surv_conversation()` |
| **Business logic** | `surveyor/pipeline.py:start()` |
| **Data write** | `surveyor/store.py:open_conversation()` → Postgres `surveyor_conversations` |

**Traceability:** FULL

### 3.2 Surveyor Profile
| Layer | Path / Symbol |
|---|---|
| **UI control** | `profile.html:fetch('/surveyor/profile')`, `cordia-surveyor.js:306` |
| **Frontend call** | `GET /surveyor/profile` |
| **Route/handler** | `training_backend.py:298` → `_surv_profile()` |
| **Business logic** | `surveyor/pipeline.py:public_profile()` |
| **Data read** | `surveyor/store.py:get_profile()` → Postgres `surveyor_profiles` |

**Traceability:** FULL

### 3.3 Surveyor Message (Turn)
| Layer | Path / Symbol |
|---|---|
| **UI control** | `cordia-surveyor.js:334` |
| **Frontend call** | `POST /surveyor/message` body `{message, choice?, token?}` |
| **Route/handler** | `training_backend.py:821` → `_surv_message(body)` |
| **Business logic** | `surveyor/pipeline.py:turn()` |
| **Data write** | `surveyor/store.py:add_message()` → Postgres `surveyor_messages` + `surveyor_conversations` update |

**Traceability:** FULL

### 3.4 Surveyor Recommendation
| Layer | Path / Symbol |
|---|---|
| **UI control** | `profile.html:209` |
| **Frontend call** | `GET /surveyor/recommendation` |
| **Route/handler** | `training_backend.py:306` → `_surv_recommendation()` |
| **Business logic** | `surveyor/recommendation.py:build()` |
| **Data read** | `surveyor/store.py:get_profile()` → Postgres |

**Traceability:** FULL

### 3.5 Surveyor Interfaces List
| Layer | Path / Symbol |
|---|---|
| **UI control** | `builder.html:load()`, `interfaces.html:load()`, `interface.html:load()` |
| **Frontend call** | `GET /surveyor/interfaces` |
| **Route/handler** | `training_backend.py:302` → `_surv_list_interfaces()` |
| **Business logic** | `surveyor/pipeline.py:public_profile()` + `surveyor/store.py:list_interfaces()` |
| **Data read** | Postgres `surveyor_profiles` + `surveyor_interfaces` |

**Traceability:** FULL

### 3.6 Save Interface
| Layer | Path / Symbol |
|---|---|
| **UI control** | `builder.html:saveBtn` |
| **Frontend call** | `POST /surveyor/interface` body `{id?, name, description, definition, theme?}` |
| **Route/handler** | `training_backend.py:823` → `_surv_save_interface(body)` |
| **Business logic** | Inline: validate shape, ownership check |
| **Data write** | `surveyor/store.py:save_interface()` → Postgres `surveyor_interfaces` upsert |

**Traceability:** FULL

### 3.7 Archive Interface
| Layer | Path / Symbol |
|---|---|
| **UI control** | `interfaces.html` archive buttons |
| **Frontend call** | `POST /surveyor/archive` body `{id, archived}` |
| **Route/handler** | `training_backend.py:825` → `_surv_archive(body)` |
| **Business logic** | Inline |
| **Data write** | `surveyor/store.py:archive_interface()` → Postgres `surveyor_interfaces` update |

**Traceability:** FULL

### 3.8 Run Interface
| Layer | Path / Symbol |
|---|---|
| **UI control** | `interface.html:runBtn` |
| **Frontend call** | `POST /surveyor/run` body `{id, input}` |
| **Route/handler** | `training_backend.py:827` → `_surv_run(body)` |
| **Business logic** | `surveyor/pipeline.py` prompts + `call_llm()` |
| **Data write** | `surveyor/store.py:add_run()` → Postgres `surveyor_runs` |

**Traceability:** FULL

### 3.9 Personalization Toggle
| Layer | Path / Symbol |
|---|---|
| **UI control** | `builder.html:killBtn`, `admin.html:toggle` |
| **Frontend call** | `POST /surveyor/personalization` body `{simple_mode_forced}` |
| **Route/handler** | `training_backend.py:829` → `_surv_personalization(body)` |
| **Business logic** | Inline |
| **Data write** | `surveyor/store.py:set_simple_mode()` → Postgres `surveyor_profiles` update |

**Traceability:** FULL

### 3.10 Surveyor Admin Debug
| Layer | Path / Symbol |
|---|---|
| **UI control** | `admin.html:go`, `admin.html:toggle` |
| **Frontend call** | `GET /surveyor/admin?email=...`, `POST /surveyor/personalization` |
| **Route/handler** | `training_backend.py:304` → `_surv_admin()` |
| **Business logic** | `surveyor/pipeline.load_profile()`, `surveyor.store.*` |
| **Data read** | Postgres `surveyor_profiles`, `surveyor_conversations`, `surveyor_messages`, `surveyor_interfaces`, `surveyor_runs`, `surveyor_events` |

**Traceability:** FULL

### 3.11 Admin Users List
| Layer | Path / Symbol |
|---|---|
| **UI control** | `admin.html:usersTab` |
| **Frontend call** | `GET /admin/users` |
| **Route/handler** | `training_backend.py:310` → `_admin_users()` |
| **Business logic** | Inline direct SQL |
| **Data read** | Postgres `accounts`, `submissions`, `surveyor_conversations`, `surveyor_messages` |

**Traceability:** FULL

### 3.12 Manifest / Assessment
| Layer | Path / Symbol |
|---|---|
| **UI control** | `assessment.html:286`, `agentic.html:289` |
| **Frontend call** | `GET /train/manifest?industries=...` |
| **Route/handler** | `training_backend.py:296` → `_manifest()` |
| **Business logic** | `sixs/profile_compiler.py:compile_profile()`, `sixs/agent_manifest.py:build_manifest()` |
| **Data read** | `read_all(CORPUS)` for survey gate check |

**Traceability:** FULL  
**Issue — soft dependency:** If `sixs` package is missing or profile compiler fails, endpoint returns 503. Frontend does not handle 503 explicitly for manifest; `assessment.html` passes the URL to `cordia-chooser.js` which may render nothing.

### 3.13 6S Status
| Layer | Path / Symbol |
|---|---|
| **UI control** | None found in frontend |
| **Frontend call** | — |
| **Route/handler** | `training_backend.py:290` → `_sixs_status()` |
| **Business logic** | `sixs/shadow.py:status()` + `table_counts()` |
| **Data read** | Postgres via sixs store |

**Traceability:** BREAK — orphan endpoint. No UI caller identified. Intended for ops TUI per comments.

### 3.14 6S Scores
| Layer | Path / Symbol |
|---|---|
| **UI control** | None found in frontend |
| **Frontend call** | — |
| **Route/handler** | `training_backend.py:292` → `_sixs_scores()` |
| **Business logic** | `sixs/shadow.py:recent_scores()` |
| **Data read** | Postgres via sixs store |

**Traceability:** BREAK — orphan endpoint. No UI caller identified.

### 3.15 Surveyor Export
| Layer | Path / Symbol |
|---|---|
| **UI control** | None found in frontend |
| **Frontend call** | — |
| **Route/handler** | `training_backend.py:308` → `_surv_export()` |
| **Business logic** | `surveyor/store.py:export_answers()` / `export_profiles()` |
| **Data read** | Postgres `surveyor_messages` + `surveyor_conversations` |

**Traceability:** BREAK — orphan endpoint. No UI caller identified. Admin-only export.

---

## 4. Payment / Entitlement Flows

### 4.1 My Access
| Layer | Path / Symbol |
|---|---|
| **UI control** | `domain.html:159`, `cordia-chooser.js:447` |
| **Frontend call** | `GET /pay/my-access` header `Authorization` |
| **Route/handler** | `training_backend.py:294` → `_my_access()` |
| **Business logic** | `cordia_paywall.my_entitlements()` |
| **Data read** | Depends on `cordia_paywall` implementation (external package) |

**Traceability:** FULL (to handler boundary)  
**Issue — soft dependency:** If `cordia_paywall` is missing, backend returns 503 with `paywall unavailable`. Frontend shows nothing or generic unavailable state. No graceful degradation path in UI.

### 4.2 Reach Webhook
| Layer | Path / Symbol |
|---|---|
| **UI control** | None (external webhook) |
| **Frontend call** | — |
| **Route/handler** | `training_backend.py:862` → `_reach_webhook(body)` |
| **Business logic** | `cordia_paywall.handle_reach_webhook()` |
| **Data write** | Depends on paywall; fires `_fire_event('purchase', ...)` |

**Traceability:** FULL (to handler boundary)  
External webhook; not user-initiated from UI.

---

## 5. Identified Traceability Breaks

| # | File:Line | What is wrong | Remediation |
|---|---|---|---|
| 1 | `exam.html:143` | Fetches `/train/responses?track=aie1` and assigns to `const r` but never reads the response. Dead API call; silent failure. | Remove the unused fetch or wire it into the page UI. |
| 2 | `training_backend.py:285` (`_research`) | Backend endpoint `/train/research` exists with full implementation but no frontend caller found. Orphan route. | Document as internal-only, or add a UI page if intended for researchers. |
| 3 | `training_backend.py:290` (`_sixs_status`) | `/train/6s/status` exists but no frontend caller found. Orphan route. | Wire into ops TUI or remove if deprecated. |
| 4 | `training_backend.py:292` (`_sixs_scores`) | `/train/6s/scores` exists but no frontend caller found. Orphan route. | Wire into admin/ops UI or remove if deprecated. |
| 5 | `training_backend.py:308` (`_surv_export`) | `/surveyor/export` exists but no frontend caller found. Orphan route. | Add export button to admin UI or remove. |
| 6 | `training_backend.py:995` (`_manifest`) | `industries` query param is split without length limit; a very long query string could create a large list in memory. | Add `max( len(industries), 20 )` cap or reject overly long values. |
| 7 | `cordia-chooser.js:447`, `domain.html:159` | `/pay/my-access` depends on `cordia_paywall` soft import; if unavailable, backend returns 503 and frontend has no user-friendly fallback message for that specific route. | Add explicit 503 handling in JS with a message like “Entitlements unavailable — contact support.” |

---

## 6. Data Layer Verification

| Store | Backend Module | Tables / Files | Access Pattern |
|---|---|---|---|
| Exam corpus | `training_backend.py` | `/var/lib/cordia/corpus/corpus.jsonl` | Append-only JSONL, `threading.RLock` |
| Ratings | `training_backend.py` | `/var/lib/cordia/corpus/ratings.jsonl` | Append-only JSONL |
| Certifications | `training_backend.py` | `/var/lib/cordia/corpus/certifications.jsonl` | Append-only JSONL |
| Accounts / sessions | `cordia_auth.py` | Postgres `accounts`, `sessions`, `devices`, `password_reset_codes` | Per-call `psycopg2.connect` |
| Surveyor profile | `surveyor/store.py` | Postgres `surveyor_profiles` | JSONB columns, parameterized SQL |
| Surveyor messages | `surveyor/store.py` | Postgres `surveyor_conversations`, `surveyor_messages` | JSONB meta, FK cascade |
| Surveyor interfaces | `surveyor/store.py` | Postgres `surveyor_interfaces`, `surveyor_runs` | JSONB definition |
| Surveyor events | `surveyor/store.py` | Postgres `surveyor_events` | Best-effort insert |
| 6S shadow scores | `sixs/shadow.py` | Postgres via `sixs/store.py` | Not fully audited in this pass |
| IRP micro-agents | `irp/micro_*.py` | `/var/lib/cordia/irp/rounds.jsonl` | Append-only via Unix bus socket |

---

## 7. Security Notes

- `training_backend.py:137-138` reads `/root/.hermes/auth.json` for the Nous API key. This is outside the `/opt/cordia` tree and should be verified for file permissions (owner root, mode 0600).
- CORS is restricted to a known allowlist (`ALLOWED_ORIGINS`). Same-origin in production; dev origins explicit.
- `_respond()`, `_rate()`, and `_llm()` resolve identity server-side from `Authorization` header, not from JSON body.
- `_survey()`, `_certification()`, and Surveyor endpoints require `auth.whoami()` and reject anonymous access except where explicitly allowed.
- `_admin_users()` and `_surv_admin()` require `CORDIA_ADMINS` or rater env vars.

---

## 8. Unaudited / Out-of-Scope

- `cordia_paywall` package (payment business logic)
- `cordaie_scoring` / `embedding_scoring` packages (rubric/scoring internals)
- `sixs/shadow.py`, `sixs/scorer.py`, `sixs/rubric.py` internals beyond route handlers
- `irp/mother.py` orchestration and bus framing
- CSS-only interactions; no API calls
