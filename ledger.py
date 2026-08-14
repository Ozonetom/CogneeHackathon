# ledger.py
# The durable, append-only source of truth for raw Slack messages and their sync
# state. Cognee's Qdrant/Neo4j stores are chunked, LLM-derived representations of
# this data, not a reliable way to reconstruct the original text -- so provenance
# lives here, independent of (and never wiped by) Cognee's prune().

import hashlib
import json
import pathlib
import sqlite3
from datetime import datetime, timezone

ROOT = pathlib.Path(__file__).parent
LEDGER_DIR = ROOT / ".cognee_ledger"
DB_PATH = LEDGER_DIR / "messages.sqlite3"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    msg_id TEXT PRIMARY KEY,
    channel TEXT NOT NULL,
    user TEXT NOT NULL,
    ts REAL NOT NULL,
    datetime TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT NOT NULL DEFAULT 'seed',
    ingested_at TEXT NOT NULL,
    pushed_to_cloud_at TEXT
);
"""


def _connect() -> sqlite3.Connection:
    LEDGER_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute(_SCHEMA)
    return conn


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _msg_id(m: dict) -> str:
    key = f"{m['channel']}|{m['ts']}|{m['user']}"
    return hashlib.sha1(key.encode("utf-8")).hexdigest()


def format_message(m: dict) -> str:
    """Render a ledger row (or raw message dict) as the text Cognee ingests."""
    return f"[{m['datetime']}] {m['user']} in #{m['channel']}: {m['text']}"


def seed_from_json(path) -> int:
    """Idempotently load messages from a Slack-export-shaped JSON file. Safe to
    call every run -- existing rows (by msg_id) are left untouched."""
    with open(path, "r", encoding="utf-8") as f:
        messages = json.load(f)

    conn = _connect()
    inserted = 0
    with conn:
        for m in messages:
            cur = conn.execute(
                """INSERT OR IGNORE INTO messages
                   (msg_id, channel, user, ts, datetime, text, source, ingested_at)
                   VALUES (?, ?, ?, ?, ?, ?, 'seed', ?)""",
                (_msg_id(m), m["channel"], m["user"], m["ts"], m["datetime"], m["text"], _now()),
            )
            inserted += cur.rowcount
    conn.close()
    return inserted


def insert_live(m: dict) -> bool:
    """Record a message ingested outside the seed file (e.g. a real Slack event).
    Returns True if it was newly inserted, False if it was already present."""
    conn = _connect()
    with conn:
        cur = conn.execute(
            """INSERT OR IGNORE INTO messages
               (msg_id, channel, user, ts, datetime, text, source, ingested_at)
               VALUES (?, ?, ?, ?, ?, ?, 'live', ?)""",
            (_msg_id(m), m["channel"], m["user"], m["ts"], m["datetime"], m["text"], _now()),
        )
        new_row = cur.rowcount > 0
    conn.close()
    return new_row


def get_unpushed() -> list[dict]:
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM messages WHERE pushed_to_cloud_at IS NULL ORDER BY ts ASC"
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM messages LIMIT 0").description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]


def mark_pushed(msg_ids: list[str], when: str = None) -> None:
    if not msg_ids:
        return
    when = when or _now()
    conn = _connect()
    with conn:
        conn.executemany(
            "UPDATE messages SET pushed_to_cloud_at = ? WHERE msg_id = ?",
            [(when, mid) for mid in msg_ids],
        )
    conn.close()


def get_since(cutoff_datetime: datetime) -> list[dict]:
    """All messages with ts >= cutoff, oldest first."""
    conn = _connect()
    rows = conn.execute(
        "SELECT * FROM messages WHERE ts >= ? ORDER BY ts ASC",
        (cutoff_datetime.timestamp(),),
    ).fetchall()
    cols = [d[0] for d in conn.execute("SELECT * FROM messages LIMIT 0").description]
    conn.close()
    return [dict(zip(cols, row)) for row in rows]
