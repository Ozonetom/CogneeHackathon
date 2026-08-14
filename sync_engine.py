# sync_engine.py
# The actual push-then-rebuild routine. Never called directly on a timer or from
# app.py -- go through scheduler.maybe_run_sync(), which adds recency-gating and
# a lock so this doesn't run twice concurrently or more often than intended.

import os
import pathlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import ledger
import store_config as sc
from connectivity import cloud_reachable

RETENTION_DAYS = int(os.getenv("LOCAL_RETENTION_DAYS", "14"))
ARTIFACTS_DIR = pathlib.Path(__file__).parent / ".artifacts"


@dataclass
class SyncResult:
    status: str  # "offline" | "ok" | "error"
    pushed: int = 0
    local_window: int = 0
    error: str = ""


async def _push_pending_to_cloud() -> int:
    pending = ledger.get_unpushed()
    if not pending:
        return 0

    sc.apply_target("cloud")
    from cognee import add, cognify

    for m in pending:
        await add(ledger.format_message(m), dataset_name=sc.DATASET_NAME)
    await cognify(datasets=[sc.DATASET_NAME])

    # Only mark pushed once cognify() has actually succeeded, so a failure here
    # leaves these rows pending and they're safely retried next sync (add() is
    # idempotent -- Cognee content-hashes Data rows).
    ledger.mark_pushed([m["msg_id"] for m in pending])
    return len(pending)


async def _rebuild_local_window() -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=RETENTION_DAYS)
    window = ledger.get_since(cutoff)

    sc.apply_target("local")
    from cognee import add, cognify, prune, visualize_graph

    await prune.prune_data()
    await prune.prune_system(metadata=True)

    for m in window:
        await add(ledger.format_message(m), dataset_name=sc.DATASET_NAME)
    if window:
        await cognify(datasets=[sc.DATASET_NAME])

    ARTIFACTS_DIR.mkdir(exist_ok=True)
    try:
        await visualize_graph(str(ARTIFACTS_DIR / "graph_visualization.html"))
    except Exception:
        pass  # graph viz is a nice-to-have for the UI, never block sync on it

    return len(window)


async def run_sync() -> SyncResult:
    if not await cloud_reachable():
        return SyncResult(status="offline")

    try:
        pushed = await _push_pending_to_cloud()
        local_window = await _rebuild_local_window()
        return SyncResult(status="ok", pushed=pushed, local_window=local_window)
    except Exception as e:
        return SyncResult(status="error", error=str(e))
