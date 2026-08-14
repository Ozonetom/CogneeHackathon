# keyword_search.py
# The "dumb search" baseline — the BEFORE panel of your demo.
# Runs tonight with NO LLM key. Also imported by the UI later.
#
# It does what ordinary keyword search does: match the literal words.
# That's exactly why it fails on questions worded differently from the original message.

import json
import re

# Common filler words we ignore, so the match is as *generous* as a real search engine.
STOPWORDS = {
    "a", "an", "the", "and", "or", "of", "to", "in", "on", "for", "with", "about",
    "is", "are", "was", "were", "be", "been", "has", "have", "had", "do", "does", "did",
    "i", "we", "you", "it", "its", "this", "that", "these", "those", "any", "anyone",
    "through", "before", "after", "yet", "so", "at", "as", "by",
}


def words_in(text):
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def keyword_search(query, messages):
    """Return (matching_messages, keywords_used). Matches if ANY content word overlaps."""
    # len >= 3 drops stray fragments like the "t" from "aren't"/"can't", which would
    # otherwise falsely match any message containing a contraction.
    tokens = [t for t in re.findall(r"[a-z0-9]+", query.lower())
              if t not in STOPWORDS and len(t) >= 3]
    hits = []
    for m in messages:
        if words_in(m["text"]) & set(tokens):
            hits.append(m)
    return hits, tokens


if __name__ == "__main__":
    with open("slack_export_sample.json", "r", encoding="utf-8") as f:
        messages = json.load(f)

    demo_queries = [
        # The real demo question — worded nothing like Priya's message. Expect ZERO hits.
        "checkout is hanging and orders aren't going through, has anyone seen this before?",
        # A control: the literal word IS in the data, so keyword search finds it. Expect hits.
        "Stripe",
    ]

    for q in demo_queries:
        hits, tokens = keyword_search(q, messages)
        print("=" * 70)
        print("Query:   ", q)
        print("Keywords:", tokens)
        print(f"Matches:  {len(hits)}")
        for m in hits:
            print(f"   [{m['datetime']}] {m['user']} in #{m['channel']}: {m['text'][:70]}...")
        if not hits:
            print("   (nothing found — the words simply don't appear in any message)")
        print()
