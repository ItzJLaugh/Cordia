# Runbook — 6S capture layer (STEP 1)

Every command here is run **by you, on the VPS**. Nothing in this repo connects
to the server on its own.

Ordering matters. Section 0 is read-only and answers the row-count question
before anything is created. Do not skip section 1.

Shadow mode: nothing here changes what a learner sees. `cordaie_scoring.py`
stays authoritative for every learner-visible number.

---

## 0. Row counts — read-only, run this first

No database, no deploy, no writes. Stdlib only. Paste as one block:

```bash
python3 - <<'PY'
import json, os
from collections import Counter
D = "/var/lib/cordia/corpus"
def rows(p):
    out, bad = [], 0
    if not os.path.exists(p): return out, -1
    for line in open(p, encoding="utf-8", errors="replace"):
        line = line.strip()
        if not line: continue
        try: out.append(json.loads(line))
        except Exception: bad += 1
    return out, bad
corpus, cbad = rows(os.path.join(D, "corpus.jsonl"))
ratings, rbad = rows(os.path.join(D, "ratings.jsonl"))
per = {}
for r in ratings:
    rid, who = str(r.get("response_id","")), str(r.get("rater",""))
    if rid and who: per.setdefault(rid, set()).add(who)
multi = [k for k,v in per.items() if len(v) >= 2]
ids = {str(c.get("id","")) for c in corpus}
print("corpus records              :", len(corpus), f"(unparseable: {cbad})")
print("rating records              :", len(ratings), f"(unparseable: {rbad})")
print("responses with >=1 rating   :", len(per))
print("responses with 2+ raters    :", len(multi))
print("orphan ratings (no response):", sum(1 for k in per if k not in ids))
print("distinct learners           :", len({str(c.get('learner','')) for c in corpus}))
print("distinct tracks             :", len({str(c.get('track','')) for c in corpus}))
print("rating levels               :", dict(Counter(str(r.get('level','')) for r in ratings)))
PY
```

`responses with 2+ raters` is the number that matters — it is the size of the
inter-rater validation set available today.

---

## 1. Snapshot the VPS

Before any command in sections 2+. Hostinger panel → VPS → Snapshots → Create.
Wait for completion. Rollback must be a real option before the first write.

---

## 2. Deploy the code

```bash
cd /opt/cordia && git fetch && git checkout feat/6s-capture && git pull
ls backend/sixs/          # rubric.py scorer.py store.py textmetrics.py migrate_jsonl.py gate_test.py
```

No pip install. No virtualenv. The live path is standard library plus
`psycopg2`, which is already present.

Confirm the boundary holds:

```bash
grep -rE '^\s*(import|from)\s+(numpy|sklearn|scipy|matplotlib|pandas)' backend/ && \
  echo "BOUNDARY VIOLATED" || echo "stdlib boundary intact"
```

---

## 3. Run the verification gate on a scratch database

Never against the production database. Create a throwaway one:

```bash
sudo -u postgres createdb cordia_scratch
sudo -u postgres psql -c "GRANT ALL ON DATABASE cordia_scratch TO cordia;"
```

Run the gate against it:

```bash
cd /opt/cordia
CORDIA_PG_DSN='postgresql://cordia:PASSWORD@127.0.0.1:5432/cordia_scratch' \
  python3 backend/sixs/gate_test.py
```

Expect `GATE: PASS` and exit code 0. If it fails, stop — do not create the
tables in production. Drop the scratch DB when done:

```bash
sudo -u postgres dropdb cordia_scratch
```

---

## 4. Back up before creating anything

The backup routine goes in **before** the first real write, not after.

```bash
sudo mkdir -p /var/backups/cordia && sudo chown postgres:postgres /var/backups/cordia
sudo -u postgres bash -c 'pg_dump cordia | gzip > /var/backups/cordia/pre-6s-$(date +%F-%H%M).sql.gz'
ls -lh /var/backups/cordia/
```

Then schedule it. As root:

```bash
cat >/etc/cron.d/cordia-pgdump <<'EOF'
# nightly logical backup, 14-day retention
30 3 * * * postgres pg_dump cordia | gzip > /var/backups/cordia/cordia-$(date +\%F).sql.gz
40 3 * * * root find /var/backups/cordia -name 'cordia-*.sql.gz' -mtime +14 -delete
EOF
systemctl restart cron
```

Verify a dump actually restores — an untested backup is not a backup:

```bash
sudo -u postgres createdb cordia_restoretest
gunzip -c /var/backups/cordia/pre-6s-*.sql.gz | sudo -u postgres psql cordia_restoretest -q
sudo -u postgres psql cordia_restoretest -c '\dt'
sudo -u postgres dropdb cordia_restoretest
```

---

## 5. Create the schema in production

Additive only: four new tables, no change to `accounts`, `sessions`, `pending`,
`login_codes` or `devices`.

```bash
cd /opt/cordia
set -a; . /etc/cordia/cordia.env; set +a
python3 -c "import sys; sys.path.insert(0,'backend'); from sixs import store; store.init_schema(); print(store.counts())"
```

