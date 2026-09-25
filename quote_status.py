"""
quote_status.py
─────────────────────────────────────────────────────────────
Manages posted/pending status for default quotes.

Status is stored DIRECTLY in the quote files (the "status" and "posted_at"
fields on each quote dict) — no separate JSON file needed.

One file per content stream:
  "en"       → quotes.py      (English sports quotes)
  "ml"       → quotes_ml.py   (Malayalam sports quotes)
  "ml_facts" → facts_ml.py    (Malayalam facts: space, aliens, surprising facts)

How it works:
  - Reads DEFAULT_QUOTES from the language's file at runtime
  - Persists changes by rewriting that file with updated
    status/posted_at values using a safe write-then-replace strategy

Public API   (every function takes lang="en" | "ml" | "ml_facts", default "en")
──────────
  get_next_quote(lang)        → quote dict | raises RuntimeError if all posted
  get_quote_by_id(id, lang)   → that quote dict | raises RuntimeError if missing/posted
  is_posted(quote_id, lang)   → bool — True if the quote is already posted
  mark_posted(quote_id, lang) → updates status="posted" + posted_at
  reset_all(lang)             → resets every quote back to pending
  last_posted_at(lang)        → most recent posted_at string, or "" if none
  pending_count(lang)         → number of quotes still pending
  get_pending(lang)           → list of pending quote dicts (file order)
  show_status(lang)           → prints a formatted summary table to stdout
─────────────────────────────────────────────────────────────
"""

import os
import datetime
import importlib


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

LANGUAGES = {
    "en":       {"module": "quotes",    "name": "English"},
    "ml":       {"module": "quotes_ml", "name": "Malayalam"},
    "ml_facts": {"module": "facts_ml",  "name": "Malayalam facts"},
}


def quotes_file(lang: str = "en") -> str:
    return os.path.join(BASE_DIR, LANGUAGES[lang]["module"] + ".py")


def _get_quotes(lang: str = "en") -> list:
    """
    Return DEFAULT_QUOTES for a language, reloaded so we always see the
    latest on-disk state.
    """
    module = importlib.import_module(LANGUAGES[lang]["module"])
    importlib.reload(module)
    return module.DEFAULT_QUOTES


def _py_str(value: str) -> str:
    """Double-quoted Python string literal (escapes backslashes and quotes)."""
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _write_quotes(quotes: list, lang: str = "en") -> None:
    """
    Regenerate the entire quote file from a list of quote dicts.
    This is 100% reliable — no regex ID collision, no line-scanning fragility.
    """
    path     = quotes_file(lang)
    filename = os.path.basename(path)
    language = LANGUAGES[lang]["name"]

    lines = []
    lines.append('"""\n')
    lines.append(f'{filename}\n')
    lines.append('─────────────────────────────────────────────────────────────\n')
    if lang == "ml_facts":
        lines.append('Central store for all Malayalam facts used by the YouTube Shorts bot.\n')
        lines.append('\n')
        lines.append('Each entry is a dict with these fields:\n')
        lines.append('  {\n')
        lines.append('    "id"        : unique int  (never reuse / reorder),\n')
        lines.append('    "text"      : the fact in Malayalam (spoken + shown as captions),\n')
        lines.append('    "topic"     : "space" | "aliens" | "animals" | "body" | "earth"\n')
        lines.append('                  (picks the on-screen label and fallback footage),\n')
        lines.append('    "footage"   : English Pexels search term for this fact\'s background video,\n')
    else:
        lines.append(f'Central store for all {language} quotes used by the YouTube Shorts bot.\n')
        lines.append('\n')
        lines.append('Each entry is a dict with these fields:\n')
        lines.append('  {\n')
        lines.append('    "id"        : unique int  (never reuse / reorder),\n')
        lines.append('    "text"      : the quote string,\n')
        lines.append('    "author"    : speaker name in English (used for footage, voice and hashtags),\n')
        if lang != "en":
            lines.append(f'    "author_{lang}" : speaker name in {language} (spoken + shown on screen),\n')
    lines.append('    "status"    : "pending" | "posted"   ← updated by quote_status.py after upload\n')
    lines.append('    "posted_at" : ISO-8601 UTC string, or None\n')
    lines.append('  }\n')
    lines.append('\n')
    lines.append('quote_status.py reads and writes the "status" / "posted_at" fields\n')
    lines.append('directly in this file so everything stays in one place — no separate JSON needed.\n')
    lines.append('\n')
    noun = "fact" if lang == "ml_facts" else "quote"
    lines.append(f'To add a new {noun}: append a new dict with a unique id,\n')
    lines.append('status="pending", and posted_at=None.\n')
    lines.append(f'{noun.capitalize()}s are never re-posted: once every {noun} is posted the bot stops\n')
    lines.append(f'with an error until new {noun}s are added here.\n')
    lines.append('─────────────────────────────────────────────────────────────\n')
    lines.append('"""\n')
    lines.append('\n')
    lines.append('DEFAULT_QUOTES = [\n')

    for q in quotes:
        lines.append('    {\n')
        lines.append(f'        "id": {q["id"]},\n')
        for key in q:
            if key not in ("id", "status", "posted_at"):
                lines.append(f'        "{key}": {_py_str(q[key])},\n')
        lines.append(f'        "status": "{q["status"]}",\n')
        posted_at_val = _py_str(q["posted_at"]) if q["posted_at"] else "None"
        lines.append(f'        "posted_at": {posted_at_val},\n')
        lines.append('    },\n')

    lines.append(']\n')

    # Safe atomic write: .tmp → rename
    tmp_path = path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    os.replace(tmp_path, path)


