"""
quote_status.py
─────────────────────────────────────────────────────────────
Manages posted/pending status for default quotes.

Status is persisted in  quotes_status.json  (created automatically).

Schema of quotes_status.json:
  {
    "1":  { "status": "posted",  "posted_at": "2025-07-01T10:23:00" },
    "2":  { "status": "pending", "posted_at": null },
    ...
  }

Public API
──────────
  get_next_quote()        → (id, text, author) | raises RuntimeError if all posted
  mark_posted(quote_id)   → writes "posted" + timestamp to JSON
  reset_all()             → resets every quote back to "pending" (for cycling)
  show_status()           → prints a summary table to stdout
"""

import json
import os
import datetime
from quotes import DEFAULT_QUOTES

STATUS_FILE = "quotes_status.json"


# ─────────────────────────────────────────────
# Internal helpers
# ─────────────────────────────────────────────

def _load_status() -> dict:
    """Load status JSON, creating it (all pending) if it doesn't exist."""
    if not os.path.exists(STATUS_FILE):
        return _create_fresh_status()
    with open(STATUS_FILE, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    # If new quotes were added to quotes.py that aren't yet in the JSON, add them
    changed = False
    for q in DEFAULT_QUOTES:
        key = str(q["id"])
        if key not in data:
            data[key] = {"status": "pending", "posted_at": None}
            changed = True
    if changed:
        _save_status(data)
    return data


def _save_status(data: dict) -> None:
    """Write status dict to JSON (pretty-printed for readability)."""
    with open(STATUS_FILE, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)


def _create_fresh_status() -> dict:
    """Build a brand-new status dict with every quote set to pending."""
    data = {}
    for q in DEFAULT_QUOTES:
        data[str(q["id"])] = {"status": "pending", "posted_at": None}
    _save_status(data)
    print(f"📋 Created fresh '{STATUS_FILE}' with {len(data)} quotes (all pending).")
    return data


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def get_next_quote() -> tuple:
    """
    Return the first pending quote (lowest id order).

    Returns:
        (quote_id: int, text: str, author: str)

    Raises:
        RuntimeError – if every quote has already been posted.
                       Caller should call reset_all() to cycle.
    """
    status = _load_status()

    for q in DEFAULT_QUOTES:          # respects insertion order (id order)
        key = str(q["id"])
        if status.get(key, {}).get("status") == "pending":
            print(f"📌 Next quote  [id={q['id']}]: \"{q['text'][:60]}...\"  — {q['author']}")
            return q["id"], q["text"], q["author"]

    raise RuntimeError(
        "🚫 All quotes have been posted!\n"
        "   Call reset_all() in quote_status.py to cycle back to the beginning."
    )


def mark_posted(quote_id: int) -> None:
    """
    Mark a quote as posted and record the UTC timestamp.

    Args:
        quote_id: the integer id from DEFAULT_QUOTES
    """
    status = _load_status()
    key    = str(quote_id)
    if key not in status:
        raise KeyError(f"Quote id {quote_id} not found in status file.")

    status[key]["status"]    = "posted"
    status[key]["posted_at"] = datetime.datetime.utcnow().isoformat(timespec="seconds")
    _save_status(status)
    print(f"✅ Quote id={quote_id} marked as POSTED at {status[key]['posted_at']} UTC")


def reset_all() -> None:
    """
    Reset every quote back to pending (clears posted_at).
    Use this to cycle through all quotes again after all are posted.
    """
    data = _create_fresh_status()
    print(f"🔄 Reset complete — {len(data)} quotes back to pending.")


def show_status() -> None:
    """Print a formatted summary of all quote statuses to stdout."""
    status = _load_status()
    total   = len(DEFAULT_QUOTES)
    posted  = sum(1 for v in status.values() if v["status"] == "posted")
    pending = total - posted

    print("\n" + "─" * 72)
    print(f"  QUOTE STATUS  │  Total: {total}   Posted: {posted}   Pending: {pending}")
    print("─" * 72)
    for q in DEFAULT_QUOTES:
        key  = str(q["id"])
        info = status.get(key, {})
        st   = info.get("status", "pending")
        at   = info.get("posted_at") or "—"
        icon = "✅" if st == "posted" else "⏳"
        excerpt = q["text"][:45] + ("…" if len(q["text"]) > 45 else "")
        print(f"  {icon} [{q['id']:>3}]  {st:<8}  {at:<20}  {q['author']:<20}  \"{excerpt}\"")
    print("─" * 72 + "\n")
