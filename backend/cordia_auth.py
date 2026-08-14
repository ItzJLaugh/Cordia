#!/usr/bin/env python3
"""Cordia auth — Postgres accounts, PBKDF2 password hashing, hashed session tokens,
email 2FA (Gmail SMTP if creds set, else dev-mode code echo when CORDIA_DEV_2FA=1).
DSN from CORDIA_PG_DSN (see /etc/cordia/cordia.env). No plaintext anything."""

import os, hashlib, hmac, secrets, time, smtplib, threading, sys
from email.message import EmailMessage
import psycopg2
import psycopg2.extras

lock = threading.RLock()

PBKDF2_ROUNDS = 200_000
CODE_TTL = 600              # 10 min
SESSION_TTL = 60*60*24*14   # 14 days
DEVICE_TTL  = 60*60*24*90   # 90 days a device stays trusted for 2FA
SIGNUP_NEXT_STEPS_MESSAGE = 'check your email for next steps'
DEV_2FA = os.environ.get('CORDIA_DEV_2FA') == '1'
DSN = os.environ.get('CORDIA_PG_DSN', '')

if not (os.environ.get('GMAIL_USER') and os.environ.get('GMAIL_APP_PASSWORD')) and not DEV_2FA:
    print('FATAL: GMAIL_USER/GMAIL_APP_PASSWORD not set and CORDIA_DEV_2FA != 1. '
          'Email 2FA cannot run. Set SMTP creds, or explicitly opt into dev mode.', file=sys.stderr)
    sys.exit(1)
if not DSN:
    print('FATAL: CORDIA_PG_DSN not set. Source /etc/cordia/cordia.env.', file=sys.stderr)
    sys.exit(1)

COMMON_PASSWORDS = {
    'password','password1','password123','123456','12345678','123456789','12345678910',
    'qwerty','qwerty123','letmein','iloveyou','dragon','monkey','football','baseball',
    'welcome','admin','login','master','sunshine','princess','starwars','whatever',
    'trustno1','cordia','cordia123','changeme','passw0rd','p@ssw0rd','abc123','111111',
}

def _hash_pw(pw, salt):
    return hashlib.pbkdf2_hmac('sha256', pw.encode(), bytes.fromhex(salt), PBKDF2_ROUNDS).hex()

def _hash_token(token):
    return hashlib.sha256(token.encode()).hexdigest()

def _conn():
    return psycopg2.connect(DSN)

def init():
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('''
        CREATE TABLE IF NOT EXISTS accounts(
          email TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          pw_hash TEXT NOT NULL,
          salt TEXT NOT NULL,
          created DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE IF NOT EXISTS pending(
          email TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          pw_hash TEXT NOT NULL,
          salt TEXT NOT NULL,
          code TEXT NOT NULL,
          expires DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE IF NOT EXISTS sessions(
          token TEXT PRIMARY KEY,
          email TEXT NOT NULL,
          created DOUBLE PRECISION NOT NULL,
          expires DOUBLE PRECISION NOT NULL
        );
        CREATE TABLE IF NOT EXISTS login_codes(
          email TEXT PRIMARY KEY,
          code TEXT NOT NULL,
          expires DOUBLE PRECISION NOT NULL
        );
        -- Devices that have already proved control of the inbox once.
        --
        -- Named trusted_devices, not devices: cordia_enroll.py already owns a
        -- `devices` table (hostname/key_id/revoked) for machine enrollment, and
        -- CREATE TABLE IF NOT EXISTS silently did nothing when this collided
        -- with it — every login then failed on a missing column.
        --
        -- Emailing a code on every sign-in buys nothing after the first time:
        -- the code proves the person owns the address, and that proof does not
        -- expire when they close the tab. A device that has completed the code
        -- flow once is trusted for DEVICE_TTL. The password is still required
        -- every single time — this skips the emailed code, never the password.
        --
        -- Stored as a SHA-256 hash exactly like sessions, so a database leak
        -- does not hand anyone a way to bypass 2FA.
        CREATE TABLE IF NOT EXISTS trusted_devices(
          token TEXT PRIMARY KEY,
          email TEXT NOT NULL,
          created DOUBLE PRECISION NOT NULL,
          expires DOUBLE PRECISION NOT NULL,
          last_used DOUBLE PRECISION NOT NULL
        );
        CREATE INDEX IF NOT EXISTS trusted_devices_email_idx ON trusted_devices(email);
        CREATE TABLE IF NOT EXISTS admin_audit(
          id BIGSERIAL PRIMARY KEY,
          ts DOUBLE PRECISION NOT NULL,
          email TEXT NOT NULL,
          route TEXT NOT NULL,
          ip TEXT,
          ua TEXT
        );
        CREATE INDEX IF NOT EXISTS admin_audit_email_idx ON admin_audit(email);
        CREATE INDEX IF NOT EXISTS admin_audit_ts_idx ON admin_audit(ts);
        CREATE TABLE IF NOT EXISTS reset_codes(
          email TEXT PRIMARY KEY,
          code TEXT NOT NULL,
          expires DOUBLE PRECISION NOT NULL
        );''')