def _patch_quote_in_file(quote_id: int, new_status: str, new_posted_at, lang: str = "en") -> None:
    """
    Update status and posted_at for a single quote by rewriting its file.
    """
    quotes = [dict(q) for q in _get_quotes(lang)]   # fresh copy

    for q in quotes:
        if q["id"] == quote_id:
            q["status"]    = new_status
            q["posted_at"] = new_posted_at
            break
    else:
        raise ValueError(f"Quote id={quote_id} not found in {quotes_file(lang)}")

    _write_quotes(quotes, lang)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def is_posted(quote_id: int, lang: str = "en") -> bool:
    """
    Return True if the quote with this id already has status="posted".
    """
    for q in _get_quotes(lang):
        if q["id"] == quote_id:
            return q.get("status") == "posted"
    raise KeyError(f"Quote id={quote_id} not found.")


def get_next_quote(lang: str = "en") -> dict:
    """
    Return a copy of the first quote whose status == "pending" (file order).

    Raises:
        RuntimeError – if every quote has status="posted".
    """
    for q in _get_quotes(lang):
        if q.get("status", "pending") == "pending":
            print(f"📌 Next {LANGUAGES[lang]['name']} entry [id={q['id']}]: \"{q['text'][:60]}...\"  — {_byline(q)}")
            return dict(q)

    raise RuntimeError(
        f"🚫 All {LANGUAGES[lang]['name']} quotes have been posted!\n"
        f"   Add new quotes to {os.path.basename(quotes_file(lang))} — re-posting old ones\n"
        "   gets the channel flagged as repetitive content."
    )


def _byline(q: dict) -> str:
    """Author for quotes, topic for facts."""
    return q.get("author") or q.get("topic", "")


def get_quote_by_id(quote_id: int, lang: str = "en") -> dict:
    """Return a copy of one specific pending entry (for posting a chosen quote/fact)."""
    for q in _get_quotes(lang):
        if q["id"] == quote_id:
            if q.get("status") == "posted":
                raise RuntimeError(f"🚫 {LANGUAGES[lang]['name']} id={quote_id} is already posted.")
            print(f"📌 Chosen {LANGUAGES[lang]['name']} entry [id={q['id']}]: \"{q['text'][:60]}...\"  — {_byline(q)}")
            return dict(q)
    raise RuntimeError(f"🚫 {LANGUAGES[lang]['name']} id={quote_id} not found.")


def get_pending(lang: str = "en") -> list:
    return [dict(q) for q in _get_quotes(lang) if q.get("status", "pending") == "pending"]


def pending_count(lang: str = "en") -> int:
    return sum(1 for q in _get_quotes(lang) if q.get("status", "pending") == "pending")


def last_posted_at(lang: str = "en") -> str:
    """Most recent posted_at for a language ("" if nothing posted yet)."""
    return max((q.get("posted_at") or "" for q in _get_quotes(lang)), default="")


def mark_posted(quote_id: int, lang: str = "en") -> None:
    """
    Set status="posted" and record the UTC timestamp for the given quote.
    Writes the change directly into the language's quote file.
    """
    # Safety check — don't overwrite an already-posted entry
    if is_posted(quote_id, lang):
        print(f"⚠️  Quote id={quote_id} is already marked as posted — skipping.")
        return

    timestamp = datetime.datetime.now(datetime.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
    _patch_quote_in_file(quote_id, new_status="posted", new_posted_at=timestamp, lang=lang)
    print(f"✅ Quote id={quote_id} marked as POSTED at {timestamp} UTC  ({os.path.basename(quotes_file(lang))} updated)")


def reset_all(lang: str = "en") -> None:
    """
    Reset every quote back to status="pending" with posted_at=None.
    """
    quotes = [dict(q) for q in _get_quotes(lang)]
    print(f"🔄 Resetting {len(quotes)} {LANGUAGES[lang]['name']} quotes to pending...")
    for q in quotes:
        q["status"], q["posted_at"] = "pending", None
    _write_quotes(quotes, lang)
    print(f"✅ All quotes reset to pending in {os.path.basename(quotes_file(lang))}")


def show_status(lang: str = "en") -> None:
    """
    Print a formatted summary table of all quote statuses to stdout.
    """
    quotes  = _get_quotes(lang)
    total   = len(quotes)
    posted  = sum(1 for q in quotes if q.get("status") == "posted")
    pending = total - posted

    print("\n" + "─" * 78)
    print(f"  {LANGUAGES[lang]['name'].upper()}  │  Total: {total}   ✅ Posted: {posted}   ⏳ Pending: {pending}")
    print("─" * 78)
    print(f"  {'Icon':<4} {'ID':>4}  {'Status':<8}  {'Posted At':<22}  {'Author/Topic':<20}  Text")
    print("─" * 78)
    for q in quotes:
        st      = q.get("status", "pending")
        at      = q.get("posted_at") or "—"
        icon    = "✅" if st == "posted" else "⏳"
        excerpt = q["text"][:40] + ("…" if len(q["text"]) > 40 else "")
        print(f"  {icon}   [{q['id']:>3}]  {st:<8}  {at:<22}  {_byline(q):<20}  \"{excerpt}\"")
    print("─" * 78 + "\n")
