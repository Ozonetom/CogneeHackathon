# store_config.py
# Single choke point for switching Cognee between the "local" (Docker Qdrant + Docker
# Neo4j) and "cloud" (Qdrant Cloud + Neo4j Aura) backends. Every module that talks to
# Cognee (ledger sync, app.py, build_memory.py, bot.py) should go through apply_target()
# instead of calling config.set_*_db_config() directly, so there's exactly one place
# that knows what "local" and "cloud" mean.

import os
import pathlib

from dotenv import load_dotenv

load_dotenv()

# Cognee's multi-user access-control mode isn't compatible with the Qdrant vector store.
os.environ["ENABLE_BACKEND_ACCESS_CONTROL"] = "false"
if os.getenv("LLM_API_KEY"):
    os.environ["LLM_API_KEY"] = os.getenv("LLM_API_KEY")

ROOT = pathlib.Path(__file__).parent
DATASET_NAME = "slack_memory"

LOCAL_VECTOR_CFG = {
    "vector_db_provider": "qdrant",
    "vector_db_url": os.getenv("QDRANT_LOCAL_URL", "http://localhost:6333"),
    "vector_db_key": os.getenv("QDRANT_LOCAL_KEY", ""),
}
LOCAL_GRAPH_CFG = {
    "graph_database_provider": "neo4j",
    "graph_database_url": os.getenv("NEO4J_LOCAL_URL", "bolt://localhost:7687"),
    "graph_database_username": os.getenv("NEO4J_LOCAL_USER", "neo4j"),
    "graph_database_password": os.getenv("NEO4J_LOCAL_PASS", ""),
}

CLOUD_VECTOR_CFG = {
    "vector_db_provider": "qdrant",
    "vector_db_url": os.getenv("QDRANT_CLOUD_URL", ""),
    "vector_db_key": os.getenv("QDRANT_CLOUD_KEY", ""),
}
CLOUD_GRAPH_CFG = {
    "graph_database_provider": "neo4j",
    "graph_database_url": os.getenv("NEO4J_CLOUD_URL", ""),
    "graph_database_username": os.getenv("NEO4J_CLOUD_USER", ""),
    "graph_database_password": os.getenv("NEO4J_CLOUD_PASS", ""),
}

_TARGETS = {
    "local": (LOCAL_VECTOR_CFG, LOCAL_GRAPH_CFG, ROOT / ".cognee_local_system", ROOT / ".data_storage_local"),
    "cloud": (CLOUD_VECTOR_CFG, CLOUD_GRAPH_CFG, ROOT / ".cognee_cloud_system", ROOT / ".data_storage_cloud"),
}


def apply_target(target: str) -> None:
    """Point Cognee at either the local or cloud backend. Call this before any
    add()/cognify()/search()/prune.*() call — those all read from global config."""
    if target not in _TARGETS:
        raise ValueError(f"Unknown target {target!r}, expected 'local' or 'cloud'")

    from cognee_community_vector_adapter_qdrant import register  # noqa: F401  (registers Qdrant)
    from cognee import config

    vector_cfg, graph_cfg, system_root, data_root = _TARGETS[target]

    config.system_root_directory(str(system_root))
    config.data_root_directory(str(data_root))
    config.set_relational_db_config({"db_provider": "sqlite"})
    config.set_graph_db_config(graph_cfg)
    config.set_vector_db_config(vector_cfg)
