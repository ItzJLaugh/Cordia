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
from copy import deepcopy

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

CREATE TABLE IF NOT EXISTS surveyor_approvals(
    id           TEXT PRIMARY KEY,
    run_id       TEXT NOT NULL,
    email        TEXT NOT NULL,
    step_id      TEXT NOT NULL,
    summary      TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'pending',
    approver     TEXT,
    note         TEXT,
    created      TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    decided      TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS surveyor_approvals_email_status_idx ON surveyor_approvals(email, status);

CREATE TABLE IF NOT EXISTS surveyor_events(
    id         BIGSERIAL PRIMARY KEY,
    email      TEXT        NOT NULL,
    event_type TEXT        NOT NULL,
    payload    JSONB,
    created    TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_events_email_idx ON surveyor_events(email, created);

CREATE TABLE IF NOT EXISTS surveyor_connector_preferences(
    email            TEXT PRIMARY KEY,
    connector_states JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated          TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS surveyor_artifacts(
    email    TEXT PRIMARY KEY,
    source   JSONB NOT NULL DEFAULT '{}'::jsonb,
    runtime  JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated  TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);

CREATE TABLE IF NOT EXISTS surveyor_secrets(
    secret_ref TEXT PRIMARY KEY,
    email      TEXT NOT NULL,
    connector  TEXT NOT NULL,
    ciphertext BYTEA NOT NULL,
    created    TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated    TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_secrets_email_connector_idx ON surveyor_secrets(email, connector);

CREATE TABLE IF NOT EXISTS surveyor_workspaces(
    id       TEXT PRIMARY KEY,
    email    TEXT NOT NULL,
    state    JSONB NOT NULL,
    created  TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated  TIMESTAMPTZ NOT NULL DEFAULT (now() AT TIME ZONE 'utc')
);
CREATE INDEX IF NOT EXISTS surveyor_workspaces_email_idx ON surveyor_workspaces(email, updated);

ALTER TABLE surveyor_runs ADD COLUMN IF NOT EXISTS idempotency_key TEXT;
CREATE UNIQUE INDEX IF NOT EXISTS surveyor_runs_owner_workspace_key_idx
ON surveyor_runs(email, interface_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;

-- Stage 2 and 3, added after the table already existed in production.
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS scenarios   JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS freeform    JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS intent_misses JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS tensions    JSONB NOT NULL DEFAULT '[]'::jsonb;
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS reliability JSONB NOT NULL DEFAULT '{}'::jsonb;
ALTER TABLE surveyor_profiles ADD COLUMN IF NOT EXISTS profile_calibration JSONB;
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


def record_registry_outcome(email, outcome) -> bool:
    """Persist bounded feedback without changing recommendation state."""
    if not isinstance(outcome, dict):
        return False
    record_id = outcome.get('record_id')
    result = outcome.get('outcome')
    from . import fde_registry
    if (not isinstance(record_id, str) or not fde_registry.describe(record_id)
            or result not in {'useful', 'not_useful'}):
        return False
    log_event(email, 'fde_registry_outcome_recorded', {
        'record_id': record_id, 'outcome': result,
    })
    return True


def events(email, limit=100) -> list:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT event_type, payload, created FROM surveyor_events "
                    "WHERE email=%s ORDER BY id DESC LIMIT %s", (email, limit))
        return [{"event_type": r[0], "payload": r[1], "created": str(r[2])}
                for r in cur.fetchall()]


# ----------------------------------------------------------------- profile

_PROFILE_COLS = ("signals", "scores", "evidence", "identifiers", "adaptation",
                 "scenarios", "freeform", "tensions", "reliability",
                 "intent_misses",
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
                 scenarios, freeform, tensions, reliability,
                 intent_misses, confidence, questions_answered, simple_mode_forced)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                signals=EXCLUDED.signals,
                scores=EXCLUDED.scores,
                evidence=EXCLUDED.evidence,
                identifiers=EXCLUDED.identifiers,
                adaptation=EXCLUDED.adaptation,
                scenarios=EXCLUDED.scenarios,
                freeform=EXCLUDED.freeform,
                tensions=EXCLUDED.tensions,
                reliability=EXCLUDED.reliability,
                intent_misses=EXCLUDED.intent_misses,
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
              _J(profile.get("scenarios") or {}),
              _J(profile.get("freeform") or {}),
              _J(profile.get("tensions") or []),
              _J(profile.get("reliability") or {}),
              _J(profile.get("intent_misses") or []),
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


def _save_profile_calibration(cursor, email: str, calibration: dict) -> None:
    cursor.execute("""
            INSERT INTO surveyor_profiles(email, profile_calibration)
            VALUES (%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                profile_calibration=EXCLUDED.profile_calibration,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, _J(calibration)))


def save_profile_calibration(email: str, calibration: dict) -> None:
    """Persist strict calibration beside the owner's existing Surveyor profile."""
    from . import profile_calibration
    validated = profile_calibration.validate_result(calibration)
    with _conn() as connection, connection.cursor() as cursor:
        _save_profile_calibration(cursor, email, validated)


def get_profile_calibration(email: str) -> dict | None:
    """Return a detached calibration for the named owner, if one exists."""
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT profile_calibration FROM surveyor_profiles WHERE email=%s",
                       (email,))
        row = cursor.fetchone()
    return deepcopy(row[0]) if row and isinstance(row[0], dict) else None


# --------------------------------------------------------- FDE artifacts

def get_connector_states(email: str) -> dict:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT connector_states FROM surveyor_connector_preferences WHERE email=%s",
                    (email,))
        row = cur.fetchone()
    return (row[0] or {}) if row else {}


def save_connector_states(email: str, states: dict) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_connector_preferences(email, connector_states)
            VALUES (%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                connector_states=EXCLUDED.connector_states,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, _J(states)))


def save_artifacts(email: str, bundle: dict) -> None:
    source = {k: v for k, v in (bundle or {}).items() if k.startswith("source/")}
    runtime = {k: v for k, v in (bundle or {}).items() if k.startswith("runtime/")}
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_artifacts(email, source, runtime)
            VALUES (%s,%s,%s)
            ON CONFLICT (email) DO UPDATE SET
                source=EXCLUDED.source,
                runtime=EXCLUDED.runtime,
                updated=(now() AT TIME ZONE 'utc')
        """, (email, _J(source), _J(runtime)))


def get_artifacts(email: str) -> dict | None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT source, runtime FROM surveyor_artifacts WHERE email=%s", (email,))
        row = cur.fetchone()
    if not row:
        return None
    return {**(row[0] or {}), **(row[1] or {})}


def save_secret(secret_ref: str, email: str, connector: str, ciphertext: bytes) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_secrets(secret_ref, email, connector, ciphertext)
            VALUES (%s,%s,%s,%s)
        """, (secret_ref, email, connector, bytes(ciphertext)))


def get_secret(email: str, connector: str) -> tuple[str, bytes] | None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            SELECT secret_ref, ciphertext FROM surveyor_secrets
            WHERE email=%s AND connector=%s ORDER BY created DESC LIMIT 1
        """, (email, connector))
        row = cur.fetchone()
    return (row[0], bytes(row[1])) if row else None


def save_workspace(email: str, workspace_id: str, state: dict) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""
            INSERT INTO surveyor_workspaces(id, email, state) VALUES (%s,%s,%s)
            ON CONFLICT (id) DO UPDATE SET state=EXCLUDED.state,
                updated=(now() AT TIME ZONE 'utc')
            WHERE surveyor_workspaces.email=EXCLUDED.email
        """, (workspace_id, email, _J(state)))


