#!/usr/bin/env python3
"""Cordia pipeline — email orchestration, scheduling, digests. Port 9997.

Modules:
  marketing.sequences   pre-built lifecycle sequences (welcome, onboarding, re-engage…)
  marketing.segments    SQL segment builders (inactive, paid, churn_risk)
  marketing.templates   Jinja-style email rendering
  marketing.strategies  derives weekly strategy recommendations from tracker data
  marketing.digest      builds the daily HTML+text digest for the founder
  marketing.outbox      Postgres-backed outbound queue (transactional + reach drafts)
  marketing.cron        schedule runner (daily digest, segment refresh, list sync)

Endpoints (:9997):
  POST /pipeline/track         fire event: {kind, email?, anon?, meta?} (server enriches)
  POST /pipeline/send          transactional: {to, kind, template, vars}
  GET  /pipeline/health        status of all subsystems
  GET  /pipeline/digest/preview   text+html of today's digest
  POST /pipeline/digest/run       generate + send today's digest NOW
  GET  /pipeline/drafts        list reach campaign drafts waiting for approval
  POST /pipeline/drafts/approve  {id}  -> archive as sent
  POST /pipeline/run/{job}     trigger cron job by name

Approval gate:
  - All lifecycle templates are auto-rendered into email bodies but staged in
    /var/lib/cordia/marketing/drafts for the operator to send through Reach UI.
  - Transactional (welcome-1, exam-finish, receipt, 2FA) auto-sends via Agentic Mail.
  - Reach-segment campaigns (re-engage, monthly digest to user base) never auto-send.
"""
import hmac, json, os, sys, threading, time, traceback
from datetime import datetime, timezone
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

sys.path.insert(0, '/opt/cordia/backend')

DSN = os.environ.get('CORDIA_PG_DSN', '')
PORT = 9997
DIGEST_TO = os.environ.get('DIGEST_TO', 'jackson@cordiacode.com').strip()
DIGEST_HOUR_LOCAL = int(os.environ.get('DIGEST_HOUR_LOCAL', '8'))
TZ_OFFSET_H = int(os.environ.get('DIGEST_TZ_OFFSET_HOURS', '-5'))   # CST default

# Auto-send classes (transactional, no approval gate).
# Anything NOT in this set writes a Reach draft instead.
AUTO_SEND_KINDS = {
    'verification_code',     # 2FA (used by cordia_auth._send_code path)
    'welcome_1',             # 1st welcome — fire right after signup verify
    'exam_finish',           # score + result link
    'certificate_ready',     # PDF link when passed
    'purchase_receipt',      # Reach webhook → entitlement granted
    'abandoned_signup_nudge' # gentle 24h nudge, single send per pending
}

# Reach-bound kinds (always draft, never auto-send). Cheap on free quota.
REACH_DRAFT_KINDS = {
    're_engage_30d',         # monthly digest to inactive learners
    'monthly_digest_user',   # learner-facing summary
    'product_news',          # new track launch, pricing change
}

lock = threading.RLock()


def _conn():
    import psycopg2
    return psycopg2.connect(DSN)


