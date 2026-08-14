# build_memory.py
# Seeds the message ledger from the Slack sample, then runs the same push+rebuild
# sync used by app.py (see sync_engine.py): pushes anything not yet pushed to
# cloud (Qdrant Cloud + Neo4j Aura), then rebuilds the local backup (Docker Qdrant
# + Docker Neo4j) to a fresh LOCAL_RETENTION_DAYS window. Then runs the three demo
# queries against whichever backend is currently reachable.
#
# BEFORE RUNNING: copy .env.example to .env and fill in your credentials.
# Then: python build_memory.py

import asyncio

import ledger
import store_config as sc
from connectivity import cloud_reachable
from sync_engine import run_sync

DEMO_QUERIES = [
    ("1) RECALL  -  has this happened before?",
     "checkout is hanging and orders aren't going through, has anyone seen this before?"),
    ("2) CURRENT TRUTH  -  time-aware, knows the decision was reversed",
     "What is our current database plan for the events service?"),
    ("3) CONNECT THE DOTS  -  multi-hop across people, incidents, and time",
     "Who should I talk to about the checkout incident, and is there any related risk I should know about?"),
]


async def main():
    inserted = ledger.seed_from_json("slack_export_sample.json")
    print(f"Ledger seeded ({inserted} new messages).")

    print("Syncing (push pending to cloud, rebuild local window)...")
    result = await run_sync()
    print(f"Sync result: {result.status}", end="")
    if result.status == "ok":
        print(f" — pushed {result.pushed}, local window {result.local_window}")
    elif result.status == "error":
        print(f" — {result.error}")
    else:
        print(" — no internet, working from whatever's already local")

    target = "cloud" if await cloud_reachable() else "local"
    print(f"\nRunning demo queries against: {target}\n")
    sc.apply_target(target)
    from cognee import search, SearchType

    for label, q in DEMO_QUERIES:
        print("=" * 72)
        print(label)
        print("Q:", q)
        results = await search(query_type=SearchType.GRAPH_COMPLETION, query_text=q)
        print("A:")
        for r in results:
            print(r)
        print()

    print("=" * 72)
    print("Knowledge graph saved to: .artifacts/graph_visualization.html")


if __name__ == "__main__":
    asyncio.run(main())