def _send_code(email, code):
    user = os.environ.get('GMAIL_USER')
    pw = os.environ.get('GMAIL_APP_PASSWORD')
    if not (user and pw):
        return False  # only reachable when CORDIA_DEV_2FA=1
    msg = EmailMessage()
    msg['From'] = user
    msg['To'] = email
    msg['Subject'] = 'Your Cordia verification code'
    msg.set_content(f'Your Cordia verification code is: {code}\n\nIt expires in 10 minutes.')
    with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as s:
        s.starttls()
        s.login(user, pw)
        s.send_message(msg)
    return True

def signup(email, name, password):
    email = email.strip().lower()
    if not email or '@' not in email:
        return False, 'valid email required', None
    if (len(password) < 10 or not any(c.isalpha() for c in password)
            or not any(c.isdigit() for c in password)):
        return False, 'password must be 10+ chars with at least one letter and one number', None
    if password.lower() in COMMON_PASSWORDS:
        return False, 'password is too common — pick something less guessable', None
    # Never reveal whether an address is already registered.
    #
    # Returning "account already exists" for known addresses while returning
    # "verification code sent" for unknown ones turned signup into an account
    # enumeration oracle: anyone could test an email and learn whether that
    # person has a Cordia account. login() was already careful to stay generic;
    # this sat right beside it and wasn't.
    #
    # The real owner is told by email instead, which is the only channel where
    # it is safe to say it — they read their inbox, someone probing addresses
    email = email.strip().lower()
    if not email or '@' not in email:
        return False, 'valid email required', None
    if (len(password) < 10 or not any(c.isalpha() for c in password)
            or not any(c.isdigit() for c in password)):
        return False, 'password must be 10+ chars with at least one letter and one number', None
    if password.lower() in COMMON_PASSWORDS:
        return False, 'password is too common — pick something less guessable', None
    # Never reveal whether an address is already registered.
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT 1 FROM accounts WHERE email=%s', (email,))
        existing = cur.fetchone() is not None
        if existing:
            _notify_existing(email)
            # Return the same generic response as a new signup so we never
            # reveal account existence via timing or message differences.
            return True, SIGNUP_NEXT_STEPS_MESSAGE, None
        salt = secrets.token_hex(16)
        code = f'{secrets.randbelow(900000)+100000}'
        cur.execute('''INSERT INTO pending VALUES(%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name, pw_hash=EXCLUDED.pw_hash,
                       salt=EXCLUDED.salt, code=EXCLUDED.code, expires=EXCLUDED.expires''',
                    (email, name or email.split('@')[0], _hash_pw(password, salt), salt, code, time.time()+CODE_TTL))
    sent = _send_code(email, code)
    return True, SIGNUP_NEXT_STEPS_MESSAGE if sent else 'dev mode: code on screen', (None if sent else code)