def _split_artifacts(bundle: dict) -> tuple[dict, dict]:
    source = {
        key: value
        for key, value in bundle.items()
        if key.startswith("source/")
    }
    runtime = {
        key: value
        for key, value in bundle.items()
        if key.startswith("runtime/")
    }
    return source, runtime


def _existing_initial_workspace(cursor, email: str) -> str | None:
    cursor.execute(
        "SELECT id FROM surveyor_interfaces "
        "WHERE email=%s AND archived=FALSE ORDER BY updated DESC LIMIT 1",
        (email,),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def _save_artifact_bundle(cursor, email: str, source: dict, runtime: dict) -> None:
    cursor.execute(
        "INSERT INTO surveyor_artifacts(email,source,runtime) VALUES(%s,%s,%s) "
        "ON CONFLICT(email) DO UPDATE SET source=EXCLUDED.source, "
        "runtime=EXCLUDED.runtime, updated=(now() AT TIME ZONE 'utc')",
        (email, _J(source), _J(runtime)),
    )


def _create_initial_workspace(cursor, email: str, prepared: dict) -> None:
    source, runtime = _split_artifacts(prepared["artifacts"])
    cursor.execute(
        "INSERT INTO surveyor_interfaces"
        "(id,email,name,description,definition,theme) "
        "VALUES(%s,%s,%s,%s,%s,%s)",
        (
            prepared["id"], email, prepared["name"], prepared["description"],
            _J(prepared["definition"]), _J({}),
        ),
    )
    cursor.execute(
        "INSERT INTO surveyor_workspaces(id,email,state) VALUES(%s,%s,%s)",
        (prepared["id"], email, _J(prepared["workspace"])),
    )
    _save_artifact_bundle(cursor, email, source, runtime)


def ensure_initial_workspace(email: str, prepared: dict) -> tuple[str, bool]:
    """Create one owner's first workspace atomically, or return the existing one."""
    with _lock, _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (email,))
        existing = _existing_initial_workspace(cursor, email)
        if existing:
            return existing, False
        _create_initial_workspace(cursor, email, prepared)
    return prepared["id"], True


