#!/usr/bin/env python3
"""Cordia first-party tracker + redirector. Port 9996.

Endpoints:
  GET  /t.js                    serve the ~2KB tracker script (also served from web/t.js)
  GET  /p                      record a page view:  /p?p=/path&r=ref&u=anon&s=session
  GET  /e                      record a custom event: /e?k=signup&u=anon&s=session&m=...
  GET  /o                      open pixel:          /o?id=<send_id>  → 1x1 gif, log open
  GET  /c                      click redirect:      /c?id=<send_id>&u=<url>
  GET  /diag                   health + recent events

Privacy:
  - First-party only (same domain). Sets anon UUID cookie on first hit.
  - IP stored as /24 hash only; raw IP never written with event row.
  - No third-party scripts. No fingerprinting. No cross-site tracking.

Storage: Postgres. Tables created on init().
  events(anon, session, kind, path, ref, meta jsonb, day, ts)
  sessions(anon, first_seen, last_seen, ua_class, entry_path)
  opens(send_id, anon, day)             # unique opens per day
  clicks(send_id, anon, url, day)
"""
import hashlib, hmac, json, os, re, sys, time, threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

import psycopg2
import psycopg2.extras

sys.path.insert(0, '/opt/cordia/backend')
from cordia_email import _log as _email_log  # reuse send log namespace

DSN = os.environ.get('CORDIA_PG_DSN', '')
PORT = 9996
WEB_T_JS = '/opt/cordia/web/t.js'

lock = threading.RLock()

GIF_1x1 = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00'
           b'!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00'
           b'\x00\x02\x02D\x01\x00;')

SALT = os.environ.get('TRACKER_HASH_SALT', 'cordia-tracker-default-salt')


def _conn():
    return psycopg2.connect(DSN)


def init():
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS track_events(
          id BIGSERIAL PRIMARY KEY,
          anon TEXT, session TEXT, kind TEXT, path TEXT, ref TEXT,
          meta JSONB, ip_h24 TEXT, ua_class TEXT, day DATE, ts DOUBLE PRECISION
        );
        CREATE INDEX IF NOT EXISTS track_events_day ON track_events(day);
        CREATE INDEX IF NOT EXISTS track_events_kind ON track_events(kind);
        CREATE INDEX IF NOT EXISTS track_events_anon ON track_events(anon);
        CREATE TABLE IF NOT EXISTS track_sessions(
          anon TEXT PRIMARY KEY,
          first_seen DOUBLE PRECISION, last_seen DOUBLE PRECISION,
          ua_class TEXT, entry_path TEXT, visits INT NOT NULL DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS track_opens(
          send_id TEXT, anon TEXT, day DATE,
          PRIMARY KEY (send_id, anon, day)
        );
        CREATE TABLE IF NOT EXISTS track_clicks(
          send_id TEXT, anon TEXT, url TEXT, day DATE,
          ts DOUBLE PRECISION
        );
        CREATE INDEX IF NOT EXISTS track_clicks_send ON track_clicks(send_id);
        ''')


def _ip24_h(ip):
    if not ip: return ''
    parts = ip.split('.')
    if len(parts) == 4:
        return hashlib.sha256((SALT + '.'.join(parts[:3])).encode()).hexdigest()[:16]
    return hashlib.sha256((SALT + ip).encode()).hexdigest()[:16]


def _ua_class(ua):
    if not ua: return 'unknown'
    ua = ua.lower()
    if 'edg/' in ua:      return 'edge'
    if 'chrome/' in ua and 'safari/' in ua: return 'chrome'
    if 'firefox/' in ua:  return 'firefox'
    if 'safari/' in ua:   return 'safari'
    if 'curl/' in ua or 'python-requests' in ua: return 'bot'
    return 'other'


def _record(anon, session, kind, path='', ref='', meta=None,
            ip='', ua=''):
    ip_h = _ip24_h(ip)
    cls = _ua_class(ua)
    now = time.time()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''INSERT INTO track_events
                       (anon,session,kind,path,ref,meta,ip_h24,ua_class,day,ts)
                       VALUES(%s,%s,%s,%s,%s,%s,%s,%s,(now() AT TIME ZONE 'UTC')::date,%s)''',
                    (anon, session, kind, path[:500], ref[:500],
                     psycopg2.extras.Json(meta or {}), ip_h, cls, now))
        if anon:
            cur.execute('''INSERT INTO track_sessions(anon,first_seen,last_seen,ua_class,entry_path,visits)
                           VALUES(%s,%s,%s,%s,%s,1)
                           ON CONFLICT (anon) DO UPDATE SET
                             last_seen=EXCLUDED.last_seen, visits=track_sessions.visits+1''',
                        (anon, now, now, cls, path[:500]))


