# bot.py — a LIVE Slack bot that answers @mentions from your Cognee memory.
# No ngrok needed (Socket Mode). Reuses the memory you built with build_memory.py.
#
# Credentials come from .env (copy .env.example -> .env and fill it in) instead of
# being pasted into this file.
#
# Run:  python bot.py    (with your (venv) active, after build_memory.py has populated the memory)

import os
import re
import asyncio

from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

import store_config as sc

load_dotenv()

SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN", "")
SLACK_APP_TOKEN = os.getenv("SLACK_APP_TOKEN", "")


def cognee_answer(question):
    """Query the memory built by build_memory.py (always the cloud copy -- a live
    Slack bot needs the durable, always-retained backend, not the local rolling
    14-day cache)."""
    sc.apply_target("cloud")
    from cognee import search, SearchType

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
