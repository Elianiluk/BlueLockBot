"""Checks WeebCentral for new Blue Lock chapters and sends a Telegram message.
Also checks the official Weekly Shonen Magazine site for breaks.

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
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

SERIES_URL = "https://weebcentral.com/series/01J76XYD7E91K8QP6CY0Y53900/Blue-Lock"
MAGAZINE_URL = "https://shonenmagazine.com/smaga/"
STATE_FILE = Path(__file__).with_name("state.json")
CHAPTER_RE = re.compile(
    r'<a href="/chapters/([A-Z0-9]+)"[^>]*>.*?<span class="">([^<]+)</span>'
    r'.*?<time[^>]*datetime="([^"]+)"',
    re.S,
)
HEBREW_DAYS = ["שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת", "ראשון"]
BREAK_REASONS = {"体調不良": "המחבר לא מרגיש טוב", "取材": "המחבר יצא לתחקיר"}


def fmt_when(t):
    t = t.astimezone(ZoneInfo("Asia/Jerusalem"))
    return f"ביום {HEBREW_DAYS[t.weekday()]} {t:%d.%m} בסביבות {t:%H:%M} (שעון ישראל)"


def english_release(issue_date):
    """K Manga publishes the English chapter at 8:00 US Pacific on the day before
    the Japanese issue date; WeebCentral picks it up ~15 minutes later."""
    d = issue_date - timedelta(days=1)
    return datetime(d.year, d.month, d.day, 8, 15, tzinfo=ZoneInfo("America/Los_Angeles"))


def next_chapter_line(released, mag):
    try:
        now = datetime.now(timezone.utc)
        if mag:
            # The site may not have switched to the new issue yet, so try both
            for issue in (mag["issue"], mag["next_issue"]):
                t = english_release(issue)
                if t > now + timedelta(hours=12):
                    return f"\n\n📅 הפרק הבא צפוי {fmt_when(t)}, אלא אם יש הפסקה"
        # Fallback: a week after this chapter, in US Pacific time (handles DST)
        t = datetime.fromisoformat(released.replace("Z", "+00:00"))
        t = t.astimezone(ZoneInfo("America/Los_Angeles")) + timedelta(days=7)
        return f"\n\n📅 הפרק הבא צפוי {fmt_when(t)}, אלא אם יש הפסקה"
    except Exception as e:  # never let the estimate block the notification
        print("Next-chapter estimate failed:", e)
        return ""


def http_get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (bluelock-notifier)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8")


def fetch_chapters():
    """Returns [(chapter_id, name, released_iso)], newest first."""
    chapters = CHAPTER_RE.findall(http_get(SERIES_URL))
    if not chapters:
        raise RuntimeError("No chapters found - WeebCentral page layout may have changed")
    return chapters


def fetch_magazine():
    """Current Weekly Shonen Magazine issue: its date, the next issue's date and
    whether Blue Lock is on break in it. None if the page can't be read."""
    try:
        s = http_get(MAGAZINE_URL)
        cur = re.search(r"(\d{4})年(\d+)月(\d+)日（.）発売", s)
        nxt = re.search(r"週刊少年マガジン\s*\d+号\s*(\d+)月(\d+)日", s)
        issue = date(int(cur[1]), int(cur[2]), int(cur[3]))
        year = issue.year + (1 if int(nxt[1]) < issue.month else 0)
        next_issue = date(year, int(nxt[1]), int(nxt[2]))
        # e.g. ※『A』、『ブルーロック』は作者体調不良のため、『C』は作者取材のため休載となります。
        notice = " ".join(re.findall(r"※[^<]*休載[^<]*", s))
        why = re.search(r"『ブルーロック』(?:、『[^』]+』)*は(.+?)のため", notice)
        reason = next((he for jp, he in BREAK_REASONS.items() if why and jp in why[1]), "")
        return {"issue": issue, "next_issue": next_issue,
                "on_break": "『ブルーロック』" in notice, "reason": reason}
    except Exception as e:
        print("Magazine check failed:", e)
        return None


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


def check_breaks(token, chat_id, state, mag):
    issue = str(mag["issue"])
    after = f"\n📅 הפרק הבא צפוי {fmt_when(english_release(mag['next_issue']))}"

    if mag["on_break"] and state.get("break_notified") != issue:
        reason = f" ({mag['reason']})" if mag["reason"] else ""
        telegram(token, "sendMessage", chat_id=chat_id,
                 text=f"⏸️ השבוע אין פרק חדש של Blue Lock: הסדרה בהפסקה{reason}.{after}")
        state["break_notified"] = issue
        print("Notified: Blue Lock break")

    # A gap of more than a week means the whole magazine skips an issue
    if (mag["next_issue"] - mag["issue"]).days > 7 and state.get("gap_notified") != issue:
        telegram(token, "sendMessage", chat_id=chat_id,
                 text=f"⏸️ בשבוע הבא אין פרק של Blue Lock: המגזין לוקח הפסקה.{after}")
        state["gap_notified"] = issue
        print("Notified: magazine break")


def main():
    token = os.environ["TELEGRAM_TOKEN"]
    state = json.loads(STATE_FILE.read_text(encoding="utf-8")) if STATE_FILE.exists() else {}

    chat_id = os.environ.get("TELEGRAM_CHAT_ID") or state.get("chat_id") or find_chat_id(token)
    state["chat_id"] = chat_id

    chapters = fetch_chapters()
    mag = fetch_magazine()
    seen = state.get("last_chapter_id")

    if seen is None:
        cid, name, released = chapters[0]
        telegram(token, "sendMessage", chat_id=chat_id,
                 text=f"✅ הבוט פעיל! הפרק האחרון של Blue Lock כרגע: {name}\nhttps://weebcentral.com/chapters/{cid}"
                      + next_chapter_line(released, mag))
    else:
        ids = [c[0] for c in chapters]
        # Everything newer than the last chapter we notified about (oldest first)
        new = chapters[: ids.index(seen)] if seen in ids else chapters[:1]
        for cid, name, released in reversed(new):
            url = f"https://weebcentral.com/chapters/{cid}"
            button = {"inline_keyboard": [[{"text": "📖 לקריאת הפרק", "url": url}]]}
            # Only the newest chapter gets the next-release estimate
            extra = next_chapter_line(released, mag) if cid == chapters[0][0] else ""
            telegram(token, "sendMessage", chat_id=chat_id,
                     text=f"⚽🔵 Blue Lock {name} יצא באנגלית!\n{url}{extra}",
                     reply_markup=json.dumps(button))
            print("Notified:", name)
        if not new:
            print("No new chapter. Latest:", chapters[0][1])

    if mag:
        check_breaks(token, chat_id, state, mag)

    state["last_chapter_id"] = chapters[0][0]
    state["last_chapter_name"] = chapters[0][1]
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print("ERROR:", e, file=sys.stderr)
        sys.exit(1)
