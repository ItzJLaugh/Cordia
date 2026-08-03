#!/usr/bin/env python3
"""Surveyor persistence. Postgres only — the same database as accounts.

Keyed by ``email`` to match ``accounts.email`` (the existing primary key in
cordia_auth), so a Surveyor profile sits beside the account, the entitlement and
the exam score rather than in a second database that has to be reconciled later.

Connections are opened per call, never shared, which is what makes the threaded
server safe. Everything is written with %s placeholders and parameter binding —
no string interpolation into SQL anywhere in this module.
"""

from __future__ import annotations

import json
import os
import threading
import uuid

_lock = threading.RLock()

_JSON_COLUMNS = {
    "signals", "scores", "evidence", "identifiers", "adaptation",
    "meta", "definition", "theme", "payload",
}


def _conn():
    import psycopg2
    dsn = os.environ.get("CORDIA_PG_DSN", "")
    if not dsn:
        raise RuntimeError("CORDIA_PG_DSN not set. Source /etc/cordia/cordia.env.")
    return psycopg2.connect(dsn)


def _J(obj):
    import psycopg2.extras
    return psycopg2.extras.Json(obj, dumps=json.dumps)


SCHEMA = """
CREATE TABLE IF NOT EXISTS surveyor_conversations(
    id          TEXT PRIMARY KEY,
    email       TEXT        NOT NULL,
    kind        TEXT        NOT NULL DEFAULT 'surveyor',
    created     TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated     TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_conv_email_idx ON surveyor_conversations(email);

CREATE TABLE IF NOT EXISTS surveyor_messages(
    id              BIGSERIAL PRIMARY KEY,
    conversation_id TEXT        NOT NULL REFERENCES surveyor_conversations(id) ON DELETE CASCADE,
    role            TEXT        NOT NULL,
    content         TEXT        NOT NULL,
    meta            JSONB,
    created         TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_msg_conv_idx ON surveyor_messages(conversation_id, id);

CREATE TABLE IF NOT EXISTS surveyor_profiles(
    email              TEXT PRIMARY KEY,
    signals            JSONB   NOT NULL DEFAULT '{}'::jsonb,
    scores             JSONB   NOT NULL DEFAULT '{}'::jsonb,
    evidence           JSONB   NOT NULL DEFAULT '[]'::jsonb,
    identifiers        JSONB   NOT NULL DEFAULT '[]'::jsonb,
    adaptation         JSONB   NOT NULL DEFAULT '{}'::jsonb,
    confidence         REAL    NOT NULL DEFAULT 0,
    questions_answered INTEGER NOT NULL DEFAULT 0,
    simple_mode_forced BOOLEAN NOT NULL DEFAULT FALSE,
    created            TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated            TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS surveyor_interfaces(
    id          TEXT PRIMARY KEY,
    email       TEXT        NOT NULL,
    name        TEXT        NOT NULL,
    description TEXT,
    definition  JSONB       NOT NULL,
    theme       JSONB,
    archived    BOOLEAN     NOT NULL DEFAULT FALSE,
    created     TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated     TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_iface_email_idx ON surveyor_interfaces(email, archived);

CREATE TABLE IF NOT EXISTS surveyor_runs(
    id           BIGSERIAL PRIMARY KEY,
    interface_id TEXT        NOT NULL REFERENCES surveyor_interfaces(id) ON DELETE CASCADE,
    email        TEXT        NOT NULL,
    input        TEXT,
    output       TEXT,
    meta         JSONB,
    created      TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_runs_iface_idx ON surveyor_runs(interface_id);

CREATE TABLE IF NOT EXISTS surveyor_events(
    id         BIGSERIAL PRIMARY KEY,
    email      TEXT        NOT NULL,
    event_type TEXT        NOT NULL,
    payload    JSONB,
    created    TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_events_email_idx ON surveyor_events(email, created);
"""


def init_schema() -> None:
    """Create tables if absent. Safe to run repeatedly, called at startup."""
    with _lock, _conn() as c, c.cursor() as cur:
        cur.execute(SCHEMA)


# ------------------------------------------------------------------ events

def log_event(email, event_type, payload=None) -> None:
    """Best-effort. Analytics must never break a user's request."""
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO surveyor_events(email, event_type, payload) VALUES (%s,%s,%s)",
                (email, event_type, _J(payload or {})))
    except Exception:
        pass


