"""
subscribers.py
─────────────────────────────────────────────────────────────
Live subscriber count for the end-of-Short "road to N subscribers" ask.
Kept free of the video dependencies so it can be checked on its own:

    python subscribers.py
─────────────────────────────────────────────────────────────
"""

import os
import re
import requests

CHANNEL_ID = os.environ.get("CHANNEL_ID", "UCAwi0YRrGlTn7E46RaAdtmw")

_ML_TENS = {1: "പത്ത്", 2: "ഇരുപത്", 3: "മുപ്പത്", 4: "നാൽപ്പത്", 5: "അമ്പത്",
            6: "അറുപത്", 7: "എഴുപത്", 8: "എൺപത്", 9: "തൊണ്ണൂറ്"}
# (standalone, before more digits) — "ഇരുനൂറ്" / "ഇരുനൂറ്റി എൺപത്"
_ML_HUNDREDS = {1: ("നൂറ്", "നൂറ്റി"), 2: ("ഇരുനൂറ്", "ഇരുനൂറ്റി"), 3: ("മുന്നൂറ്", "മുന്നൂറ്റി"),
                4: ("നാനൂറ്", "നാനൂറ്റി"), 5: ("അഞ്ഞൂറ്", "അഞ്ഞൂറ്റി"), 6: ("അറുനൂറ്", "അറുനൂറ്റി"),
                7: ("എഴുനൂറ്", "എഴുനൂറ്റി"), 8: ("എണ്ണൂറ്", "എണ്ണൂറ്റി"),
                9: ("തൊള്ളായിരം", "തൊള്ളായിരത്തി")}
_ML_THOUSANDS = {1: "ആയിരം", 2: "രണ്ടായിരം", 3: "മൂവായിരം", 4: "നാലായിരം", 5: "അയ്യായിരം",
                 6: "ആറായിരം", 7: "ഏഴായിരം", 8: "എണ്ണായിരം", 9: "ഒമ്പതിനായിരം"}


def ml_number(n):
    """Malayalam words for a multiple of ten below 10,000 (e.g. 280 → "ഇരുനൂറ്റി എൺപത്");
    digits for anything else."""
    if n % 10 or not 0 < n < 10000:
        return str(n)
    th, h, t = n // 1000, n // 100 % 10, n // 10 % 10
    words = []
    if th:
        w = _ML_THOUSANDS[th]
        words.append(w[:-1] + "ത്തി" if (h or t) else w)   # ആയിരം → ആയിരത്തി
    if h:
        words.append(_ML_HUNDREDS[h][1 if t else 0])
    if t:
        words.append(_ML_TENS[t])
    return " ".join(words)


_subscriber_count = "unset"


def get_subscriber_count():
    """The channel's current subscriber count, or None if it can't be read.
    Tries the YouTube API with the upload credentials (works if the refresh
    token also has a read scope), then an optional YOUTUBE_API_KEY, then the
    public channel page."""
    global _subscriber_count
    if _subscriber_count != "unset":
        return _subscriber_count
    _subscriber_count = None
    api = "https://www.googleapis.com/youtube/v3/channels"
    attempts = []
    if os.environ.get("REFRESH_TOKEN"):
        def oauth():
            tok = requests.post("https://oauth2.googleapis.com/token", timeout=15, data={
                "grant_type": "refresh_token", "refresh_token": os.environ["REFRESH_TOKEN"],
                "client_id": os.environ.get("CLIENT_ID"),
                "client_secret": os.environ.get("CLIENT_SECRET")}).json()["access_token"]
            return requests.get(api, params={"part": "statistics", "id": CHANNEL_ID}, timeout=15,
                                headers={"Authorization": f"Bearer {tok}"})
        attempts.append(("YouTube API", oauth))
    if os.environ.get("YOUTUBE_API_KEY"):
        attempts.append(("API key", lambda: requests.get(api, timeout=15, params={
            "part": "statistics", "id": CHANNEL_ID, "key": os.environ["YOUTUBE_API_KEY"]})))
    attempts.append(("channel page", lambda: requests.get(
        f"https://www.youtube.com/channel/{CHANNEL_ID}", timeout=15,
        headers={"User-Agent": "Mozilla/5.0", "Accept-Language": "en-US,en"},
        cookies={"CONSENT": "YES+1"})))
    for name, call in attempts:
        try:
            r = call()
            if "googleapis" in r.url:
                r.raise_for_status()
                count = int(r.json()["items"][0]["statistics"]["subscriberCount"])
            else:
                m = re.search(r'"([\d.,]+)\s*([KM]?) subscribers"', r.text)
                if not m:
                    raise ValueError("count not found on the page")
                count = int(float(m.group(1).replace(",", "")) *
                            {"": 1, "K": 1000, "M": 1000000}[m.group(2)])
            print(f"👥 Subscribers: {count} (via {name})")
            _subscriber_count = count
            return count
        except Exception as e:
            print(f"⚠️  Subscriber count via {name} failed: {str(e)[:120]}")
    return None


def subscriber_goal():
    """Current subscribers + 10, rounded up to the next 10 (267 → 280)."""
    count = get_subscriber_count()
    return None if count is None else -(-(count + 10) // 10) * 10


if __name__ == "__main__":
    print("Goal:", subscriber_goal())
