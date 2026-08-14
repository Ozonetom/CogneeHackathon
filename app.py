# app.py — the demo. Dumb keyword search vs Cognee + Qdrant/Neo4j memory, plus the knowledge graph.
#
# Credentials come from .env (copy .env.example -> .env and fill it in) instead of
# being pasted into this file. Talks to whichever backend is currently reachable:
# cloud (Qdrant Cloud + Neo4j Aura) when online, local (Docker Qdrant + Docker
# Neo4j, last LOCAL_RETENTION_DAYS only) when offline. A sync (push local-only
# messages to cloud, then rebuild the local window) runs once per browser session
# and again every SYNC_MIN_INTERVAL_HOURS in the background -- see scheduler.py.
#
# Before running: `docker compose up -d`, fill in .env, then `python build_memory.py`
# once to seed the memory. Then: streamlit run app.py

import asyncio
import json
import os

import streamlit as st
import streamlit.components.v1 as components

import ledger
import scheduler
import store_config as sc
from connectivity import cloud_reachable
from keyword_search import keyword_search

with open("slack_export_sample.json", "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

Q1 = "checkout is hanging and orders aren't going through, has anyone seen this before?"
Q2 = "What is our current database plan for the events service?"
Q3 = "Who should I talk to about the checkout incident, and is there any related risk I should know about?"


@st.cache_data(ttl=300)
def check_reachable() -> bool:
    return asyncio.run(cloud_reachable())


def cognee_answer(question: str):
    """Query whichever backend is currently reachable."""
    target = "cloud" if check_reachable() else "local"
    sc.apply_target(target)
    from cognee import search, SearchType

    results = asyncio.run(search(query_type=SearchType.GRAPH_COMPLETION, query_text=question))
    return target, results


st.set_page_config(page_title="Give Your Slack a Memory", layout="wide")

# Runs once per process (safe under Streamlit reruns -- module top level only
# executes once) and once per browser session, each gated by the 12h recency
# check inside scheduler.maybe_run_sync().
scheduler.ensure_background_scheduler_started()
if "synced_this_session" not in st.session_state:
    ledger.seed_from_json("slack_export_sample.json")
    scheduler.maybe_run_sync()
    st.session_state["synced_this_session"] = True

with st.sidebar:
    st.subheader("Sync status")
    online = check_reachable()
    st.markdown(("🟢 Cloud reachable" if online else "🔴 Offline — using local backup"))
    info = scheduler.last_sync_info()
    if info.get("last_sync_finished_at"):
        st.caption(f"Last synced: {info['last_sync_finished_at']}")
        st.caption(f"Pushed: {info.get('last_pushed', 0)} · Local window: {info.get('last_local_window', 0)}")
    else:
        st.caption("Never synced yet.")
    if info.get("last_status") == "error":
        st.caption(f"Last sync error: {info.get('last_error', '')}")
    if st.button("Sync now"):
        with st.spinner("Syncing..."):
            check_reachable.clear()
            result = scheduler.maybe_run_sync(force=True)
        if result and result.status == "ok":
            st.success(f"Synced. Pushed {result.pushed}, local window {result.local_window}.")
        elif result and result.status == "offline":
            st.warning("Still offline — nothing to sync against.")
        elif result and result.status == "error":
            st.error(f"Sync failed: {result.error}")
        st.rerun()

st.title("Give Your Slack a Memory")
st.caption("Same question, two engines. Left: ordinary keyword search. Right: Cognee + Qdrant connected memory.")

if "query" not in st.session_state:
    st.session_state["query"] = Q1

st.markdown("**Try the escalating demo:**")
c1, c2, c3 = st.columns(3)
if c1.button("1 · Seen this before?"):
    st.session_state["query"] = Q1
if c2.button("2 · Current plan? (time-aware)"):
    st.session_state["query"] = Q2
if c3.button("3 · Connect the dots (multi-hop)"):
    st.session_state["query"] = Q3

question = st.text_input("Ask the Slack history:", key="query")

if st.button("Search", type="primary"):
    left, right = st.columns(2)

    with left:
        st.subheader("Keyword search")
        hits, tokens = keyword_search(question, MESSAGES)
        st.caption(f"Searching for words: {tokens}")
        if hits:
            for m in hits:
                st.markdown(f"**{m['user']}** in #{m['channel']} · _{m['datetime']}_")
                st.write(m["text"])
                st.divider()
        else:
            st.error("No results — the exact words don't appear in any message.")

    with right:
        st.subheader("Cognee + Qdrant memory")
        try:
            with st.spinner("Recalling from connected memory..."):
                target, results = cognee_answer(question)
            st.caption(f"Answered from: {target}")
            for r in results:
                st.success(r)
        except Exception as e:
            st.warning(f"Memory not ready yet — run build_memory.py first.\n\n{e}")

st.divider()
with st.expander("Show the knowledge graph Cognee built", expanded=False):
    graph_path = os.path.join(".artifacts", "graph_visualization.html")
    if os.path.exists(graph_path):
        with open(graph_path, "r", encoding="utf-8") as f:
            components.html(f.read(), height=650, scrolling=True)
    else:
        st.info("Run `python build_memory.py` first to generate the graph.")
