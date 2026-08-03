"""Outbound queue + transactional dispatch.

Every send request lands in mail_outbox with status='queued'. A background
worker drains the queue at 1Hz and calls cordia_email.send() for
transactional kinds, or cordia_reach.queue_campaign(manual_only=True) for
Reach-bound kinds.
"""
import json, os, sys, time, threading
from queue import Queue, Empty

sys.path.insert(0, '/opt/cordia/backend')
import cordia_email as em
import cordia_reach as r
from cordia_pipeline import DSN, AUTO_SEND_KINDS, REACH_DRAFT_KINDS, lock, _conn
from marketing.templates import render as render_tpl

Q = Queue()


def apply_event(ev):
    """Idempotently record an event and trigger any matching sequence."""
    kind = (ev.get('kind') or '').strip()
    email = (ev.get('email') or '').strip().lower() or None
    anon = (ev.get('anon') or '').strip() or None
    meta = ev.get('meta') or {}

    if email:
        _upsert_contact(email, name=ev.get('name'), tags=_tags_for_kind(kind),
                        paid_tracks=meta.get('paid_tracks') if isinstance(meta, dict) else None,
                        score=meta.get('score') if isinstance(meta, dict) else None)

    if kind == 'signup_verified' and email:
        enqueue_send({
            'to': email, 'kind': 'welcome_1', 'template': 'welcome_1',
            'vars': _welcome_vars(email),
        })
    elif kind == 'exam_finished' and email:
        enqueue_send({
            'to': email, 'kind': 'exam_finish', 'template': 'exam_finish',
            'vars': _exam_finish_vars(email, meta),
        })
    elif kind == 'exam_passed' and email:
        enqueue_send({
            'to': email, 'kind': 'certificate_ready', 'template': 'certificate',
            'vars': _cert_vars(email, meta),
        })
    elif kind == 'purchase' and email:
        enqueue_send({
            'to': email, 'kind': 'purchase_receipt', 'template': 'receipt',
            'vars': _receipt_vars(email, meta),
        })
    elif kind == 'signup_abandoned_24h' and email:
        enqueue_send({
            'to': email, 'kind': 'abandoned_signup_nudge', 'template': 'abandoned',
            'vars': _abandoned_vars(email),
        })


def _tags_for_kind(kind):
    base = {'has_account'}
    if kind in ('exam_finished', 'exam_passed'): base.add('exam_taker')
    if kind == 'exam_passed':                    base.add('certified')
    if kind == 'purchase':                       base.add('paying')
    if kind == 'signup_abandoned_24h':           base.add('abandoned_signup')
    return sorted(base)


def _welcome_vars(email):
    return {
        'name': email.split('@')[0].title(),
        'cta_url': 'https://cordiacode.com/learn.html',
        'unsubscribe_url': f'https://cordiacode.com/u?email={email}',
    }


def _exam_finish_vars(email, meta):
    score = meta.get('score') if isinstance(meta, dict) else None
    return {
        'name': email.split('@')[0].title(),
        'score': f'{score:.0f}' if isinstance(score, (int, float)) else '—',
        'result_url': 'https://cordiacode.com/space.html',
        'unsubscribe_url': f'https://cordiacode.com/u?email={email}',
    }


def _cert_vars(email, meta):
    score = meta.get('score') if isinstance(meta, dict) else None
    return {
        'name': email.split('@')[0].title(),
        'score': f'{score:.0f}' if isinstance(score, (int, float)) else '—',
        'cert_url': meta.get('cert_url', 'https://cordiacode.com/space.html') if isinstance(meta, dict) else 'https://cordiacode.com/space.html',
        'unsubscribe_url': f'https://cordiacode.com/u?email={email}',
    }


def _receipt_vars(email, meta):
    track = meta.get('track', 'a track') if isinstance(meta, dict) else 'a track'
    order = meta.get('order_id', '—') if isinstance(meta, dict) else '—'
    return {
        'name': email.split('@')[0].title(),
        'track': track,
        'order_id': order,
        'cta_url': 'https://cordiacode.com/space.html',
        'unsubscribe_url': f'https://cordiacode.com/u?email={email}',
    }


def _abandoned_vars(email):
    return {
        'name': email.split('@')[0].title(),
        'resume_url': f'https://cordiacode.com/index.html?email={email}',
        'unsubscribe_url': f'https://cordiacode.com/u?email={email}',
    }


