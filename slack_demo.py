# slack_demo.py — a LOCAL, Slack-styled chat. Type a question, the Memory bot answers
# from your Cognee memory. No real Slack needed.
#
# Run:  streamlit run slack_demo.py

import os

os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
os.environ["LLM_API_KEY"] = "key"   # <-- your OpenAI key (same as build_memory.py)

# --- Qdrant (vector store) ---
QDRANT_URL = "key"
QDRANT_KEY = "key"

# --- Neo4j Aura (graph store) ---
NEO4J_URL  = "key"
NEO4J_USER = "key"
NEO4J_PASS = "key"

import asyncio
import streamlit as st

USER_AVATAR = "🧑"
BOT_AVATAR = "🧠"
BOT_NAME = "Memory"


def cognee_answer(question):
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
    results = asyncio.run(search(query_type=SearchType.GRAPH_COMPLETION, query_text=question))
    if not results:
        return "I couldn't find anything about that in our memory yet."
    return "\n\n".join(str(r) for r in results)


st.set_page_config(page_title="#engineering — Memory", layout="centered")

# Slack-style channel header
st.markdown(
    """
    <div style="background:#3f0e40;color:white;padding:10px 16px;border-radius:8px 8px 0 0;
                font-family:sans-serif;margin-bottom:2px;">
      <span style="font-size:18px;font-weight:700;"># engineering</span>
      <span style="opacity:.7;font-size:13px;margin-left:10px;">Company memory bot · ask about anything discussed here</span>
    </div>
    """,
    unsafe_allow_html=True,
)

if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant",
         "content": "👋 Hi! I'm your team's memory. Ask me anything that's come up in Slack — "
                    "like *\"has checkout broken before?\"* or *\"what's our current database plan?\"*"}
    ]

# Render the conversation so far
for m in st.session_state.messages:
    avatar = BOT_AVATAR if m["role"] == "assistant" else USER_AVATAR
    with st.chat_message(m["role"], avatar=avatar):
        if m["role"] == "assistant":
            st.markdown(f"**{BOT_NAME}**  \n{m['content']}")
        else:
            st.markdown(m["content"])

# Quick-pick demo questions (so you don't fat-finger them live)
st.caption("Quick demo questions:")
c1, c2, c3 = st.columns(3)
preset = None
if c1.button("Seen this before?"):
    preset = "checkout is hanging and orders aren't going through, has anyone seen this before?"
if c2.button("Current DB plan?"):
    preset = "What is our current database plan for the events service?"
if c3.button("Who + related risk?"):
    preset = "Who should I talk to about the checkout incident, and is there any related risk?"

typed = st.chat_input("Message #engineering")
prompt = preset or typed

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        with st.spinner("searching our memory…"):
            answer = cognee_answer(prompt)
        st.markdown(f"**{BOT_NAME}**  \n{answer}")
    st.session_state.messages.append({"role": "assistant", "content": answer})
