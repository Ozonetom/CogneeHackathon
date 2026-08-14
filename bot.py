# bot.py — a LIVE Slack bot that answers @mentions from your Cognee memory.
# No ngrok needed (Socket Mode). Reuses the memory you built with build_memory.py.
#
# Run:  python bot.py    (with your (venv) active, after build_memory.py has populated the memory)

import os

os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
os.environ["LLM_API_KEY"] = ""   # <-- the SAME event key you used in build_memory.py

# --- Qdrant (vector store) ---
QDRANT_URL = ""
QDRANT_KEY = ""

# --- Neo4j Aura (graph store) ---
NEO4J_URL  = ""
NEO4J_USER = ""
NEO4J_PASS = ""

# --- Slack tokens ---
SLACK_BOT_TOKEN = ""   # Bot User OAuth Token (from OAuth & Permissions after install)
SLACK_APP_TOKEN = ""   # App-level token with connections:write (from Socket Mode)

import re
import asyncio
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler


def cognee_answer(question):
    """Query the memory built by build_memory.py."""
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


app = App(token=SLACK_BOT_TOKEN)


@app.event("app_mention")
def handle_mention(event, say):
    # Remove the "<@BOTID>" part, leaving the actual question.
    question = re.sub(r"<@[^>]+>", "", event.get("text", "")).strip()
    if not question:
        say("Ask me something like:  `@Memory has checkout broken before?`")
        return
    say(f":brain: searching our memory for _{question}_ …")
    try:
        say(cognee_answer(question))
    except Exception as e:
        say(f":warning: something went wrong: {e}")


if __name__ == "__main__":
    print("Slack memory bot is running. Invite it to a channel and @mention it.")
    SocketModeHandler(app, SLACK_APP_TOKEN).start()