def _upsert_contact(email, name=None, tags=None, paid_tracks=None, score=None):
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''INSERT INTO mail_contacts(email,name,tags,first_seen,updated)
                       VALUES(%s,%s,%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET
                         name=COALESCE(EXCLUDED.name, mail_contacts.name),
                         tags=(SELECT array(SELECT DISTINCT unnest(mail_contacts.tags || EXCLUDED.tags))),
                         updated=EXCLUDED.updated''',
                    (email, name, tags or ['has_account'], time.time(), time.time()))
        if paid_tracks:
            cur.execute('''UPDATE mail_contacts SET paid_tracks=%s, updated=%s WHERE email=%s''',
                        (paid_tracks, time.time(), email))
        if score is not None:
            cur.execute('''UPDATE mail_contacts SET exam_score=%s, updated=%s WHERE email=%s''',
                        (score, time.time(), email))


def enqueue_send(req):
    """Insert into mail_outbox + push to in-memory queue."""
    to = (req.get('to') or '').strip().lower()
    kind = (req.get('kind') or '').strip()
    if not to or '@' not in to:
        return {'ok': False, 'error': 'to required'}
    if kind not in AUTO_SEND_KINDS and kind not in REACH_DRAFT_KINDS:
        return {'ok': False, 'error': f'unknown kind: {kind}'}
    template = req.get('template') or kind
    vars_ = req.get('vars') or {}
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''INSERT INTO mail_outbox(to_email,kind,template,vars,status,created)
                       VALUES(%s,%s,%s,%s,'queued',%s) RETURNING id''',
                    (to, kind, template, json.dumps(vars_), time.time()))
        row = cur.fetchone()
        oid = row[0] if row else None
    Q.put(oid)
    return {'ok': True, 'id': oid, 'queued': kind in AUTO_SEND_KINDS}


def _send_one(out_id):
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT to_email,kind,template,vars,attempts FROM mail_outbox WHERE id=%s', (out_id,))
        row = cur.fetchone()
        if not row: return
        to, kind, template, vars_json, attempts = row
        cur.execute('UPDATE mail_outbox SET attempts=attempts+1 WHERE id=%s', (out_id,))
    vars_ = vars_json if isinstance(vars_json, dict) else json.loads(vars_json or '{}')

    if kind in AUTO_SEND_KINDS:
        rendered = render_tpl(template, vars_)
        result = em.send(to, rendered['subject'], rendered['text'], html=rendered['html'],
                         kind=kind, contact_id=to, tags=['auto'])
        status = 'sent' if result.get('ok') else 'failed'
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('''UPDATE mail_outbox
                           SET status=%s, sent=%s, send_id=%s, provider=%s, last_error=%s
                           WHERE id=%s''',
                        (status, time.time() if status=='sent' else None,
                         result.get('send_id'), result.get('provider'),
                         (result.get('error') or '')[:400], out_id))
    elif kind in REACH_DRAFT_KINDS:
        rendered = render_tpl(template, vars_)
        result = r.queue_campaign(
            name=f'{kind}-{int(time.time())}',
            subject=rendered['subject'],
            html=rendered['html'], text=rendered['text'],
            segment=_segment_for_kind(kind),
            manual_only=True, tags=[kind],
        )
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('''UPDATE mail_outbox
                           SET status='sent', sent=%s, send_id=%s, provider='reach_draft',
                               last_error=%s, meta=%s WHERE id=%s''',
                        (time.time(), result.get('id'),
                         result.get('reach_error') or '',
                         json.dumps({'draft': result.get('draft')}), out_id))
    else:
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('UPDATE mail_outbox SET status=\'skipped\', last_error=%s WHERE id=%s',
                        (f'unknown kind {kind}', out_id))


def _segment_for_kind(kind):
    return {
        're_engage_30d': 'inactive_30d',
        'monthly_digest_user': 'all_active',
        'product_news': 'all_active',
    }.get(kind, 'all')


def _drain():
    while True:
        try:
            oid = Q.get(timeout=1)
        except Empty:
            time.sleep(2); continue
        try: _send_one(oid)
        except Exception as e:
            with lock, _conn() as c, c.cursor() as cur:
                cur.execute('UPDATE mail_outbox SET status=\'failed\', last_error=%s WHERE id=%s',
                            (str(e)[:400], oid))
        time.sleep(0.2)


def start_worker():
    t = threading.Thread(target=_drain, daemon=True, name='outbox-drain')
    t.start()
    return t


# Drain any items left queued from previous runs.
def recover_queued():
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT id FROM mail_outbox WHERE status=\'queued\' ORDER BY id LIMIT 500')
        for (oid,) in cur.fetchall(): Q.put(oid)


if __name__ == '__main__':
    # CLI: python3 -m marketing.outbox enqueue '{"to":..,"kind":..,"template":..,"vars":{}}'
    if len(sys.argv) > 1 and sys.argv[1] == 'enqueue':
        req = json.loads(sys.argv[2])
        print(json.dumps(enqueue_send(req), indent=2))
