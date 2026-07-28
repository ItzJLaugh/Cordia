#!/usr/bin/env python3
"""HiveBus v2 — inter-agent message bus. Port 9999.
JSONL logs at /var/lib/cordia/log/<name>.log. Stdlib only."""
import json, os, time, threading, uuid, re
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs

PORT = 9999
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
            out = []
            for f in sorted(os.listdir(LOGDIR)):
                if f.endswith('.log'):
                    path = os.path.join(LOGDIR, f)
                    with lock:
                        n = sum(1 for _ in open(path)) if os.path.exists(path) else 0
                    out.append({'name': f[:-4], 'messages': n, 'file_size': os.path.getsize(path)})
            self._json({'logs': out})
        elif p == '/hive/messages':
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
    HTTPServer(('0.0.0.0', PORT), H).serve_forever()
