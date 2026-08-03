"""Schedule runner — daily digest, segmentation refresh, list sync.

This module is invoked by systemd timer or by the run-now endpoint
POST /pipeline/run/<job>. All jobs are idempotent and safe to re-run.
"""
import sys, time
from datetime import datetime, timezone, timedelta

sys.path.insert(0, '/opt/cordia/backend')
from cordia_pipeline import DSN, DIGEST_TO, DIGEST_HOUR_LOCAL, TZ_OFFSET_H, lock, _conn


def _record(name, status, error='', meta=None):
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''INSERT INTO pipeline_jobs(name,last_run,last_status,last_error,last_meta)
                       VALUES(%s,%s,%s,%s,%s)
                       ON CONFLICT (name) DO UPDATE SET
                         last_run=EXCLUDED.last_run, last_status=EXCLUDED.last_status,
                         last_error=EXCLUDED.last_error, last_meta=EXCLUDED.last_meta''',
                    (name, time.time(), status, (error or '')[:500],
                     __import__('json').dumps(meta or {})))


def _should_send_digest_now():
    """Compare current UTC hour against DIGEST_HOUR_LOCAL adjusted by TZ_OFFSET_H."""
    now = datetime.now(timezone.utc)
    local = now + timedelta(hours=TZ_OFFSET_H)
    return local.hour == DIGEST_HOUR_LOCAL


JOBS = {
    'digest': lambda: _run_digest(),
    'list_sync': lambda: _run_list_sync(),
    'abandoned_signup_scan': lambda: _run_abandoned_scan(),
    'reconcile_reach_quota': lambda: _run_reconcile_quota(),
}


def run_now(name):
    fn = JOBS.get(name)
    if not fn: return {'ok': False, 'error': f'unknown job: {name}'}
    try:
        out = fn()
        _record(name, 'ok', meta=out)
        return {'ok': True, 'job': name, **out}
    except Exception as e:
        _record(name, 'failed', error=str(e))
        return {'ok': False, 'job': name, 'error': str(e)}


def _run_digest():
    from marketing.digest import render_and_send
    if not _should_send_digest_now():
        # Called from TUI button — allow but mark 'manual'
        pass
    out = render_and_send(DIGEST_TO)
    return {'sent_to': DIGEST_TO, 'subject': out['subject'], 'manual': not _should_send_digest_now()}


def _run_list_sync():
    """Push every contact + tags into Reach via API."""
    import cordia_reach as r
    synced, errors = 0, []
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT email, name, tags, paid_tracks FROM mail_contacts')
        rows = cur.fetchall()
    for email, name, tags, paid_tracks in rows:
        result = r.upsert_contact(email, attrs={
            'first_name': (name or '').split(' ')[0] if name else '',
            'tags': tags or [],
            'custom_fields': {'paid_tracks': ','.join(paid_tracks or [])},
        })
        if result.get('ok'): synced += 1
        else: errors.append({'email': email, 'error': result.get('error')})
    return {'synced': synced, 'errors': len(errors), 'total': len(rows)}


def _run_abandoned_scan():
    """Fire abandoned-signup event for accounts that started but never verified."""
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''SELECT email FROM mail_contacts
                       WHERE 'has_account' = ANY(tags)
                         AND NOT ('exam_taker' = ANY(tags) OR 'abandoned_signup' = ANY(tags))
                         AND first_seen < %s
                         AND first_seen > %s''',
                    (time.time() - 7*86400, time.time() - 1*86400))
        candidates = [e for (e,) in cur.fetchall()]
    from marketing.outbox import apply_event
    for email in candidates:
        apply_event({'kind': 'signup_abandoned_24h', 'email': email})
    return {'candidates': len(candidates)}


def _run_reconcile_quota():
    """Read Reach usage, pause queueing if >80%, alert if hard-capped."""
    import cordia_reach as r
    usage = r.get_usage()
    pause, why = r.should_throttle(usage, hard_cap_pct=80)
    return {'usage': usage, 'pause_queue': pause, 'reason': why}


def tick():
    """Called by systemd timer every 10 min — decides which jobs to fire."""
    results = []
    if _should_send_digest_now():
        results.append(run_now('digest'))
    # Hourly-ish sweeps
    local = datetime.now(timezone.utc) + timedelta(hours=TZ_OFFSET_H)
    if local.hour == 3 and local.minute < 10:  # ~3am local
        results.append(run_now('list_sync'))
        results.append(run_now('abandoned_signup_scan'))
    if local.hour == 12 and local.minute < 10:  # ~noon local
        results.append(run_now('reconcile_reach_quota'))
    return results


if __name__ == '__main__':
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'tick'
    if cmd == 'tick':
        print(__import__('json').dumps(tick(), indent=2))
    elif cmd in JOBS:
        print(__import__('json').dumps(run_now(cmd), indent=2))
    else:
        print('jobs:', ', '.join(JOBS))