def init():
    """Create pipeline tables. Safe to call repeatedly."""
    import psycopg2.extras
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS mail_outbox(
          id BIGSERIAL PRIMARY KEY,
          to_email TEXT NOT NULL,
          kind TEXT NOT NULL,
          template TEXT,
          vars JSONB,
          status TEXT NOT NULL DEFAULT 'queued',  -- queued|sent|failed|skipped
          attempts INT NOT NULL DEFAULT 0,
          last_error TEXT,
          send_id TEXT,
          provider TEXT,
          created DOUBLE PRECISION NOT NULL,
          sent DOUBLE PRECISION,
          meta JSONB
        );
        CREATE INDEX IF NOT EXISTS mail_outbox_status ON mail_outbox(status, created);
        CREATE TABLE IF NOT EXISTS mail_contacts(
          email TEXT PRIMARY KEY,
          name TEXT,
          tags TEXT[],
          first_seen DOUBLE PRECISION,
          last_event_kind TEXT,
          last_event_ts DOUBLE PRECISION,
          paid_tracks TEXT[],
          exam_score REAL,
          updated DOUBLE PRECISION
        );
        CREATE TABLE IF NOT EXISTS pipeline_jobs(
          name TEXT PRIMARY KEY,
          last_run DOUBLE PRECISION,
          last_status TEXT,
          last_error TEXT,
          last_meta JSONB
        );
        ''')


# ---- routing ----

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, obj, code=200, ctype='application/json'):
        body = json.dumps(obj, default=str).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n > 5_000_000: raise ValueError('too large')
        return json.loads(self.rfile.read(n) or b'{}')

    def do_GET(self):
        p = urlparse(self.path).path
        if   p == '/pipeline/health':       self._send(self._health())
        elif p == '/pipeline/drafts':       self._send(self._list_drafts())
        elif p == '/pipeline/digest/preview':self._send_preview()
        elif p == '/pipeline/jobs':         self._send(self._job_history())
        else: self._send({'error':'not found'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        try: body = self._body()
        except Exception as e:
            self._send({'error': str(e)}, 400); return
        try:
            if   p == '/pipeline/track':           self._on_track(body)
            elif p == '/pipeline/send':            self._on_send(body)
            elif p == '/pipeline/digest/run':      self._on_digest_run(body)
            elif p == '/pipeline/drafts/approve':  self._on_approve(body)
            elif p.startswith('/pipeline/run/'):   self._on_run_job(p.rsplit('/',1)[-1], body)
            else: self._send({'error':'not found'}, 404)
        except Exception as e:
            traceback.print_exc()
            self._send({'ok': False, 'error': str(e)}, 500)

    def _health(self):
        import cordia_email as em, cordia_reach as r
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('SELECT count(*) FROM mail_outbox WHERE status=\'queued\'')
            queued = cur.fetchone()[0]
            cur.execute('SELECT count(*) FROM mail_outbox WHERE status=\'sent\' AND sent > %s', (time.time()-86400,))
            sent_24h = cur.fetchone()[0]
        return {
            'status': 'ok',
            'email': em.health(),
            'reach': {'configured': bool(r.API_KEY), 'usage': r.get_usage()},
            'queue': {'queued': queued, 'sent_24h': sent_24h},
            'digest_to': DIGEST_TO,
        }

    def _list_drafts(self):
        import cordia_reach as r
        return {'drafts': r.list_drafts()}

    def _job_history(self):
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('SELECT name,last_run,last_status,last_error FROM pipeline_jobs ORDER BY name')
            rows = cur.fetchall()
        return {'jobs': [{'name':n, 'last_run':ts, 'last_status':s, 'last_error':e}
                         for n,ts,s,e in rows]}

    def _send_preview(self):
        from marketing.digest import render
        d = render(DIGEST_TO)
        self._send({'to': d['to'], 'subject': d['subject'], 'text': d['text'][:6000]})

    def _on_track(self, body):
        """Fire-and-forget event sink used by tracker + auth + reach webhook."""
        from marketing.outbox import apply_event
        apply_event(body)
        self._send({'ok': True})

    def _on_send(self, body):
        """Send a transactional email. Auto-queued through outbox."""
        from marketing.outbox import enqueue_send
        result = enqueue_send(body)
        self._send(result)

    def _on_digest_run(self, body):
        from marketing.digest import render_and_send
        out = render_and_send(DIGEST_TO)
        self._send(out)

    def _on_approve(self, body):
        import cordia_reach as r
        cid = (body.get('id') or '').strip()
        if not cid: self._send({'ok': False, 'error': 'id required'}, 400); return
        self._send(r.approve_draft(cid))

    def _on_run_job(self, name, body):
        from marketing.cron import run_now
        out = run_now(name)
        self._send(out)


def main():
    init()
    print(f'cordia-pipeline :{PORT}', flush=True)
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()


if __name__ == '__main__':
    main()
