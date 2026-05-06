"""
quote_status.py
─────────────────────────────────────────────────────────────
Manages posted/pending status for default quotes.

Status is stored DIRECTLY in quotes.py (the "status" and "posted_at"
fields on each quote dict) — no separate JSON file needed.

How it works:
  - Reads DEFAULT_QUOTES from quotes.py at runtime (in-memory)
  - Persists changes by rewriting the quotes.py file with updated
    status/posted_at values using a safe write-then-replace strategy

Public API
──────────
  get_next_quote()        → (id, text, author) | raises RuntimeError if all posted
  is_posted(quote_id)     → bool — True if the quote is already posted
  mark_posted(quote_id)   → updates status="posted" + posted_at in quotes.py
  reset_all()             → resets every quote back to pending in quotes.py
  show_status()           → prints a formatted summary table to stdout
─────────────────────────────────────────────────────────────
"""

import os
import re
import datetime
import quotes as _quotes_module   # imported as module so we can reload it


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

QUOTES_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quotes.py")


def _get_quotes():
    """
    Return a fresh copy of DEFAULT_QUOTES by reloading the quotes module.
    This ensures we always see the latest on-disk state.
    """
    import importlib
    importlib.reload(_quotes_module)
    return _quotes_module.DEFAULT_QUOTES


def _patch_quote_in_file(quote_id: int, new_status: str, new_posted_at) -> None:
    """
    Update status and posted_at for a single quote by rewriting quotes.py.

    Approach: load DEFAULT_QUOTES via importlib, mutate the target entry
    in-memory, then regenerate the entire quotes.py file from scratch.
    This is 100% reliable — no regex ID collision, no line-scanning fragility.
    """
    import importlib
    importlib.reload(_quotes_module)
    quotes = list(_quotes_module.DEFAULT_QUOTES)   # fresh copy

    # Find and update the target quote
    found = False
    for q in quotes:
        if q["id"] == quote_id:
            q["status"]    = new_status
            q["posted_at"] = new_posted_at
            found = True
            break

    if not found:
        raise ValueError(f"Quote id={quote_id} not found in DEFAULT_QUOTES")

    # Regenerate quotes.py content
    lines = []
    lines.append('"""\n')
    lines.append('quotes.py\n')
    lines.append('─────────────────────────────────────────────────────────────\n')
    lines.append('Central store for all default quotes used by the YouTube Shorts bot.\n')
    lines.append('\n')
    lines.append('Each entry is a dict with these fields:\n')
    lines.append('  {\n')
    lines.append('    "id"        : unique int  (never reuse / reorder),\n')
    lines.append('    "text"      : the quote string,\n')
    lines.append('    "author"    : speaker name,\n')
    lines.append('    "status"    : "pending" | "posted"   ← updated by quote_status.py after upload\n')
    lines.append('    "posted_at" : ISO-8601 UTC string, or None\n')
    lines.append('  }\n')
    lines.append('\n')
    lines.append('quote_status.py reads and writes the "status" / "posted_at" fields\n')
    lines.append('directly in this file so everything stays in one place — no separate JSON needed.\n')
    lines.append('\n')
    lines.append('To add a new quote: append a new dict with a unique id,\n')
    lines.append('status="pending", and posted_at=None.\n')
    lines.append('─────────────────────────────────────────────────────────────\n')
    lines.append('"""\n')
    lines.append('\n')
    lines.append('DEFAULT_QUOTES = [\n')

    for q in quotes:
        posted_at_val = f'"{q["posted_at"]}"' if q["posted_at"] else "None"
        # Escape any backslashes or quotes in text/author
        text   = q["text"].replace('\\', '\\\\').replace('"', '\\"')
        author = q["author"].replace('\\', '\\\\').replace('"', '\\"')

        lines.append('    {\n')
        lines.append(f'        "id": {q["id"]},\n')
        lines.append(f'        "text": "{text}",\n')
        lines.append(f'        "author": "{author}",\n')
        lines.append(f'        "status": "{q["status"]}",\n')
        lines.append(f'        "posted_at": {posted_at_val},\n')
        lines.append('    },\n')

    lines.append(']\n')

    # Safe atomic write: .tmp → rename
    tmp_path = QUOTES_FILE + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as fh:
        fh.writelines(lines)
    os.replace(tmp_path, QUOTES_FILE)


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def is_posted(quote_id: int) -> bool:
    """
    Return True if the quote with this id already has status="posted".
    Used by main.py to guard against double-posting.
    """
    for q in _get_quotes():
        if q["id"] == quote_id:
            return q.get("status") == "posted"
    raise KeyError(f"Quote id={quote_id} not found.")


def get_next_quote() -> tuple:
    """
    Return the first quote whose status == "pending" (lowest id order).

    Returns:
        (quote_id: int, text: str, author: str)

    Raises:
        RuntimeError – if every quote has status="posted".
                       Caller should call reset_all() to cycle.
    """
    for q in _get_quotes():
        if q.get("status", "pending") == "pending":
            print(f"📌 Next quote [id={q['id']}]: \"{q['text'][:60]}...\"  — {q['author']}")
            return q["id"], q["text"], q["author"]

    raise RuntimeError(
        "🚫 All quotes have been posted!\n"
        "   Call reset_all() to cycle back to the beginning."
    )


def mark_posted(quote_id: int) -> None:
    """
    Set status="posted" and record the UTC timestamp for the given quote.
    Writes the change directly into quotes.py.

    Args:
        quote_id: the integer id from DEFAULT_QUOTES
    """
    # Safety check — don't overwrite an already-posted entry
    if is_posted(quote_id):
        print(f"⚠️  Quote id={quote_id} is already marked as posted — skipping.")
        return

    timestamp = datetime.datetime.utcnow().isoformat(timespec="seconds")
    _patch_quote_in_file(quote_id, new_status="posted", new_posted_at=timestamp)
    print(f"✅ Quote id={quote_id} marked as POSTED at {timestamp} UTC  (quotes.py updated)")


def reset_all() -> None:
    """
    Reset every quote back to status="pending" with posted_at=None.
    Rewrites quotes.py for all entries.
    """
    quotes = _get_quotes()
    print(f"🔄 Resetting {len(quotes)} quotes to pending...")
    for q in quotes:
        _patch_quote_in_file(q["id"], new_status="pending", new_posted_at=None)
    print("✅ All quotes reset to pending in quotes.py")


def show_status() -> None:
    """
    Print a formatted summary table of all quote statuses to stdout,
    reading directly from quotes.py.
    """
    quotes  = _get_quotes()
    total   = len(quotes)
    posted  = sum(1 for q in quotes if q.get("status") == "posted")
    pending = total - posted

    print("\n" + "─" * 78)
    print(f"  QUOTE STATUS  │  Total: {total}   ✅ Posted: {posted}   ⏳ Pending: {pending}")
    print("─" * 78)
    print(f"  {'Icon':<4} {'ID':>4}  {'Status':<8}  {'Posted At':<22}  {'Author':<20}  Quote")
    print("─" * 78)
    for q in quotes:
        st      = q.get("status", "pending")
        at      = q.get("posted_at") or "—"
        icon    = "✅" if st == "posted" else "⏳"
        excerpt = q["text"][:40] + ("…" if len(q["text"]) > 40 else "")
        print(f"  {icon}   [{q['id']:>3}]  {st:<8}  {at:<22}  {q['author']:<20}  \"{excerpt}\"")
    print("─" * 78 + "\n")
