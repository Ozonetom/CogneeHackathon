# build_memory.py
# Builds the Cognee memory from the Slack sample, using Qdrant (vectors) + Neo4j (graph),
# then runs the three demo queries and renders the knowledge graph.
#
# BEFORE RUNNING: paste your hosted LLM key + your Qdrant and Neo4j credentials below.
# Then:  python build_memory.py

import os

# Cognee's multi-user access-control mode isn't compatible with the Qdrant vector store,
# so we switch it off. (Keep this line whenever using Qdrant here.)
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"

# Your hosted LLM key (the event-provided key, or an OpenAI key). OpenAI is the default provider.
os.environ["LLM_API_KEY"] = ""   # <-- PASTE LLM KEY HERE

# --- Qdrant (vector store) ---
QDRANT_URL = ""   # <-- your Qdrant URL (keep :6333)
QDRANT_KEY = ""                            # <-- your Qdrant API key

# --- Neo4j Aura (graph store) ---
NEO4J_URL  = ""          # <-- your Aura URI
NEO4J_USER = ""
NEO4J_PASS = ""                            # <-- your Aura password

import json
import asyncio

from cognee_community_vector_adapter_qdrant import register  # noqa: F401  (registers Qdrant)
from cognee import config, add, cognify, search, prune, visualize_graph, SearchType

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

# The three escalating demo queries.
DEMO_QUERIES = [
    ("1) RECALL  -  has this happened before?",
     "checkout is hanging and orders aren't going through, has anyone seen this before?"),
    ("2) CURRENT TRUTH  -  time-aware, knows the decision was reversed",
     "What is our current database plan for the events service?"),
    ("3) CONNECT THE DOTS  -  multi-hop across people, incidents, and time",
     "Who should I talk to about the checkout incident, and is there any related risk I should know about?"),
]


def format_message(m):
    return f"[{m['datetime']}] {m['user']} in #{m['channel']}: {m['text']}"


async def main():
    await prune.prune_data()
    await prune.prune_system(metadata=True)

    with open("slack_export_sample.json", "r", encoding="utf-8") as f:
        messages = json.load(f)
    print(f"Loaded {len(messages)} messages.")

    for m in messages:
        await add(format_message(m))
    print("Messages added. Building the knowledge graph (LLM + embeddings into Qdrant)...")

    await cognify()
    print("Memory built.\n")

    for label, q in DEMO_QUERIES:
        print("=" * 72)
        print(label)
        print("Q:", q)
        results = await search(query_type=SearchType.GRAPH_COMPLETION, query_text=q)
        print("A:")
        for r in results:
            print(r)
        print()

    os.makedirs(".artifacts", exist_ok=True)
    graph_path = os.path.join(".artifacts", "graph_visualization.html")
    await visualize_graph(graph_path)
    print("=" * 72)
    print(f"Knowledge graph saved to: {graph_path}")


if __name__ == "__main__":
    asyncio.run(main())
