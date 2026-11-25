"""
news_ml.py
─────────────────────────────────────────────────────────────
Central store for the one-off Malayalam "today's top news" Shorts.
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
        "title": "ഇന്നത്തെ പ്രധാന വാർത്തകൾ",
        "hook": "ഇന്നത്തെ അഞ്ച് പ്രധാന വാർത്തകൾ.",
        "text": "ആഫ്രിക്ക കപ്പ് ഓഫ് നേഷൻസ് കിരീടം സെനഗലിന് തിരികെ ലഭിച്ചു. മൊറോക്കോയ്ക്ക് അനുകൂലമായ മുൻ വിധി കായിക തർക്ക പരിഹാര കോടതി റദ്ദാക്കി. || ചൈനയുടെ ബഹിരാകാശ നിലയത്തിൽ എത്തുന്ന ആദ്യത്തെ വിദേശ ബഹിരാകാശ യാത്രികനായി പാകിസ്ഥാന്റെ സീഷാൻ അലി. || പതിനഞ്ച് വയസ്സുള്ള വൈഭവ് സൂര്യവംശി ഒരു ലിസ്റ്റ് എ മത്സരത്തിൽ വെറും അമ്പത്തിമൂന്ന് പന്തിൽ ഇരുനൂറ്റി നാല് റൺസ് അടിച്ചു. || ടൈം മാസികയുടെ പട്ടികയിൽ ലോകത്തിലെ ഏറ്റവും മികച്ച എയർലൈനായി എമിറേറ്റ്സ് തിരഞ്ഞെടുക്കപ്പെട്ടു. ഏറ്റവും വിശ്വസനീയമായ എയർലൈനുകളിൽ ഇൻഡിഗോ ആറാം സ്ഥാനത്താണ്. || നിർമ്മിത ബുദ്ധിയെക്കുറിച്ചുള്ള ആശങ്കകൾ കാരണം ജപ്പാൻ, ദക്ഷിണ കൊറിയ, തായ്വാൻ, ഹോങ്കോങ് എന്നിവിടങ്ങളിലെ ഓഹരി വിപണികൾ ഇടിഞ്ഞു.",
        "sources": "Al Jazeera, NDTV, Times of India, Indian Express (Nov 24–25, 2026)",
        "footage": "football trophy|space station|cricket stadium|airplane|stock market",
        "status": "posted",
        "posted_at": "2026-11-25T13:26:25",
    },
]
