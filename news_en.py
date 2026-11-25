"""
news_en.py
─────────────────────────────────────────────────────────────
Central store for the one-off English "today's top news" Shorts.
Each entry is one Short: the hook, then "Number one." story 1 … story 5.

Each entry is a dict with these fields:
  {
    "id"        : unique int  (never reuse / reorder),
    "title"     : on-screen label,
    "hook"      : opening line (also the YouTube title),
    "text"      : the stories, separated by " || ",
    "sources"   : news outlets the stories came from (shown in the description),
    "footage"   : English Pexels searches, separated by "|",
    "status"    : "pending" | "posted"   ← updated by quote_status.py after upload
    "posted_at" : ISO-8601 UTC string, or None
  }

quote_status.py reads and writes the "status" / "posted_at" fields
directly in this file so everything stays in one place — no separate JSON needed.

To add a new news Short: append a new dict with a unique id,
status="pending", and posted_at=None.
News shorts are never re-posted: once every news Short is posted the bot stops
with an error until new news Shorts are added here.
─────────────────────────────────────────────────────────────
"""

DEFAULT_QUOTES = [
    {
        "id": 1,
        "title": "TODAY'S TOP 5 | NOV 25",
        "hook": "Here are today's top 5 news stories.",
        "text": "Senegal gets its Africa Cup of Nations title back. The Court of Arbitration for Sport overturned the earlier ruling in Morocco's favour. || Pakistan's Zeeshan Ali has become the first foreign astronaut to board China's space station. || Fifteen year old Vaibhav Sooryavanshi smashed 204 runs off just 53 balls in a List A match. || Emirates was named the world's best airline in TIME's 2027 list, and IndiGo came sixth among the most reliable airlines. || Asian stock markets in Japan, South Korea, Taiwan and Hong Kong fell, as worries about AI continued.",
        "sources": "Al Jazeera, NDTV, Times of India, Indian Express (Nov 24–25, 2026)",
        "footage": "football trophy|space station|cricket stadium|airplane|stock market",
        "status": "pending",
        "posted_at": None,
    },
]
