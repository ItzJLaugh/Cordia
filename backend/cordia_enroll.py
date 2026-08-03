#!/usr/bin/env python3
"""Cordia device enrollment — mints per-employee Tailscale auth keys via the
Tailscale API after the employee proves their cordiacode.com email.

Flow: employee app verifies email via cordia_auth (2FA code), then POSTs the
resulting session token here. We mint a short-lived, pre-authorized, tagged,
ephemeral=false auth key scoped to tag:employee and return it. The app runs
`tailscale up --auth-key=<key> --hostname=<derived>` and the device appears in
the tailnet owned by that employee's enrollment record.

Config (in /etc/cordia/cordia.env):
  TS_API_KEY   — tailnet API access token (tskey-api-...)
  TS_TAILNET   — tailnet name (e.g. tail1cc9c1.ts.net or the org name)
Keys expire after TS_KEY_TTL seconds (default 15 min) so an unused key can't
be replayed later.
"""
import json, os, time, threading, urllib.request, base64, re, sys

sys.path.insert(0, '/opt/cordia/backend')
import cordia_auth as auth
import psycopg2

lock = threading.RLock()
TS_API_KEY = os.environ.get('TS_API_KEY', '')
TS_TAILNET = os.environ.get('TS_TAILNET', '')
TS_KEY_TTL = int(os.environ.get('TS_KEY_TTL', '900'))  # 15 min
TAGS = ['tag:employee']

def _api(path, method='GET', body=None):
    """Minimal Tailscale v2 API client, stdlib only."""
    if not (TS_API_KEY and TS_TAILNET):
        raise RuntimeError('TS_API_KEY/TS_TAILNET not configured')
    req = urllib.request.Request(
        f'https://api.tailscale.com/api/v2/tailnet/{TS_TAILNET}{path}',
        data=json.dumps(body).encode() if body is not None else None,
        method=method,
        headers={'Authorization': 'Basic ' + base64.b64encode(f'{TS_API_KEY}:'.encode()).decode(),
                 'Content-Type': 'application/json'})
    return json.loads(urllib.request.urlopen(req, timeout=20).read())

def _conn():
    return psycopg2.connect(os.environ.get('CORDIA_PG_DSN', ''))

def init():
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS devices(
          id TEXT PRIMARY KEY,
          email TEXT NOT NULL,
          hostname TEXT NOT NULL,
          key_id TEXT NOT NULL,
          created DOUBLE PRECISION NOT NULL,
          revoked BOOLEAN NOT NULL DEFAULT FALSE
        );''')

def _hostname_for(email):
    local = re.sub(r'[^a-z0-9-]', '-', email.split('@')[0].lower()).strip('-') or 'employee'
    return f'cordia-{local}'

def enroll(token):
    """Verify session → mint tagged auth key → record device. Returns dict for the app."""
    me = auth.whoami(token)
    if not me:
        return None, 'sign in required'
    if not me['email'].endswith('@cordiacode.com'):
        return None, 'cordiacode.com email required'
    hostname = _hostname_for(me['email'])
    caps = {'capabilities': {'createDevices': {'reusable': False, 'ephemeral': False,
            'preauthorized': True, 'tags': TAGS}}, 'expirySeconds': TS_KEY_TTL}
    r = _api('/keys', 'POST', caps)
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('INSERT INTO devices VALUES(%s,%s,%s,%s,%s,FALSE)',
                    (r['id'], me['email'], hostname, r['id'], time.time()))
    return {'auth_key': r['key'], 'hostname': hostname,
            'tailnet': TS_TAILNET, 'expires_in': TS_KEY_TTL}, None

def list_devices(email=None):
    with lock, _conn() as c, c.cursor() as cur:
        if email:
            cur.execute('SELECT id,email,hostname,created,revoked FROM devices WHERE email=%s ORDER BY created DESC', (email,))
        else:
            cur.execute('SELECT id,email,hostname,created,revoked FROM devices ORDER BY created DESC')
        return [{'id': r[0], 'email': r[1], 'hostname': r[2],
                 'created': r[3], 'revoked': r[4]} for r in cur.fetchall()]

def revoke(device_id):
    """Mark revoked locally + delete the device from the tailnet."""
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('UPDATE devices SET revoked=TRUE WHERE id=%s', (device_id,))
    try:
        _api(f'/devices/{device_id}', 'DELETE')
    except Exception:
        pass  # device may not exist yet (key minted but never used)

init()