def complete_profile_calibration(
    email: str, calibration: dict, prepared: dict, memory: str
) -> tuple[str, bool]:
    """Commit calibration, one workspace, and refreshed memory as one owner transaction."""
    from . import profile_calibration
    validated = profile_calibration.validate_result(calibration)
    if not isinstance(memory, str):
        raise ValueError("profile memory is invalid")
    with _lock, _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (email,))
        _save_profile_calibration(cursor, email, validated)
        existing = _existing_initial_workspace(cursor, email)
        if not existing:
            bundle = dict(prepared["artifacts"])
            bundle["source/memory.md"] = memory
            prepared = {**prepared, "artifacts": bundle}
            _create_initial_workspace(cursor, email, prepared)
            return prepared["id"], True
        cursor.execute(
            "SELECT source, runtime FROM surveyor_artifacts WHERE email=%s FOR UPDATE",
            (email,),
        )
        row = cursor.fetchone()
        source = dict(row[0] or {}) if row else {}
        runtime = dict(row[1] or {}) if row else {}
        source["source/memory.md"] = memory
        _save_artifact_bundle(cursor, email, source, runtime)
        return existing, False


def get_workspace(email: str, workspace_id: str) -> dict | None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT state FROM surveyor_workspaces WHERE id=%s AND email=%s",
                    (workspace_id, email))
        row = cur.fetchone()
    return row[0] if row else None


def get_run_by_idempotency(email: str, workspace_id: str, key: str) -> dict | None:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT meta FROM surveyor_runs WHERE email=%s AND interface_id=%s "
                       "AND idempotency_key=%s", (email, workspace_id, key))
        row = cursor.fetchone()
    return deepcopy(row[0]) if row and isinstance(row[0], dict) else None


def recent_workspace_turns(email: str, workspace_id: str, limit: int = 12) -> list[dict]:
    bounded = max(1, min(int(limit), 12))
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT input,output FROM surveyor_runs "
                       "WHERE email=%s AND interface_id=%s ORDER BY id DESC LIMIT %s",
                       (email, workspace_id, bounded))
        rows = cursor.fetchall()
    return [{"user": str(row[0] or "")[:6000], "assistant": str(row[1] or "")[:4000]}
            for row in reversed(rows)]


def has_workspace_turns(email: str, workspace_id: str) -> bool:
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT 1 FROM surveyor_runs WHERE email=%s AND interface_id=%s LIMIT 1",
                       (email, workspace_id))
        return cursor.fetchone() is not None