def events(email, limit=100) -> list:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT event_type, payload, created FROM surveyor_events "
                    "WHERE email=%s ORDER BY id DESC LIMIT %s", (email, limit))
        return [{"event_type": r[0], "payload": r[1], "created": str(r[2])}
                for r in cur.fetchall()]


# ----------------------------------------------------------------- profile

_PROFILE_COLS = ("signals", "scores", "evidence", "identifiers", "adaptation",
                 "confidence", "questions_answered", "simple_mode_forced")


def get_profile(email) -> dict | None:
    with _conn() as c, c.cursor() as cur:
        cur.execute(f"SELECT {', '.join(_PROFILE_COLS)} FROM surveyor_profiles "
                    "WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row:
        return None
    return dict(zip(_PROFILE_COLS, row))


def save_profile(email, profile) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_profiles
                (email, signals, scores, evidence, identifiers, adaptation,
                 confidence, questions_answered, simple_mode_forced)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                signals=EXCLUDED.signals,
                scores=EXCLUDED.scores,
                evidence=EXCLUDED.evidence,
                identifiers=EXCLUDED.identifiers,
                adaptation=EXCLUDED.adaptation,
                confidence=EXCLUDED.confidence,
                questions_answered=EXCLUDED.questions_answered,
                simple_mode_forced=EXCLUDED.simple_mode_forced,
                updated=(now() AT TIME ZONE 'utc')
        """, (email,
              _J(profile.get("signals") or {}),
              _J(profile.get("scores") or {}),
              _J(profile.get("evidence") or []),
              _J(profile.get("identifiers") or []),
              _J(profile.get("adaptation") or {}),
              float(profile.get("confidence") or 0.0),
              int(profile.get("questions_answered") or 0),
              bool(profile.get("simple_mode_forced"))))


def set_simple_mode(email, forced: bool) -> None:
    """Per-user kill switch. Works without a restart, unlike the env var."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_profiles(email, simple_mode_forced)
            VALUES (%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                simple_mode_forced=EXCLUDED.simple_mode_forced,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, bool(forced)))


# ------------------------------------------------------------ conversation

def open_conversation(email) -> str:
    """Return the person's live conversation, creating one on first use."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id FROM surveyor_conversations WHERE email=%s "
                    "ORDER BY created DESC LIMIT 1", (email,))
        row = cur.fetchone()
        if row:
            return row[0]
        cid = uuid.uuid4().hex
        cur.execute("INSERT INTO surveyor_conversations(id, email) VALUES (%s,%s)",
                    (cid, email))
        return cid


def add_message(conversation_id, role, content, meta=None) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO surveyor_messages(conversation_id, role, content, meta) "
                    "VALUES (%s,%s,%s,%s)",
                    (conversation_id, role, content, _J(meta or {})))
        cur.execute("UPDATE surveyor_conversations SET updated=(now() AT TIME ZONE 'utc') "
                    "WHERE id=%s", (conversation_id,))


def messages(conversation_id, limit=200) -> list:
    """meta is included deliberately: question_strategy.asked_signals and the
    'already closed' check both read it, and without it they silently fall back
    to fuzzy text matching against the question bank."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT role, content, created, meta FROM surveyor_messages "
                    "WHERE conversation_id=%s ORDER BY id ASC LIMIT %s",
                    (conversation_id, limit))
        return [{"role": r[0], "content": r[1], "created": str(r[2]), "meta": r[3] or {}}
                for r in cur.fetchall()]


# ------------------------------------------------------------- interfaces

