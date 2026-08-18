# Cordia Surveyor Runtime Setup

This slice needs a reachable PostgreSQL connection, the PostgreSQL driver, and
an authenticated-encryption key before it can run live. They are intentionally
not stored in the repository.
Production uses the existing `/etc/cordia/cordia.env` convention and the
existing `training_backend.py` process on port 9995.

## Required environment

Start from `.env.surveyor.example`; copy its names into the deployment secret
store or `/etc/cordia/cordia.env`, then replace every placeholder.

```text
CORDIA_PG_DSN=postgresql://...
CORDIA_VAULT_KEY=<Fernet key>
GMAIL_USER=ops@example.com
GMAIL_APP_PASSWORD=<Gmail app password>
HF_HOME=/var/lib/cordia/huggingface
```

Generate a new Fernet key in the target environment only:

```powershell
& 'C:\Users\jacks\AppData\Local\Programs\Python\Python312\python.exe' -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Install the required backend packages, then run the non-secret readiness
check. The requirements select the official CPU-only PyTorch wheel so the
embedding shadow scorer does not pull CUDA libraries onto the server. Its
failure remains non-blocking: the authoritative rubric scorer, Surveyor, and
the live workspace continue operating, and preflight reports the missing
runtime components without exposing configuration values:

```powershell
pip install -r requirements.txt
python -m surveyor.preflight
```

Run the repeatable implementation checks before any deployment:

```powershell
python -m unittest tests.test_library tests.test_artifacts tests.test_capability_gateway tests.test_github_connector tests.test_hitl_policy tests.test_intent_misses tests.test_preflight tests.test_runtime_prompt tests.test_skills tests.test_vault tests.test_workspace_state sixs.test_selfreport sixs.test_shadow -v
```

The preflight reports only missing variable names. It never prints values.
For local development only, `CORDIA_DEV_2FA=1` may replace the SMTP pair; do
not use that override in production.

For a plain-HTTP localhost preview only, set `CORDIA_COOKIE_SECURE=0`; the
default remains secure cookies for every deployed environment.

## Deployment health checks

After the existing Apache/systemd deployment starts the backend, use
`GET /healthz` for a public-safe readiness result. It returns only
`{"ok": true}` with HTTP 200 or `{"ok": false}` with HTTP 503; it never
reveals secret names, database locations, or connector state. Detailed
preflight information remains authenticated at `GET /surveyor/preflight`.

## Repeatable host rollout

The historical production service and Apache virtual host are host-managed, not
stored in this repository. Versioned examples are available at
`deploy/cordia-backend.service.example` and
`deploy/apache-surveyor.conf.example`; review their account, Python, and
document-root assumptions before adopting them.

On a Debian/Ubuntu VPS, the safe rollout order is:

```bash
# From the checked-out Cordia repository.
sudo install -d -m 0750 -o cordia -g cordia /etc/cordia /var/lib/cordia /var/lib/cordia/huggingface
sudo install -m 0640 -o root -g cordia backend/.env.surveyor.example /etc/cordia/cordia.env
# Edit /etc/cordia/cordia.env locally on the server; replace every placeholder.

python3 -m venv /opt/cordia/venv
/opt/cordia/venv/bin/pip install -r backend/requirements.txt
cd backend
/opt/cordia/venv/bin/python -m surveyor.preflight
```

Only when preflight prints `Cordia preflight: ready`, install/reload the
reviewed systemd and Apache configuration, then verify from the VPS:

```bash
sudo systemctl restart cordia-backend.service
curl --fail --silent http://127.0.0.1:9995/healthz
```

Reload Apache only after validating its edited virtual-host configuration with
the host's normal config test. Do not expose port 9995 publicly: the backend
must remain loopback-only behind the existing reverse proxy.

## What a live verification must cover

1. Start `training_backend.py` with the required environment.
2. Sign in and complete or resume Surveyor.
3. Open the profile, artifacts, and saved workspace.
4. Add a fine-grained GitHub token with repository Metadata read access; setup
   validates it with the same bounded metadata request before encryption.
5. Confirm the native repository window returns metadata and records `live`.
6. Confirm a failed refresh records `needs_attention` without deleting the
   connector confirmation.
7. Run a workspace with an approval step and confirm the decision is persisted.

## Deliberate current limits

- GitHub repository metadata is the only live connector capability.
- Other common connectors are represented in the universal catalog but need a
  concrete adapter and setup flow before being marked live.
- Approvals are durable audit records; they do not yet resume an external write.
