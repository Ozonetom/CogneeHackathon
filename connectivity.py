# connectivity.py
# Cheap reachability probes for the cloud backend. Both Qdrant Cloud and Neo4j
# Aura must answer for cloud_reachable() to be true -- a "cloud" sync needs both.

import asyncio
import os

from dotenv import load_dotenv

load_dotenv()

DEFAULT_TIMEOUT = float(os.getenv("CONNECTIVITY_TIMEOUT_SECONDS", "5"))


def _probe_qdrant_sync(url: str, key: str, timeout: float) -> bool:
    if not url:
        return False
    from qdrant_client import QdrantClient

    try:
        client = QdrantClient(url=url, api_key=key or None, timeout=timeout)
        client.get_collections()
        return True
    except Exception:
        return False


async def probe_qdrant(url: str, key: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    return await asyncio.to_thread(_probe_qdrant_sync, url, key, timeout)


async def probe_neo4j(url: str, user: str, password: str, timeout: float = DEFAULT_TIMEOUT) -> bool:
    if not url:
        return False
    from neo4j import AsyncGraphDatabase

    try:
        driver = AsyncGraphDatabase.driver(url, auth=(user, password), connection_timeout=timeout)
        try:
            await asyncio.wait_for(driver.verify_connectivity(), timeout=timeout)
            return True
        finally:
            await driver.close()
    except Exception:
        return False


async def cloud_reachable(timeout: float = DEFAULT_TIMEOUT) -> bool:
    import store_config as sc

    try:
        qdrant_ok, neo4j_ok = await asyncio.wait_for(
            asyncio.gather(
                probe_qdrant(sc.CLOUD_VECTOR_CFG["vector_db_url"], sc.CLOUD_VECTOR_CFG["vector_db_key"], timeout),
                probe_neo4j(
                    sc.CLOUD_GRAPH_CFG["graph_database_url"],
                    sc.CLOUD_GRAPH_CFG["graph_database_username"],
                    sc.CLOUD_GRAPH_CFG["graph_database_password"],
                    timeout,
                ),
            ),
            timeout=timeout * 2,
        )
    except asyncio.TimeoutError:
        return False
    return bool(qdrant_ok and neo4j_ok)
