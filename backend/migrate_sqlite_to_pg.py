#!/usr/bin/env python3
"""One-shot migration: SQLite legacy DB -> Postgres. Idempotent (ON CONFLICT DO NOTHING)."""
import os, sqlite3, psycopg2

os.environ.setdefault('CORDIA_DEV_2FA', '1')
dsn = [l.split('=',1)[1].strip() for l in open('/etc/cordia/cordia.env') if l.startswith('CORDIA_PG_DSN=')][0]
os.environ['CORDIA_PG_DSN'] = dsn

import sys; sys.path.insert(0, '/opt/cordia/backend')
import cordia_auth  # ensures schema exists

sq = sqlite3.connect('/var/lib/cordia/db/cordia-sqlite-legacy.db')
pg = psycopg2.connect(dsn)
cur = pg.cursor()
for t in ('accounts','sessions','pending','login_codes'):
    try:
        rows = sq.execute(f'SELECT * FROM {t}').fetchall()
    except Exception:
        rows = []
    if rows:
        ph = ','.join(['%s']*len(rows[0]))
        cur.executemany(f'INSERT INTO {t} VALUES({ph}) ON CONFLICT DO NOTHING', rows)
    print(f'{t}: {len(rows)} rows migrated')
pg.commit()
for t in ('accounts','sessions','pending','login_codes'):
    cur.execute(f'SELECT COUNT(*) FROM {t}')
    print(f'pg {t}: {cur.fetchone()[0]}')
pg.close()
print('migration complete')
