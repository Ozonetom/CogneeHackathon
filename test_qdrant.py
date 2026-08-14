# test_qdrant.py
# Purpose: confirm your Qdrant Cloud cluster is reachable. Needs NO LLM key.
# Run this TONIGHT to de-risk the finicky part before the hackathon.

from qdrant_client import QdrantClient

# ---- PASTE YOUR TWO QDRANT VALUES HERE -------------------------------
QDRANT_URL = ""   # <-- your cluster URL (keep the :6333)
QDRANT_KEY = ""                             # <-- your Qdrant API key
# ----------------------------------------------------------------------

client = QdrantClient(url=QDRANT_URL, api_key=QDRANT_KEY)

# This call fails loudly if the URL or key is wrong — which is exactly what we want to catch tonight.
info = client.get_collections()

print("Connected to Qdrant successfully.")
print("Existing collections:", info.collections)
print("(An empty list here is normal — you haven't added data yet.)")
