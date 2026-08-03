#!/usr/bin/env python3
"""Cordia paywall — entitlements + Hostinger Reach order verification.

Model: one `entitlements` table in Postgres. An entitlement grants `email`
access to `track` ('*' = all-access bundle). Sources: 'reach' (Hostinger
order), 'manual' (admin grant), 'free' (intro track promo).

Hostinger side: paid products/orders live in Hostinger Reach. When a customer
buys, Reach fires a webhook (or you paste the order id) containing the buyer
email + product SKU. SKU maps to track via SKU_TRACK below. Set
REACH_WEBHOOK_SECRET in cordia.env; webhook posts to /pay/reach-webhook with
header X-Reach-Secret equal to that value.

No payment card data ever touches this server — Hostinger is the merchant of
record. We only record that a grant exists.
"""
import hmac, os, re, sys, threading, time
import psycopg2

sys.path.insert(0, '/opt/cordia/backend')

lock = threading.RLock()

# Hostinger product SKU -> Cordia track id. Fill in when products exist in Reach.
SKU_TRACK = {
    # 'track-software': 'software',
    # 'track-legal': 'legal',
    # 'bundle-all': '*',
}
FREE_TRACKS = set()          # promo: tracks currently free ('software' while beta, e.g.)

def _conn():
    return psycopg2.connect(os.environ.get('CORDIA_PG_DSN', ''))

def init():
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS entitlements(
          id BIGSERIAL PRIMARY KEY,
          email TEXT NOT NULL,
          track TEXT NOT NULL,
          source TEXT NOT NULL,
          order_id TEXT,
          created DOUBLE PRECISION NOT NULL,
          UNIQUE(email, track)
        );''')

def grant(email, track, source, order_id=None):
    email = email.strip().lower()
    if not re.match(r'^[^@\s]+@[^@\s]+$', email):
        return False
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''INSERT INTO entitlements(email,track,source,order_id,created)
                       VALUES(%s,%s,%s,%s,%s) ON CONFLICT (email,track) DO NOTHING''',
                    (email, track, source, order_id, time.time()))
    return True

def entitled(email, track):
    if not email: return False
    if track in FREE_TRACKS: return True
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT 1 FROM entitlements WHERE email=%s AND (track=%s OR track=%s) LIMIT 1',
                    (email, track, '*'))
        return cur.fetchone() is not None

def my_entitlements(email):
    email = (email or '').strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT track,source,created FROM entitlements WHERE email=%s ORDER BY created DESC',
                    (email,))
        return [{'track': r[0], 'source': r[1], 'created': r[2]} for r in cur.fetchall()]

def handle_reach_webhook(headers, body):
    """Verify shared secret, extract email+SKU, grant. Returns (ok, msg)."""
    secret = os.environ.get('REACH_WEBHOOK_SECRET', '')
    if not secret:
        return False, 'webhook not configured'
    if not hmac.compare_digest(headers.get('X-Reach-Secret', ''), secret):
        return False, 'bad secret'
    email = str(body.get('email', '')).strip().lower()
    sku = str(body.get('sku', '')).strip()
    order = str(body.get('order_id', '')).strip()[:80]
    track = SKU_TRACK.get(sku)
    if not email or not track:
        return False, 'unknown sku or missing email'
    grant(email, track, 'reach', order)
    return True, f'granted {track} to {email}'

init()
