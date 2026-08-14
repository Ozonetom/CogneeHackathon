# test_qdrant.py
# Purpose: confirm your Qdrant clusters are reachable. Needs NO LLM key.
# Reads credentials from .env (copy .env.example -> .env and fill it in first).
# Run this to de-risk the finicky part before the hackathon.

import os

from dotenv import load_dotenv
from qdrant_client import QdrantClient

load_dotenv()


def check(label: str, url: str, key: str) -> None:
    print(f"--- {label} ({url or 'not set'}) ---")
    if not url:
        print("Skipped: URL not set in .env.\n")
        return
    try:
        client = QdrantClient(url=url, api_key=key or None)
        info = client.get_collections()
        print("Connected successfully.")
        print("Existing collections:", info.collections)
        print("(An empty list here is normal if you haven't added data yet.)\n")
    except Exception as e:
        print(f"FAILED: {e}\n")


check("Qdrant Cloud", os.getenv("QDRANT_CLOUD_URL", ""), os.getenv("QDRANT_CLOUD_KEY", ""))
check("Qdrant Local", os.getenv("QDRANT_LOCAL_URL", "http://localhost:6333"), os.getenv("QDRANT_LOCAL_KEY", ""))