def commit_workspace_turn(email: str, workspace_id: str, expected_revision: int,
                          key: str, user_message: str, public_result: dict,
                          next_state: dict) -> dict:
    """Lock one owner workspace and atomically save at most one turn and mutation."""
    with _conn() as connection, connection.cursor() as cursor:
        cursor.execute("SELECT state FROM surveyor_workspaces "
                       "WHERE id=%s AND email=%s FOR UPDATE", (workspace_id, email))
        row = cursor.fetchone()
        if not row:
            return {"status": "missing"}
        cursor.execute("SELECT meta FROM surveyor_runs WHERE email=%s AND interface_id=%s "
                       "AND idempotency_key=%s", (email, workspace_id, key))
        prior = cursor.fetchone()
        if prior:
            return {"status": "prior", "result": deepcopy(prior[0])}
        current = (row[0] or {}) if isinstance(row[0], dict) else {}
        if int(current.get("revision", 0)) != expected_revision:
            return {"status": "conflict"}
        cursor.execute("UPDATE surveyor_workspaces SET state=%s, "
                       "updated=(now() AT TIME ZONE 'utc') WHERE id=%s AND email=%s",
                       (_J(next_state), workspace_id, email))
        cursor.execute("INSERT INTO surveyor_runs"
                       "(interface_id,email,input,output,meta,idempotency_key) "
                       "VALUES(%s,%s,%s,%s,%s,%s)",
                       (workspace_id, email, str(user_message)[:6000],
                        str(public_result.get("speech") or "")[:4000],
                        _J(public_result), key))
    return {"status": "committed", "result": deepcopy(public_result)}


def workspaces(email: str) -> list[tuple[str, dict]]:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, state FROM surveyor_workspaces WHERE email=%s", (email,))
        return cur.fetchall()


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
        pm = prev_meta or {}
        out.append({
            "email": email,
            "conversation_id": cid,
            "message_id": mid,
            "stage": pm.get("stage"),          # preferences | scenarios | freeform
            "key": pm.get("key"),              # signal name, scenario id, or freeform key
            "question": prev,
            "signal": pm.get("signal"),
            "answer": content,
            "tapped_suggestion": bool((meta or {}).get("choice")),
            "created": str(created),
        })
    return out


def export_profiles() -> list:
    """One row per participant: signals, scenario choices, free text and any
    stated-vs-revealed tensions. This is the shape phase 2 clusters on."""
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT email, signals, scenarios, freeform, tensions, reliability, "
                    "confidence, questions_answered, updated FROM surveyor_profiles "
                    "ORDER BY updated DESC")
        rows = cur.fetchall()
    return [{"email": r[0], "signals": r[1], "scenarios": r[2], "freeform": r[3],
             "tensions": r[4], "reliability": r[5], "completeness": r[6],
             "answers": r[7], "updated": str(r[8])} for r in rows]


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
                    "VALUES (%s,%s,%s,%s,%s) RETURNING id",
                    (interface_id, email, inp, out, _J(meta or {})))
        return str(cur.fetchone()[0])


# --------------------------------------------------------------- approvals

def save_approval(email, checkpoint: dict) -> None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""INSERT INTO surveyor_approvals(id, run_id, email, step_id, summary, status)
                       VALUES (%s,%s,%s,%s,%s,%s)""",
                    (checkpoint['id'], checkpoint['run_id'], email, checkpoint['step_id'],
                     checkpoint['summary'], checkpoint['status']))


def decide_approval(email, decision: dict) -> bool:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""UPDATE surveyor_approvals SET status=%s, approver=%s, note=%s,
                       decided=(now() AT TIME ZONE 'utc') WHERE id=%s AND email=%s AND status='pending'""",
                    (decision['status'], decision['approver'], decision['note'], decision['id'], email))
        return cur.rowcount == 1


def pending_approvals(email) -> list:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT id, run_id, step_id, summary, created FROM surveyor_approvals "
                    "WHERE email=%s AND status='pending' ORDER BY created DESC", (email,))
        return [{'id': r[0], 'run_id': r[1], 'step_id': r[2], 'summary': r[3],
                 'status': 'pending', 'created': str(r[4])} for r in cur.fetchall()]


def get_pending_approval(email, approval_id: str) -> dict | None:
    with _conn() as c, c.cursor() as cur:
        cur.execute("""SELECT id, run_id, step_id, summary, created FROM surveyor_approvals
                       WHERE id=%s AND email=%s AND status='pending'""", (approval_id, email))
        row = cur.fetchone()
    return ({'id': row[0], 'run_id': row[1], 'step_id': row[2], 'summary': row[3],
             'status': 'pending', 'created': str(row[4])} if row else None)


def runs(email, limit=50) -> list:
    with _conn() as c, c.cursor() as cur:
        cur.execute("SELECT interface_id, input, output, created FROM surveyor_runs "
                    "WHERE email=%s ORDER BY id DESC LIMIT %s", (email, limit))
        return [{"interface_id": r[0], "input": r[1], "output": r[2], "created": str(r[3])}
                for r in cur.fetchall()]