Expect all four counts at 0.

---

## 6. Migrate the JSONL archive

Dry run first — reads the files, writes nothing:

```bash
cd /opt/cordia
set -a; . /etc/cordia/cordia.env; set +a
python3 backend/sixs/migrate_jsonl.py --report
```

Then apply. Idempotent — safe to re-run:

```bash
python3 backend/sixs/migrate_jsonl.py --apply
```

The archive is opened read-only. `corpus.jsonl` and `ratings.jsonl` are never
written, moved or truncated. Confirm:

```bash
ls -l --time-style=full-iso /var/lib/cordia/corpus/
```

Modification times should be unchanged except by live traffic.

---

## 7. Rollback

The migration only ever inserts into the four new tables. To undo completely:

```sql
DROP TABLE IF EXISTS outcomes, human_grades, scores, submissions CASCADE;
```

The JSONL archive is untouched, so nothing is lost by dropping them. If
something worse happened, restore the section-4 dump or roll back the snapshot.

---

## Known issues logged during this work — not blocking Aug 2

1. **`training_backend.py` runs as root.** It reads `/root/.hermes/auth.json`
   for LLM credentials, which implies the whole web-facing service runs as
   root. A public HTTP handler running as root is one parsing bug away from
   full host compromise. Fix: dedicated `cordia` service user, credentials
   moved to `/etc/cordia/cordia.env`, systemd unit with `User=cordia`,
   `NoNewPrivileges=yes`, `ProtectSystem=strict`.

2. **Deployment config is unversioned.** There is no nginx/Apache config, no
   systemd unit and no deploy script anywhere in the repo. Production config
   exists only on that one machine; if it is lost, the config is lost with it.
   Capture it into the repo as documentation while you are on the box:

   ```bash
   mkdir -p /opt/cordia/deploy/captured
   cp /etc/systemd/system/cordia*.service      /opt/cordia/deploy/captured/ 2>/dev/null
   apache2ctl -S                             > /opt/cordia/deploy/captured/apache-vhosts.txt 2>&1
   cp -r /etc/apache2/sites-enabled           /opt/cordia/deploy/captured/ 2>/dev/null
   cp -r /etc/nginx/sites-enabled             /opt/cordia/deploy/captured/ 2>/dev/null
   crontab -l                                > /opt/cordia/deploy/captured/root-crontab.txt 2>&1
   systemctl list-units --type=service --state=running \
                                             > /opt/cordia/deploy/captured/running-services.txt
   ```

   **Scrub before committing** — vhost files and env dumps can contain
   secrets. Review every captured file, then commit.

---

## 8. Shadow scoring on the CordiaAIE exam

Wired into `training_backend.py`. Three additions, 40 lines, zero deletions:
a soft import, one `submit()` call in `_respond`, and a new read-only endpoint.

**What a learner sees: nothing.** `cordaie_scoring.py` still produces every
visible number. `/train/respond` returns the identical payload it always did.

**What ops sees: nothing.** `/train/status` is byte-identical, so the Rust TUI
cannot be affected. The 6S health lives on a separate endpoint.

### Restart and verify

```bash
systemctl restart cordia-training     # confirm the real unit name first
journalctl -u cordia-training -n 30 --no-pager
```

If the `sixs` package or `psycopg2` is missing, you will see
`6S shadow scoring unavailable (...); exam unaffected` on stderr and the exam
runs exactly as before. That is the designed degradation, not a failure.

Check the exam still works, then check 6S separately:

```bash
curl -s localhost:9995/train/status | head -c 300;   echo
curl -s localhost:9995/train/6s/status | python3 -m json.tool
```

Expect `shadow_mode: true`, `learner_visible: false`, a live worker, and
`tables` counts that climb as learners submit.

### Kill switch

Shadow scoring is off with one environment variable — no code change, no
redeploy:

```bash
echo 'CORDIA_6S_SHADOW=0' >> /etc/cordia/cordia.env
systemctl restart cordia-training
```

`CORDIA_6S_QUEUE_MAX` (default 256) bounds the in-memory queue. When it fills,
jobs are dropped and counted rather than blocking a submission.

### Why this cannot slow the exam down

`submit()` enqueues and returns — no scoring, no file reads, no database calls
on the request thread. A single daemon worker does the work behind a
`BaseException` handler. Measured in `backend/sixs/test_shadow.py`: 0.7 ms to
return with the database pointed at a dead port.

Run those tests on the box after deploying — they need no database:

```bash
cd /opt/cordia && python3 backend/sixs/test_shadow.py
```

Expect `27/27 checks passed`.

---

## What is deliberately NOT here

No `/score` or `/grade` HTTP endpoint for external callers, no `training.html`
changes, no learner-visible matrix, no radar or heatmap rendering. Those are
STEP 2 and STEP 3, and they start only after this gate passes and the row
counts are reviewed.

The 6S numbers are being recorded, not shown. They stay that way until
validation clears and the version string loses `-unvalidated`.