def save_interface(email, iface_id, name, description, definition, theme=None) -> str:
    iface_id = iface_id or uuid.uuid4().hex
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_interfaces(id, email, name, description, definition, theme)
            VALUES (%s,%s,%s,%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET
                name=EXCLUDED.name,
                description=EXCLUDED.description,
                definition=EXCLUDED.definition,
                theme=EXCLUDED.theme,
                updated=(now() AT TIME ZONE 'utc')
            WHERE surveyor_interfaces.email = EXCLUDED.email
        """, (iface_id, email, name, description, _J(definition), _J(theme or {})))
    return iface_id


def list_interfaces(email, include_archived=False) -> list:
    sql = ("SELECT id, name, description, definition, archived, updated "
           "FROM surveyor_interfaces WHERE email=%s")
    if not include_archived:
        sql += " AND archived=FALSE"
    sql += " ORDER BY updated DESC"
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql, (email,))
        rows = cur.fetchall()
    return [{"id": r[0], "name": r[1], "description": r[2], "definition": r[3],
             "archived": r[4], "updated": str(r[5])} for r in rows]


def get_interface(email, iface_id) -> dict | None:
    """Always scoped by email — an interface id must never be enough to read
    someone else's workspace."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, name, description, definition, theme, archived, updated "
                    "FROM surveyor_interfaces WHERE id=%s AND email=%s", (iface_id, email))
        r = cur.fetchone()
    if not r:
        return None
    return {"id": r[0], "name": r[1], "description": r[2], "definition": r[3],
            "theme": r[4], "archived": r[5], "updated": str(r[6])}


def archive_interface(email, iface_id, archived=True) -> bool:
    with _conn() as c, c.cursor() as cur:
        cur.execute("UPDATE surveyor_interfaces SET archived=%s, "
                    "updated=(now() AT TIME ZONE 'utc') WHERE id=%s AND email=%s",
                    (bool(archived), iface_id, email))
        return cur.rowcount > 0


def export_answers() -> list:
    """Every survey exchange as flat rows, for phase-2 analysis.

    One row per user answer, carrying the question that prompted it, the signal
    it was meant to fill, and whether the person tapped a suggested answer or
    typed freely. That last flag matters: tapped answers are ground truth, typed
    ones are what a future extractor has to learn to read, and mixing them would
    contaminate any training set built from this.
    """
    sql = """
        SELECT c.email, m.conversation_id, m.id, m.role, m.content, m.meta, m.created,
               LAG(m.content) OVER (PARTITION BY m.conversation_id ORDER BY m.id) AS prompted_by,
               LAG(m.meta)    OVER (PARTITION BY m.conversation_id ORDER BY m.id) AS prompt_meta
        FROM surveyor_messages m
        JOIN surveyor_conversations c ON c.id = m.conversation_id
        ORDER BY m.conversation_id, m.id
    """
    with _conn() as c, c.cursor() as cur:
        cur.execute(sql)
        rows = cur.fetchall()

    out = []
    for email, cid, mid, role, content, meta, created, prev, prev_meta in rows:
        if role != "user":
            continue
        out.append({
            "email": email,
            "conversation_id": cid,
            "message_id": mid,
            "question": prev,
            "signal": (prev_meta or {}).get("signal"),
            "answer": content,
            "tapped_suggestion": bool((meta or {}).get("choice")),
            "created": str(created),
        })
    return out


def record_recommendation(email, definition) -> bool:
    """Log what Cordia recommended into the existing 6S ``outcomes`` table.

    That table was built for exactly this — recommendation_given alongside an
    outcome_worked flag — and has never held a row. Writing here means that when
    someone later reports whether their workspace actually helped, the answer
    lands next to what was recommended and becomes analysable.

    ``outcomes.submission_id`` is NOT NULL with a foreign key to ``submissions``,
    so this can only attach to a learner who has an exam submission on record.
    Someone who has only talked to Surveyor has nothing to attach to yet, and we
    return False rather than inventing a submission to satisfy the constraint.
    """
    try:
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT id FROM submissions WHERE user_ref=%s "
                        "ORDER BY id DESC LIMIT 1", (email,))
            row = cur.fetchone()
            if not row:
                return False
            cur.execute("INSERT INTO outcomes(submission_id, recommendation_given) "
                        "VALUES (%s,%s)", (row[0], _J(definition)))
        return True
    except Exception:
        return False


def add_run(interface_id, email, inp, out, meta=None) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("INSERT INTO surveyor_runs(interface_id, email, input, output, meta) "
                    "VALUES (%s,%s,%s,%s,%s)",
                    (interface_id, email, inp, out, _J(meta or {})))


def runs(email, limit=50) -> list:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT interface_id, input, output, created FROM surveyor_runs "
                    "WHERE email=%s ORDER BY id DESC LIMIT %s", (email, limit))
        return [{"interface_id": r[0], "input": r[1], "output": r[2], "created": str(r[3])}
                for r in cur.fetchall()]