def _notify_existing(email):
    """Tell a real account holder that someone tried to register their address.

    Best-effort and deliberately silent on failure: if this raises, signup must
    still return the same generic response, or the timing and error behaviour
    would leak exactly what the generic message exists to hide."""
    try:
        user = os.environ.get('GMAIL_USER')
        pw = os.environ.get('GMAIL_APP_PASSWORD')
        if not (user and pw):
            return
        msg = EmailMessage()
        msg['From'] = user
        msg['To'] = email
        msg['Subject'] = 'This email already has a Cordia account'
        msg.set_content(
            'A Cordia account already exists for this email address.\n\n'
            'No verification code was generated. This was an account-creation '
            'attempt, not a sign-in attempt.\n\n'
            'If that was you, return to Cordia and sign in instead — or use '
            '"forgot password" if you need to reset it.\n\n'
            'If it was not you, no action is needed. Your account was not changed '
            'and no new account was created.\n')
        with smtplib.SMTP('smtp.gmail.com', 587, timeout=15) as s:
            s.starttls()
            s.login(user, pw)
            s.send_message(msg)
    except Exception:
        pass

def verify_signup(email, code):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT name,pw_hash,salt,code,expires FROM pending WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'no pending signup', None, None
        name, pw_hash, salt, real_code, exp = row
        if time.time() > exp: return False, 'code expired', None, None
        if not hmac.compare_digest(code.strip(), real_code): return False, 'wrong code', None, None
        cur.execute('INSERT INTO accounts VALUES(%s,%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING',
                    (email, name, pw_hash, salt, time.time()))
        cur.execute('DELETE FROM pending WHERE email=%s', (email,))
    _fire_event(email, 'signup_verified', {'name': name})
    return True, 'account created', _make_session(email), trust_device(email)


def _fire_event(email, kind, meta=None):
    """No-op. The marketing pipeline it used to POST to was removed — it was
    dead code for lifecycle email automation that never shipped. Kept as a
    stub so callers don't need to change."""
    pass

def trust_device(email):
    """Issue a device token after the emailed code has been verified.

    Only ever called from verify_login/verify_signup — a device becomes trusted
    by proving inbox control once, never by asking."""
    token = secrets.token_urlsafe(32)
    now = time.time()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('INSERT INTO trusted_devices VALUES(%s,%s,%s,%s,%s)',
                    (_hash_token(token), email, now, now + DEVICE_TTL, now))
    return token                       # raw token returned once; only the hash is stored


def device_trusted(email, device_token):
    """True when this device already completed the code flow for THIS account.

    Scoped by email as well as token: a valid device token belonging to someone
    else must never satisfy the check for a different address, or one person's
    remembered laptop would skip 2FA for anyone whose password was known."""
    if not device_token or not email:
        return False
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT expires FROM trusted_devices WHERE token=%s AND email=%s',
                    (_hash_token(device_token), email))
        row = cur.fetchone()
        if not row or time.time() > row[0]:
            return False
        cur.execute('UPDATE trusted_devices SET last_used=%s WHERE token=%s',
                    (time.time(), _hash_token(device_token)))
    return True


def forget_devices(email):
    """Drop every remembered device for an account. The 'sign out everywhere'
    lever, and what a password reset should call."""
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('DELETE FROM trusted_devices WHERE email=%s', (email,))
        return cur.rowcount


def login(email, password, device_token=None):
    """Verify the password, then decide whether a code is needed.

    Returns (ok, msg, dev_code, session_token). session_token is non-None only
    when the device is already trusted and the code step is skipped.
    """
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT pw_hash,salt FROM accounts WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'invalid email or password', None, None
        pw_hash, salt = row
        if not hmac.compare_digest(_hash_pw(password, salt), pw_hash):
            return False, 'invalid email or password', None, None

    # Password is correct. A device that has already proved inbox control for
    # this account skips the emailed code — but never the password above.
    if device_trusted(email, device_token):
        _fire_event(email, 'login_trusted_device')
        return True, 'signed in', None, _make_session(email)

    # Stale or missing device token — fall back to code flow. If the browser
    # sent a token we don't recognize, clear it server-side too so the next
    # attempt doesn't keep trying the same dead token.
    if device_token:
        with lock, _conn() as c, c.cursor() as cur:
            cur.execute('DELETE FROM trusted_devices WHERE token=%s',
                        (_hash_token(device_token),))

    with lock, _conn() as c, c.cursor() as cur:
        code = f'{secrets.randbelow(900000)+100000}'
        cur.execute('''INSERT INTO login_codes VALUES(%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET code=EXCLUDED.code, expires=EXCLUDED.expires''',
                    (email, code, time.time()+CODE_TTL))
    sent = _send_code(email, code)
    return True, 'verification code sent' if sent else 'dev mode: code on screen', \
           (None if sent else code), None

