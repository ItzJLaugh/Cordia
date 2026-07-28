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
    with lock, _conn() as c, c.cursor() as cur:
        if cur.execute('SELECT 1 FROM accounts WHERE email=%s', (email,)) or cur.fetchone():
            return False, 'account already exists', None
        salt = secrets.token_hex(16)
        code = f'{secrets.randbelow(900000)+100000}'
        cur.execute('''INSERT INTO pending VALUES(%s,%s,%s,%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET name=EXCLUDED.name, pw_hash=EXCLUDED.pw_hash,
                       salt=EXCLUDED.salt, code=EXCLUDED.code, expires=EXCLUDED.expires''',
                    (email, name or email.split('@')[0], _hash_pw(password, salt), salt, code, time.time()+CODE_TTL))
    sent = _send_code(email, code)
    return True, 'verification code sent' if sent else 'dev mode: code on screen', (None if sent else code)

def verify_signup(email, code):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT name,pw_hash,salt,code,expires FROM pending WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'no pending signup', None
        name, pw_hash, salt, real_code, exp = row
        if time.time() > exp: return False, 'code expired', None
        if not hmac.compare_digest(code.strip(), real_code): return False, 'wrong code', None
        cur.execute('INSERT INTO accounts VALUES(%s,%s,%s,%s,%s) ON CONFLICT (email) DO NOTHING',
                    (email, name, pw_hash, salt, time.time()))
        cur.execute('DELETE FROM pending WHERE email=%s', (email,))
    return True, 'account created', _make_session(email)

def login(email, password):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT pw_hash,salt FROM accounts WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'invalid email or password', None
        pw_hash, salt = row
        if not hmac.compare_digest(_hash_pw(password, salt), pw_hash):
            return False, 'invalid email or password', None
        code = f'{secrets.randbelow(900000)+100000}'
        cur.execute('''INSERT INTO login_codes VALUES(%s,%s,%s)
                       ON CONFLICT (email) DO UPDATE SET code=EXCLUDED.code, expires=EXCLUDED.expires''',
                    (email, code, time.time()+CODE_TTL))
    sent = _send_code(email, code)
    return True, 'verification code sent' if sent else 'dev mode: code on screen', (None if sent else code)

def verify_login(email, code):
    email = email.strip().lower()
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute('SELECT code,expires FROM login_codes WHERE email=%s', (email,))
        row = cur.fetchone()
        if not row: return False, 'no pending login', None
        real_code, exp = row
        if time.time() > exp: return False, 'code expired', None
        if not hmac.compare_digest(code.strip(), real_code): return False, 'wrong code', None
        cur.execute('DELETE FROM login_codes WHERE email=%s', (email,))
    return True, 'logged in', _make_session(email)

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

init()
