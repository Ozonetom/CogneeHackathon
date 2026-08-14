# scheduler.py
# Gates sync_engine.run_sync() to "at most once per SYNC_MIN_INTERVAL_HOURS, checked
# at session start and every ~5min in the background" (requirement: 12h cadence +
# session start, not continuous). Two guards make this safe under Streamlit, which
# re-executes app.py's top level on every rerun within a session:
#   1. A cross-process file lock + a state.json recency check, so concurrent/rapid
#      calls to maybe_run_sync() are cheap no-ops instead of duplicate syncs.
#   2. A module-level flag for the background poller thread -- Python only runs a
#      module's top-level code once per process, so this survives reruns fine.

import asyncio
import json
import os
import pathlib
import threading
import time
from datetime import datetime, timezone

from filelock import FileLock, Timeout

import sync_engine

ROOT = pathlib.Path(__file__).parent
SYNC_DIR = ROOT / ".cognee_sync"
LOCK_PATH = SYNC_DIR / "sync.lock"
STATE_PATH = SYNC_DIR / "state.json"

MIN_INTERVAL_HOURS = float(os.getenv("SYNC_MIN_INTERVAL_HOURS", "12"))
POLL_SECONDS = 5 * 60

_bg_thread = None
_bg_lock = threading.Lock()


def _read_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def _write_state(result: "sync_engine.SyncResult") -> None:
    SYNC_DIR.mkdir(exist_ok=True)
    state = {
        "last_attempt_at": datetime.now(timezone.utc).isoformat(),
        "last_status": result.status,
    }
    if result.status == "ok":
        state["last_sync_finished_at"] = state["last_attempt_at"]
        state["last_pushed"] = result.pushed
        state["last_local_window"] = result.local_window
    else:
        prev = _read_state()
        if "last_sync_finished_at" in prev:
            state["last_sync_finished_at"] = prev["last_sync_finished_at"]
        if result.status == "error":
            state["last_error"] = result.error
    STATE_PATH.write_text(json.dumps(state, indent=2))


def _due(state: dict) -> bool:
    last = state.get("last_sync_finished_at")
    if not last:
        return True
    elapsed_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(last)).total_seconds() / 3600
    return elapsed_hours >= MIN_INTERVAL_HOURS


def last_sync_info() -> dict:
    """For the UI: what happened last time, without triggering a new sync."""
    return _read_state()


def maybe_run_sync(force: bool = False) -> "sync_engine.SyncResult | None":
    """Run a sync now if one is due (or force=True) and no other sync is already
    running. Safe to call from any thread; a non-blocking lock makes concurrent
    callers no-ops rather than piling up."""
    SYNC_DIR.mkdir(exist_ok=True)
    lock = FileLock(str(LOCK_PATH), timeout=0)
    try:
        with lock:
            state = _read_state()
            if not force and not _due(state):
                return None
            result = asyncio.run(sync_engine.run_sync())
            _write_state(result)
            return result
    except Timeout:
        return None  # another sync is already running


def _poll_loop():
    while True:
        time.sleep(POLL_SECONDS)
        try:
            maybe_run_sync()
        except Exception:
            pass  # background poller must never crash the process


def ensure_background_scheduler_started() -> None:
    """Idempotent: safe to call on every Streamlit rerun. Starts one daemon
    thread per process that checks every ~5min whether a sync is due."""
    global _bg_thread
    with _bg_lock:
        if _bg_thread is None:
            _bg_thread = threading.Thread(target=_poll_loop, daemon=True, name="sync-poller")
            _bg_thread.start()
