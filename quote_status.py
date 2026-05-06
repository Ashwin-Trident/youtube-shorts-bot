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
    Rewrite the quotes.py file in-place, updating only the status and
    posted_at fields for the quote with the given id.

    Uses regex to find the block for this quote and replace just those
    two field values — all other content is preserved exactly.
    """
    with open(QUOTES_FILE, "r", encoding="utf-8") as fh:
        source = fh.read()

    # We need to find the dict block for this specific quote id and patch it.
    # Strategy: locate  "id": <N>,  then within a reasonable window replace
    # the nearest "status": "..." and "posted_at": ... lines.

    # Build the replacement values
    status_val    = f'"{new_status}"'
    posted_at_val = f'"{new_posted_at}"' if new_posted_at else "None"

    # Split into lines for safe, targeted editing
    lines     = source.splitlines(keepends=True)
    id_line   = None

    for i, line in enumerate(lines):
        # Match the id field for this specific quote (word boundary safe)
        if re.search(rf'"id"\s*:\s*{quote_id}\s*,', line):
            id_line = i
            break

    if id_line is None:
        raise ValueError(f"Quote id={quote_id} not found in {QUOTES_FILE}")

    # Scan forward from id_line (max 20 lines) to patch status + posted_at
    patched_status    = False
    patched_posted_at = False

    for j in range(id_line + 1, min(id_line + 20, len(lines))):
        if not patched_status and re.search(r'"status"\s*:', lines[j]):
            lines[j] = re.sub(
                r'("status"\s*:\s*)("pending"|"posted")',
                rf'\g<1>{status_val}',
                lines[j],
            )
            patched_status = True

        if not patched_posted_at and re.search(r'"posted_at"\s*:', lines[j]):
            lines[j] = re.sub(
                r'("posted_at"\s*:\s*)(None|"[^"]*")',
                rf'\g<1>{posted_at_val}',
                lines[j],
            )
            patched_posted_at = True

        if patched_status and patched_posted_at:
            break

    if not patched_status or not patched_posted_at:
        raise RuntimeError(
            f"Could not patch status/posted_at for quote id={quote_id}. "
            "Make sure both fields exist in the quotes.py entry."
        )

    # Safe write: write to .tmp then rename (atomic on most OS)
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