class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def _send(self, body, code=200, ctype='text/plain'):
        if isinstance(body, str): body = body.encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(body)
    def _client_ip(self):
        if self.client_address[0] == '127.0.0.1':
            xff = self.headers.get('X-Forwarded-For', '').split(',')
            xff = [x.strip() for x in xff if x.strip()]
            if xff: return xff[-1]
        return self.client_address[0]

    def do_GET(self):
        p = urlparse(self.path)
        q = parse_qs(p.query)
        ip = self._client_ip()
        ua = self.headers.get('User-Agent', '')
        anon  = (q.get('u', [''])[0] or '')[:64]
        sess  = (q.get('s', [''])[0] or '')[:64]

        if p.path == '/t.js':
            try:    self._send(open(WEB_T_JS).read(), ctype='application/javascript; charset=utf-8')
            except: self._send('// tracker offline', ctype='application/javascript')
            return

        if p.path == '/p':
            _record(anon, sess, 'page_view',
                    path=q.get('p',[''])[0], ref=q.get('r',[''])[0],
                    meta={'lang': q.get('lang',[''])[0][:12],
                          'sw':  q.get('sw',[''])[0][:8],
                          'sh':  q.get('sh',[''])[0][:8]},
                    ip=ip, ua=ua)
            self._send('{}', ctype='application/json')
            return

        if p.path == '/e':
            try: meta = json.loads(q.get('m',['{}'])[0])
            except Exception: meta = {}
            if not isinstance(meta, dict): meta = {}
            _record(anon, sess, (q.get('k',['custom'])[0])[:40],
                    path=(q.get('p',[''])[0])[:500], ref=(q.get('r',[''])[0])[:500],
                    meta=meta, ip=ip, ua=ua)
            self._send('{}', ctype='application/json')
            return

        if p.path == '/o':
            sid = (q.get('id',[''])[0])[:80]
            if sid and anon:
                try:
                    with lock, _conn() as c, c.cursor() as cur:
                        cur.execute('''INSERT INTO track_opens VALUES(%s,%s,(now() AT TIME ZONE 'UTC')::date)
                                       ON CONFLICT DO NOTHING''', (sid, anon))
                except Exception as e:
                    _email_log({'kind':'open_pixel_err','send_id':sid,'error':str(e)})
            self._send(GIF_1x1, ctype='image/gif')
            return

        if p.path == '/c':
            sid = (q.get('id',[''])[0])[:80]
            dst = q.get('u',[''])[0]
            if not dst.startswith(('https://','http://')):
                self._send('bad redirect', code=400); return
            if sid and anon:
                try:
                    with lock, _conn() as c, c.cursor() as cur:
                        cur.execute('''INSERT INTO track_clicks(send_id,anon,url,day,ts)
                                       VALUES(%s,%s,%s,(now() AT TIME ZONE 'UTC')::date,%s)''',
                                    (sid, anon, dst[:1000], time.time()))
                except Exception as e:
                    _email_log({'kind':'click_track_err','send_id':sid,'error':str(e)})
            self.send_response(302)
            self.send_header('Location', dst)
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            return

        if p.path == '/diag':
            with lock, _conn() as c, c.cursor() as cur:
                cur.execute('SELECT count(*), max(ts) FROM track_events')
                row = cur.fetchone()
                ev_n = int(row[0]) if row and row[0] is not None else 0
                ev_last = row[1] if row else None
                cur.execute('SELECT count(*) FROM track_sessions')
                r2 = cur.fetchone()
                sess_n = int(r2[0]) if r2 and r2[0] is not None else 0
                cur.execute('SELECT count(*) FROM track_opens WHERE day=(now() AT TIME ZONE \'UTC\')::date')
                r3 = cur.fetchone()
                opens_today = int(r3[0]) if r3 and r3[0] is not None else 0
            self._send(json.dumps({
                'status': 'ok', 'events_total': ev_n, 'events_last_ts': ev_last,
                'sessions_total': sess_n, 'opens_today': opens_today,
                'cookie_salt_set': SALT != 'cordia-tracker-default-salt',
            }, indent=2), ctype='application/json')
            return

        self._send('not found', code=404)


if __name__ == '__main__':
    init()
    print(f'cordia-tracker :{PORT}', flush=True)
    HTTPServer(('127.0.0.1', PORT), H).serve_forever()
