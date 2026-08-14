# app.py — the demo. Dumb keyword search vs Cognee + Qdrant/Neo4j memory, plus the knowledge graph.
#
# BEFORE RUNNING: paste the SAME credentials you put in build_memory.py.
# Then, after running build_memory.py once:  streamlit run app.py

import os

# Same access-control switch as build_memory.py (required with Qdrant).
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"

# Your hosted LLM key (event key, or OpenAI).
os.environ["LLM_API_KEY"] = ""   # <-- PASTE LLM KEY HERE

# --- Qdrant (vector store) ---
QDRANT_URL = ""
QDRANT_KEY = ""

# --- Neo4j Aura (graph store) ---
NEO4J_URL  = ""
NEO4J_USER = ""
NEO4J_PASS = ""

import json
import asyncio
import streamlit as st
import streamlit.components.v1 as components

from keyword_search import keyword_search

with open("slack_export_sample.json", "r", encoding="utf-8") as f:
    MESSAGES = json.load(f)

Q1 = "checkout is hanging and orders aren't going through, has anyone seen this before?"
Q2 = "What is our current database plan for the events service?"
Q3 = "Who should I talk to about the checkout incident, and is there any related risk I should know about?"


def cognee_answer(question):
    """Query the already-built Cognee memory (populated by build_memory.py)."""
    from cognee_community_vector_adapter_qdrant import register  # noqa: F401
    from cognee import config, search, SearchType

    config.set_relational_db_config({"db_provider": "sqlite"})
    config.set_graph_db_config({
        "graph_database_provider": "neo4j",
        "graph_database_url": NEO4J_URL,
        "graph_database_username": NEO4J_USER,
        "graph_database_password": NEO4J_PASS,
    })
    config.set_vector_db_config({
        "vector_db_provider": "qdrant",
        "vector_db_url": QDRANT_URL,
        "vector_db_key": QDRANT_KEY,
    })
    return asyncio.run(search(query_type=SearchType.GRAPH_COMPLETION, query_text=question))


st.set_page_config(page_title="Give Your Slack a Memory", layout="wide")
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
                results = cognee_answer(question)
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
