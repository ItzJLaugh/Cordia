"""Lifecycle sequences and SQL segment builders."""
import sys, time

if hasattr(sys, 'path'):
    pass
sys.path.insert(0, '/opt/cordia/backend')
from cordia_pipeline import DSN, lock, _conn

SEGMENTS = {
    'all_active': '''
        SELECT email, name FROM mail_contacts
        WHERE COALESCE(updated, first_seen) > %s
        ORDER BY updated DESC NULLS LAST
    ''',
    'inactive_30d': '''
        SELECT email, name FROM mail_contacts
        WHERE COALESCE(updated, first_seen) < %s
          AND COALESCE(updated, first_seen) > %s
        ORDER BY updated DESC NULLS LAST
    ''',
    'paid_no_repeat': '''
        SELECT email, name FROM mail_contacts
        WHERE 'paying' = ANY(tags)
          AND cardinality(paid_tracks) <= 1
        ORDER BY updated DESC NULLS LAST
    ''',
    'exam_takers_low_score': '''
        SELECT email, name FROM mail_contacts
        WHERE 'exam_taker' = ANY(tags)
          AND exam_score IS NOT NULL AND exam_score < 70
        ORDER BY updated DESC NULLS LAST
    ''',
    'never_examined': '''
        SELECT email, name FROM mail_contacts
        WHERE NOT ('exam_taker' = ANY(tags) OR 'certified' = ANY(tags))
          AND first_seen < %s
        ORDER BY first_seen
    ''',
}


def fetch(segment, since=None, until=None, limit=500):
    sql = SEGMENTS.get(segment)
    if not sql: return []
    args = []
    if segment == 'all_active':
        args = [time.time() - 60*86400]
    elif segment == 'inactive_30d':
        args = [time.time() - 30*86400, time.time() - 180*86400]
    elif segment == 'never_examined':
        args = [time.time() - 7*86400]
    with lock, _conn() as c, c.cursor() as cur:
        cur.execute(sql + ' LIMIT %s', args + [limit])
        return [{'email': e, 'name': n} for e, n in cur.fetchall()]


# --- Lifecycle sequence spec: ordered list of (delay_seconds, kind) ---
# The orchestrator (cordia_pipeline) reads these to schedule.
SEQUENCES = {
    'welcome': [
        (0,          'welcome_1', 'welcome_1'),
        (3*86400,    'welcome_2', 'welcome_2'),
        (7*86400,    'welcome_3', 'welcome_3'),
    ],
    'onboarding_track': [
        (0,          'purchase_receipt', 'receipt'),
        (1*86400,    'onboarding_1',     'onboarding_1'),
        (3*86400,    'onboarding_2',     'onboarding_2'),
        (7*86400,    'onboarding_3',     'onboarding_3'),
        (14*86400,   'onboarding_4',     'onboarding_4'),
    ],
}
