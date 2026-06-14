"""Core engine for CONSENTLEDGER.

The ledger is an append-only JSON Lines file. Each line is a `LedgerEntry`
record with the shape::

    {
      "index": 0,
      "prev_hash": "<hex sha256 of previous entry, or GENESIS_HASH for entry 0>",
      "event": { ... domain payload (access/consent event) ... },
      "entry_hash": "<hex sha256 over index|prev_hash|canonical(event)>"
    }

The `entry_hash` of each record is computed over its index, the previous
entry's hash, and a canonical (sorted-key, separator-stable) JSON encoding of
the event payload. Because every record commits to the hash of the one before
it, tampering with any historical event — editing a field, deleting a row,
reordering rows, or inserting a forged row — breaks the chain at the point of
the change and is detected by `verify_ledger`.

A HIPAA-style consent/access event has at minimum:
  - ts:        ISO-8601 timestamp of the event
  - actor:     who performed the action (user/clinician id)
  - patient:   patient identifier (or pseudonym)
  - action:    e.g. VIEW, EXPORT, GRANT_CONSENT, REVOKE_CONSENT, MODIFY
  - resource:  what was touched (e.g. "chart", "labs", "consent:research")

Extra keys are preserved verbatim and included in the hash.
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

# Hash placed in the prev_hash slot of the very first (genesis) entry.
GENESIS_HASH = "0" * 64

# Required keys for a well-formed consent/access event.
REQUIRED_EVENT_KEYS = ("ts", "actor", "patient", "action", "resource")


@dataclass
class LedgerEntry:
    """A single hash-chained record in the ledger."""

    index: int
    prev_hash: str
    event: Dict[str, Any]
    entry_hash: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "index": self.index,
            "prev_hash": self.prev_hash,
            "event": self.event,
            "entry_hash": self.entry_hash,
        }

    def to_json(self) -> str:
        # Compact, deterministic on-disk representation (one entry per line).
        return json.dumps(self.to_dict(), sort_keys=True, separators=(",", ":"))


@dataclass
class VerifyResult:
    """Outcome of verifying a ledger."""

    ok: bool
    count: int
    head_hash: str
    errors: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ok": self.ok,
            "count": self.count,
            "head_hash": self.head_hash,
            "errors": self.errors,
        }


def canonical_event(event: Dict[str, Any]) -> str:
    """Deterministic canonical JSON encoding of an event payload.

    Sorted keys + stable separators so the same logical event always hashes
    identically regardless of key insertion order or incidental whitespace.
    """
    return json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def compute_entry_hash(index: int, prev_hash: str, event: Dict[str, Any]) -> str:
    """Compute the sha256 entry hash binding index + prev_hash + event."""
    h = hashlib.sha256()
    h.update(str(index).encode("utf-8"))
    h.update(b"|")
    h.update(prev_hash.encode("utf-8"))
    h.update(b"|")
    h.update(canonical_event(event).encode("utf-8"))
    return h.hexdigest()


def validate_event(event: Dict[str, Any]) -> List[str]:
    """Return a list of human-readable problems with an event payload."""
    problems: List[str] = []
    if not isinstance(event, dict):
        return ["event must be a JSON object"]
    for k in REQUIRED_EVENT_KEYS:
        if k not in event:
            problems.append(f"missing required field '{k}'")
        elif not isinstance(event[k], str) or not event[k].strip():
            problems.append(f"field '{k}' must be a non-empty string")
    return problems


def _read_lines(path: str) -> Iterator[Tuple[int, str]]:
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for lineno, raw in enumerate(fh, start=1):
                stripped = raw.strip()
                if stripped:
                    yield lineno, stripped
    except OSError as exc:
        raise OSError(f"cannot read ledger file {path!r}: {exc}") from exc


def load_ledger(path: str) -> List[LedgerEntry]:
    """Load all entries from a ledger file. Returns [] if file is absent.

    Raises ValueError on a line that is not valid JSON or not a ledger entry.
    Raises OSError if the file exists but cannot be read.
    """
    if not os.path.exists(path):
        return []
    entries: List[LedgerEntry] = []
    for lineno, line in _read_lines(path):
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"line {lineno}: invalid JSON ({exc})") from exc
        if not isinstance(obj, dict):
            raise ValueError(
                f"line {lineno}: expected a JSON object, got {type(obj).__name__}"
            )
        for k in ("index", "prev_hash", "event", "entry_hash"):
            if k not in obj:
                raise ValueError(f"line {lineno}: ledger entry missing '{k}'")
        if not isinstance(obj["index"], int):
            got = type(obj["index"]).__name__
            raise ValueError(
                f"line {lineno}: 'index' must be an integer, got {got}"
            )
        if not isinstance(obj["prev_hash"], str):
            raise ValueError(
                f"line {lineno}: 'prev_hash' must be a string"
            )
        if not isinstance(obj["entry_hash"], str):
            raise ValueError(
                f"line {lineno}: 'entry_hash' must be a string"
            )
        if not isinstance(obj["event"], dict):
            raise ValueError(
                f"line {lineno}: 'event' must be a JSON object"
            )
        entries.append(
            LedgerEntry(
                index=obj["index"],
                prev_hash=obj["prev_hash"],
                event=obj["event"],
                entry_hash=obj["entry_hash"],
            )
        )
    return entries


def head_hash(path: str) -> str:
    """Return the entry_hash of the last entry, or GENESIS_HASH if empty."""
    entries = load_ledger(path)
    return entries[-1].entry_hash if entries else GENESIS_HASH


def append_event(
    path: str, event: Dict[str, Any], *, strict: bool = True
) -> LedgerEntry:
    """Validate, chain, and append an event to the ledger file.

    With strict=True (default) a malformed event (missing required HIPAA audit
    fields) raises ValueError before anything is written.
    Raises OSError if the file cannot be opened for writing.
    """
    if event is None:
        raise ValueError("event must not be None")
    if strict:
        problems = validate_event(event)
        if problems:
            raise ValueError("invalid event: " + "; ".join(problems))

    entries = load_ledger(path)
    index = len(entries)
    prev = entries[-1].entry_hash if entries else GENESIS_HASH
    entry_hash = compute_entry_hash(index, prev, event)
    entry = LedgerEntry(index=index, prev_hash=prev, event=event, entry_hash=entry_hash)

    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
    except OSError as exc:
        raise OSError(f"cannot write to ledger file {path!r}: {exc}") from exc
    return entry


def verify_ledger(path: str) -> VerifyResult:
    """Verify the integrity of the entire hash chain.

    Checks, in order, for every entry:
      * index is sequential starting at 0
      * prev_hash matches the actual hash of the prior entry (genesis for #0)
      * entry_hash recomputes to the stored value (no payload tampering)

    Returns a VerifyResult; `ok` is False if any error is found.
    """
    try:
        entries = load_ledger(path)
    except (ValueError, OSError) as exc:
        return VerifyResult(
            ok=False,
            count=0,
            head_hash=GENESIS_HASH,
            errors=[{"index": None, "problem": str(exc)}],
        )

    errors: List[Dict[str, Any]] = []
    prev_hash = GENESIS_HASH

    for i, entry in enumerate(entries):
        if entry.index != i:
            errors.append({
                "index": i,
                "problem": (
                    f"index out of sequence: stored {entry.index!r}, expected {i}"
                ),
            })
        if entry.prev_hash != prev_hash:
            errors.append({
                "index": i,
                "problem": "broken chain: prev_hash does not match prior entry",
                "expected": prev_hash,
                "stored": entry.prev_hash,
            })
        recomputed = compute_entry_hash(entry.index, entry.prev_hash, entry.event)
        if recomputed != entry.entry_hash:
            errors.append({
                "index": i,
                "problem": "tampered entry: entry_hash does not match contents",
                "expected": recomputed,
                "stored": entry.entry_hash,
            })
        # Chain forward using the stored hash so a single break does not
        # cascade into spurious errors on every later row.
        prev_hash = entry.entry_hash

    head = entries[-1].entry_hash if entries else GENESIS_HASH
    return VerifyResult(
        ok=not errors, count=len(entries), head_hash=head, errors=errors
    )


def inclusion_proof(path: str, index: int) -> Dict[str, Any]:
    """Return a minimal inclusion record proving entry `index` is in the chain.

    The proof is the entry plus the hash linkage needed to recompute and
    confirm its place: callers recompute compute_entry_hash(index, prev_hash,
    event) and check it equals entry_hash, then check the next entry (if any)
    commits to that hash via its prev_hash.
    """
    entries = load_ledger(path)
    if index < 0 or index >= len(entries):
        raise IndexError(f"no entry at index {index} (ledger has {len(entries)})")
    entry = entries[index]
    recomputed = compute_entry_hash(entry.index, entry.prev_hash, entry.event)
    next_prev: Optional[str] = (
        entries[index + 1].prev_hash if index + 1 < len(entries) else None
    )
    return {
        "index": index,
        "entry": entry.to_dict(),
        "recomputed_hash": recomputed,
        "hash_matches": recomputed == entry.entry_hash,
        "linked_to_next": (
            (next_prev == entry.entry_hash) if next_prev is not None else None
        ),
        "included": recomputed == entry.entry_hash
        and (next_prev is None or next_prev == entry.entry_hash),
    }