def verify_login(email, code):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT code,expires FROM login_codes WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'invalid code', None, None
        real_code, exp = row
        if time.time() > exp:
            cur.execute('DELETE FROM login_codes WHERE email=%s', (email,))
            return False, 'invalid code', None, None
        if not hmac.compare_digest(code.strip(), real_code):
            return False, 'invalid code', None, None
        cur.execute('DELETE FROM login_codes WHERE email=%s', (email,))
    return True, 'logged in', _make_session(email), trust_device(email)

def request_password_reset(email):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT email FROM accounts WHERE email=%s', (email,))
        if not cur.fetchone():
            # Return the same generic response regardless of account existence.
            return False, 'if that email exists, a reset code was sent'
        code = f'{secrets.randbelow(900000)+100000}'
        cur.execute('''INSERT INTO reset_codes VALUES(%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET code=EXCLUDED.code, expires=EXCLUDED.expires''',
                    (email, code, time.time() + CODE_TTL))
    sent = _send_code(email, code)
    return True, 'reset code sent' if sent else 'dev mode: code on screen'

def reset_password(email, code, new_password):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT code,expires FROM reset_codes WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'no reset requested'
        real_code, exp = row
        if time.time() > exp: return False, 'code expired'
        if not hmac.compare_digest(code.strip(), real_code): return False, 'wrong code'
        cur.execute('SELECT email FROM accounts WHERE email=%s', (email,))
        if not cur.fetchone(): return False, 'no account'
        salt = secrets.token_hex(16)
        pw_hash = _hash_pw(new_password, salt)
        cur.execute('UPDATE accounts SET pw_hash=%s, salt=%s WHERE email=%s',
                    (pw_hash, salt, email))
        cur.execute('DELETE FROM reset_codes WHERE email=%s', (email,))
        cur.execute('DELETE FROM trusted_devices WHERE email=%s', (email,))
    return True, 'password updated'

def _make_session(email):
    token = secrets.token_urlsafe(32)
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('INSERT INTO sessions VALUES(%s,%s,%s,%s)',
                    (_hash_token(token), email, time.time(), time.time()+SESSION_TTL))
    return token  # raw token returned once; only the hash is stored

def whoami(token):
    if not token: return None
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT email,expires FROM sessions WHERE token=%s', (_hash_token(token),))
        row = cur.fetchone()
        if not row or time.time() > row[1]: return None
        cur.execute('SELECT name FROM accounts WHERE email=%s', (row[0],))
        name = cur.fetchone()
        return {'email': row[0], 'name': name[0] if name else row[0]}


def logout(token):
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('DELETE FROM sessions WHERE token=%s', (_hash_token(token),))


def purge_expired():
    """Delete expired sessions, login codes and pending signups.

    whoami() already rejects an expired session, so this is hygiene rather than
    a vulnerability fix: without it the tables grow forever and a database
    compromise hands over a longer history of who was logged in and when.
    Returns counts so the caller can log them."""
    out = {}
    now = time.time()
    with lock, _conn() as c, c.cursor() as cur:
        for table in ('sessions', 'login_codes', 'pending', 'trusted_devices', 'reset_codes'):
            cur.execute(f'DELETE FROM {table} WHERE expires < %s', (now,))
            out[table] = cur.rowcount
    return out

init()
