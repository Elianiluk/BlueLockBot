"""Checks WeebCentral for new Blue Lock chapters and sends a Telegram message.

Env vars:
  TELEGRAM_TOKEN    - bot token from @BotFather (required)
  TELEGRAM_CHAT_ID  - optional; if missing, taken from the last message sent to the bot
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

SERIES_URL = "https://weebcentral.com/series/01J76XYD7E91K8QP6CY0Y53900/Blue-Lock"
STATE_FILE = Path(__file__).with_name("state.json")
CHAPTER_RE = re.compile(
    r'<a href="/chapters/([A-Z0-9]+)"[^>]*>.*?<span class="">([^<]+)</span>', re.S
)


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bluelock-notifier)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_chapters():
    """Returns [(chapter_id, name)], newest first."""
    chapters = CHAPTER_RE.findall(http_get(SERIES_URL))
    if not chapters:
        raise RuntimeError("No chapters found - WeebCentral page layout may have changed")
    return chapters


def telegram(token, method, **params):
    data = urllib.parse.urlencode(params).encode() if params else None
    with urllib.request.urlopen(f"https://api.telegram.org/bot{token}/{method}", data, timeout=30) as r:
        return json.load(r)["result"]


def find_chat_id(token):
    updates = telegram(token, "getUpdates")
    for u in reversed(updates):
        msg = u.get("message") or u.get("channel_post")
        if msg:
            return str(msg["chat"]["id"])
    raise RuntimeError("Send any message (e.g. /start) to your bot in Telegram, then run again")


def main():
    token = os.environ["TELEGRAM_TOKEN"]
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}

    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or state.get("chat_id") or find_chat_id(token)
    state["chat_id"] = chat_id

    chapters = fetch_chapters()
    seen = state.get("last_chapter_id")

    if seen is None:
        cid, name = chapters[0]
        telegram(token, "sendMessage", chat_id=chat_id,
                 text=f"✅ הבוט פעיל! הפרק האחרון של Blue Lock כרגע: {name}\nhttps://weebcentral.com/chapters/{cid}")
    else:
        ids = [c[0] for c in chapters]
        # Everything newer than the last chapter we notified about (oldest first)
        new = chapters[: ids.index(seen)] if seen in ids else chapters[:1]
        for cid, name in reversed(new):
            url = f"https://weebcentral.com/chapters/{cid}"
            button = {"inline_keyboard": [[{"text": "📖 לקריאת הפרק", "url": url}]]}
            telegram(token, "sendMessage", chat_id=chat_id,
                     text=f"⚽🔵 Blue Lock {name} יצא באנגלית!\n{url}",
                     reply_markup=json.dumps(button))
            print("Notified:", name)
        if not new:
            print("No new chapter. Latest:", chapters[0][1])

    state["last_chapter_id"] = chapters[0][0]
    state["last_chapter_name"] = chapters[0][1]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
