#!/usr/bin/env python3
"""HiveBus v2 — inter-agent message bus. Port 9999.
JSONL logs at /var/lib/cordia/log/<name>.log. Stdlib only."""
import json, os, time, threading, uuid, re
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 9999

# Bind address. Defaults to loopback: these services have no authentication on
# any route, and were previously bound to 0.0.0.0 AND proxied publicly, which
# let anyone on the internet read the inter-agent message bus and POST a message
# addressed to 'engineer' — whose poller feeds message text into `claude -p`
# with --allowedTools Read,Write,Edit,Bash. Unauthenticated prompt injection
# into an agent with shell access on this box.
#
# Everything that legitimately talks to these runs on this host and already uses
# 127.0.0.1 (see cordia-engineer.service). Override only with a specific private
# address; never 0.0.0.0.
BIND = os.environ.get('CORDIA_BIND', '127.0.0.1')

LOGDIR = '/var/lib/cordia/log'
os.makedirs(LOGDIR, exist_ok=True)
lock = threading.RLock()

def logfile(name):
    name = re.sub(r'[^a-zA-Z0-9_.-]', '', name)[:64] or 'Hive'
    return os.path.join(LOGDIR, name + '.log')

def append(name, msg):
    with lock:
        with open(logfile(name), 'a') as f:
            f.write(json.dumps(msg) + '\n')

def read_log(name, limit=50):
    path = logfile(name)
    if not os.path.exists(path):
        return None
    rows = []
    with lock, open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                try: rows.append(json.loads(line))
                except Exception: pass
    return rows[-limit:]


# ---------------- authentication ----------------
#
# The bus had no authentication on any route. Combined with a public Apache
# proxy and a 0.0.0.0 bind, that meant anyone on the internet could read every
# inter-agent message and, worse, POST one addressed to 'engineer' — whose
# poller feeds message text straight into `claude -p` with
# --allowedTools Read,Write,Edit,Bash. Unauthenticated prompt injection into an
# agent holding a shell on this box.
#
# Network exposure is closed (loopback bind, proxy removed, ufw). This is the
# control that does not depend on the network staying closed: an SSRF anywhere
# on this host, or a future proxy rule added by mistake, should still not be
# enough to drive the agents.
#
# Shared secret rather than anything richer because every caller is a local
# systemd unit reading the same env file. Compared with compare_digest so a
# wrong guess leaks nothing through timing.
SECRET = os.environ.get('CORDIA_BUS_SECRET', '')


def _authed(handler):
    """True when the caller proved it holds the bus secret.

    Fails CLOSED: with no secret configured nothing is accepted, because the
    alternative — treating 'unset' as 'allow' — is exactly how this was wide
    open in the first place."""
    if not SECRET:
        return False
    supplied = handler.headers.get('X-Cordia-Bus', '')
    return hmac.compare_digest(supplied, SECRET)


class H(BaseHTTPRequestHandler):
    def _json(self, obj, code=200):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(b)))
        self.end_headers()
        self.wfile.write(b)
    def log_message(self, *a): pass
    def _body(self):
        n = int(self.headers.get('Content-Length', 0))
        if n > 1_000_000: raise ValueError('too large')
        return json.loads(self.rfile.read(n) or b'{}')

    def do_GET(self):
        p = urlparse(self.path).path
        if p == '/hive/status':
            logs = [f[:-4] for f in os.listdir(LOGDIR) if f.endswith('.log')]
            total = sum(len(read_log(l, 100000) or []) for l in logs)
            self._json({'status': 'running', 'uptime': time.time(), 'logs': len(logs), 'messages_total': total})
        elif p == '/hive/logs':
            if not _authed(self):
                self._json({'error': 'unauthorised'}, 401); return
            out = []
            for f in sorted(os.listdir(LOGDIR)):
                if f.endswith('.log'):
                    path = os.path.join(LOGDIR, f)
                    with lock:
                        n = sum(1 for _ in open(path)) if os.path.exists(path) else 0
                    out.append({'name': f[:-4], 'messages': n, 'file_size': os.path.getsize(path)})
            self._json({'logs': out})
        elif p == '/hive/messages':
            # message bodies are inter-agent content; status stays open as a
            # healthcheck but this does not
            if not _authed(self):
                self._json({'error': 'unauthorised'}, 401); return
            q = parse_qs(urlparse(self.path).query)
            name = q.get('log', [''])[0]
            limit = int(q.get('limit', ['50'])[0])
            rows = read_log(name, limit)
            if rows is None:
                self._json({'error': f"Log '{name}' not found"}, 404)
            else:
                self._json({'messages': rows})
        else:
            self._json({'error': 'not found'}, 404)

    def do_POST(self):
        p = urlparse(self.path).path
        if not _authed(self):
            self._json({'error': 'unauthorised'}, 401); return
        try:
            body = self._body()
        except Exception as e:
            self._json({'error': str(e)}, 400); return
        if p == '/hive/message':
            to = str(body.get('to', ''))[:64]
            if not to:
                self._json({'error': 'to required'}, 400); return
            msg = {
                'id': uuid.uuid4().hex[:12],
                'ts': time.time(),
                'from': str(body.get('from', 'anon'))[:64],
                'to': to,
                'type': str(body.get('type', 'message'))[:32],
                'text': str(body.get('text', ''))[:50000],
                'meta': body.get('meta') if isinstance(body.get('meta'), dict) else {},
            }
            append(to, msg)
            append('Hive', msg)
            self._json({'ok': True, 'id': msg['id']})
        else:
            self._json({'error': 'not found'}, 404)

if __name__ == '__main__':
    print(f'HiveBus on :{PORT}')
    HTTPServer((BIND, PORT), H).serve_forever()
