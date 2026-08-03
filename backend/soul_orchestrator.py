#!/usr/bin/env python3
"""SOUL v3 — natural-language command router. Port 9992.
Routes intent to skills. Agents (like cordia-engineer) register their own
skill manifests; SOUL dispatches by posting tasks onto their HiveBus log.
Stdlib only."""
import json, os, re, time, threading, urllib.request, uuid
import hmac
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

PORT = 9992

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

HIVE = 'http://127.0.0.1:9999'
LOGDIR = '/var/lib/cordia/log'
SKILLDIR = '/var/lib/cordia/skills'
os.makedirs(LOGDIR, exist_ok=True)
os.makedirs(SKILLDIR, exist_ok=True)
lock = threading.RLock()
START = time.time()

# ---------------- built-in skills (static routes) ----------------

def hive_post(path, obj):
    req = urllib.request.Request(HIVE + path, data=json.dumps(obj).encode(),
                                 headers={'Content-Type': 'application/json',
                          'X-Cordia-Bus': os.environ.get('CORDIA_BUS_SECRET', '')})
    return json.loads(urllib.request.urlopen(req, timeout=10).read())

def sk_task_add(args, **_):
    text = args.strip()
    if not text: return {'ok': False, 'msg': 'usage: add task <text>'}
    urgent = bool(re.search(r'\burgent\b', text, re.I))
    r = hive_post('/hive/message', {'from': 'soul', 'to': 'tasks', 'type': 'task_add',
                                    'text': text, 'meta': {'urgent': urgent}})
    return {'ok': True, 'msg': f"task queued ({r['id']})" + (' [urgent]' if urgent else '')}

def sk_task_list(**_):
    rows = json.loads(urllib.request.urlopen(urllib.request.Request(
        HIVE + '/hive/messages?log=tasks&limit=20',
        headers={'X-Cordia-Bus': os.environ.get('CORDIA_BUS_SECRET', '')}), timeout=10).read())
    msgs = [m for m in rows.get('messages', []) if m.get('type') == 'task_add']
    if not msgs: return {'ok': True, 'msg': 'no tasks'}
    lines = [f"- {'[!] ' if m.get('meta',{}).get('urgent') else ''}{m['text']}" for m in msgs[-10:]]
    return {'ok': True, 'msg': 'tasks:\n' + '\n'.join(lines)}

def sk_agent_message(args, **_):
    m = re.match(r'(\S+)\s+(.*)', args.strip(), re.S)
    if not m: return {'ok': False, 'msg': 'usage: message <agent> <text>'}
    to, text = m.group(1), m.group(2)
    r = hive_post('/hive/message', {'from': 'soul', 'to': to, 'type': 'message', 'text': text})
    return {'ok': True, 'msg': f"message sent to {to} ({r['id']})"}

def sk_vps_diagnostic(**_):
    import shutil
    d = shutil.disk_usage('/')
    load = os.getloadavg()[0] if hasattr(os, 'getloadavg') else 0
    return {'ok': True, 'msg': f"disk {d.used//2**30}G/{d.total//2**30}G used, load {load:.2f}"}

def sk_web_check(args, **_):
    url = args.strip() or 'https://cordiacode.com'
    if not url.startswith('http'): url = 'https://' + url
    t0 = time.time()
    try:
        code = urllib.request.urlopen(url, timeout=10).getcode()
        return {'ok': True, 'msg': f"{url} -> {code} in {int((time.time()-t0)*1000)}ms"}
    except Exception as e:
        return {'ok': False, 'msg': f"{url} failed: {e}"}

BUILTIN = {
    'add task': sk_task_add,
    'list tasks': sk_task_list,
    'message': sk_agent_message,
    'checklog': sk_vps_diagnostic,
    'check website': sk_web_check,
}

ROUTES = {
    'add task X [urgent]': 'Add task to queue',
    'list tasks': 'Show pending tasks',
    'message <agent> <text>': 'Send message to agent log',
    'checklog': 'VPS diagnostic',
    'check website <url>': 'Website health check',
}

# ---------------- agent skill manifests ----------------

def load_agent_skills():
    """Each agent drops <agent>.json in SKILLDIR: {"skills": {"name": "desc"}}"""
    out = {}
    with lock:
        for f in os.listdir(SKILLDIR):
            if f.endswith('.json'):
                agent = f[:-5]
                try:
                    out[agent] = json.load(open(os.path.join(SKILLDIR, f))).get('skills', {})
                except Exception:
                    out[agent] = {}
    return out

def dispatch(agent, skill, args, caller='soul'):
    r = hive_post('/hive/message', {
        'from': caller, 'to': agent, 'type': 'task_assign',
        'text': args, 'meta': {'skill': skill, 'task_id': uuid.uuid4().hex[:8]}})
    return {'ok': True, 'msg': f"task '{skill}' assigned to {agent} ({r['id']})", 'route': 'agent'}

def route(prompt, caller='soul'):
    p = prompt.strip()
    low = p.lower()
    # agent skill invocation: "<agent> <skill> <args...>" or "ask <agent> to <skill> <args>"
    agents = load_agent_skills()
    m = re.match(r'(?:ask\s+)?(\w+)\s+(?:to\s+)?(\w[\w-]*)\s*(.*)', p, re.S)
    if m and m.group(1) in agents and m.group(2) in agents[m.group(1)]:
        return dispatch(m.group(1), m.group(2), m.group(3), caller)
    # built-ins, longest-prefix match
    for k in sorted(BUILTIN, key=len, reverse=True):
        if low.startswith(k):
            return {**BUILTIN[k](args=p[len(k):]), 'route': 'builtin'}
    return {'ok': False, 'msg': 'unknown command. routes: ' + ', '.join(ROUTES) +
            (' | agents: ' + ', '.join(f"{a}({','.join(s)})" for a, s in agents.items()) if agents else '')}


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
        if p == '/soul/status':
            agents = load_agent_skills()
            self._json({'status': 'running', 'uptime': time.time() - START,
                        'skills': list(ROUTES), 'agents': {a: list(s) for a, s in agents.items()}})
        elif p == '/soul/routes':
            if not _authed(self):
                self._json({'error': 'unauthorised'}, 401); return
            r = dict(ROUTES)
            for a, s in load_agent_skills().items():
                for sk, desc in s.items():
                    r[f'{a} {sk}'] = desc
            self._json({'commands': r})
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
        if p == '/soul/task':
            prompt = str(body.get('prompt', ''))[:50000]
            if not prompt:
                self._json({'ok': False, 'msg': 'prompt required'}, 400); return
            caller = str(body.get('from', 'soul'))[:64]
            self._json(route(prompt, caller))
        elif p == '/soul/register':
            agent = re.sub(r'[^a-zA-Z0-9_-]', '', str(body.get('agent', '')))[:64]
            skills = body.get('skills')
            if not agent or not isinstance(skills, dict):
                self._json({'ok': False, 'msg': 'agent + skills{ name: desc } required'}, 400); return
            with lock:
                with open(os.path.join(SKILLDIR, agent + '.json'), 'w') as f:
                    json.dump({'agent': agent, 'skills': skills, 'ts': time.time()}, f)
            self._json({'ok': True, 'msg': f'{agent} registered with {len(skills)} skills'})
        else:
            self._json({'error': 'not found'}, 404)

if __name__ == '__main__':
    print(f'SOUL on :{PORT}')
    HTTPServer((BIND, PORT), H).serve_forever()
