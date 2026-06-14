"""Command-line interface for CONSENTLEDGER.

Examples
--------
  # Record a patient-data access event
  consentledger append --ledger audit.jsonl \\
      --actor dr.adams --patient P-1001 --action VIEW --resource chart \\
      --ts 2026-06-08T09:15:00Z

  # Record a consent grant with extra metadata
  consentledger append --ledger audit.jsonl \\
      --actor patient.P-1001 --patient P-1001 \\
      --action GRANT_CONSENT --resource consent:research \\
      --meta scope=genomics --meta expires=2027-01-01

  # Verify the whole chain is tamper-free (exit 1 if not) — use in CI
  consentledger verify --ledger audit.jsonl --format json

  # List events as a table
  consentledger list --ledger audit.jsonl

  # Prove a specific entry is included in the chain
  consentledger prove --ledger audit.jsonl --index 0 --format json
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any, Dict, List, Optional

from consentledger import TOOL_NAME, TOOL_VERSION
from consentledger.core import (
    append_event,
    inclusion_proof,
    load_ledger,
    verify_ledger,
)


def _parse_meta(pairs: Optional[List[str]]) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for item in pairs or []:
        if "=" not in item:
            raise SystemExit(f"--meta must be key=value, got {item!r}")
        key, val = item.split("=", 1)
        key = key.strip()
        if not key:
            raise SystemExit(f"--meta key must be non-empty in {item!r}")
        out[key] = val
    return out


def _print(payload: Any, fmt: str) -> None:
    if fmt == "json":
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        _print_table(payload)


def _print_table(payload: Any) -> None:
    if isinstance(payload, list):
        if not payload:
            print("(no entries)")
            return
        cols = ["index", "ts", "actor", "patient", "action", "resource", "entry_hash"]
        rows = []
        for row in payload:
            rows.append([str(row.get(c, "")) for c in cols])
        widths = [len(c) for c in cols]
        for r in rows:
            for i, cell in enumerate(r):
                widths[i] = max(widths[i], len(cell))
        # Truncate hash column for readability.
        def fmt_row(cells: List[str]) -> str:
            out = []
            for i, cell in enumerate(cells):
                if cols[i] == "entry_hash":
                    cell = cell[:12]
                out.append(cell.ljust(min(widths[i], 24)))
            return "  ".join(out)
        print(fmt_row(cols))
        print(fmt_row(["-" * min(widths[i], 24) for i in range(len(cols))]))
        for r in rows:
            print(fmt_row(r))
    elif isinstance(payload, dict):
        for k, v in payload.items():
            if isinstance(v, (dict, list)):
                print(f"{k}: {json.dumps(v)}")
            else:
                print(f"{k}: {v}")
    else:
        print(payload)


def _cmd_append(args: argparse.Namespace) -> int:
    event: Dict[str, Any] = {
        "ts": args.ts,
        "actor": args.actor,
        "patient": args.patient,
        "action": args.action,
        "resource": args.resource,
    }
    event.update(_parse_meta(args.meta))
    try:
        entry = append_event(args.ledger, event)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print(entry.to_dict() if args.format == "json" else {
        "appended": True,
        "index": entry.index,
        "entry_hash": entry.entry_hash,
    }, args.format)
    return 0


def _cmd_list(args: argparse.Namespace) -> int:
    try:
        entries = load_ledger(args.ledger)
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    rows = []
    for e in entries:
        row = {"index": e.index, "entry_hash": e.entry_hash}
        row.update(e.event)
        rows.append(row)
    _print(rows, args.format)
    return 0


def _cmd_verify(args: argparse.Namespace) -> int:
    try:
        result = verify_ledger(args.ledger)
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print(result.to_dict(), args.format)
    if not result.ok:
        # Non-zero exit so CI / HIPAA audit gates fail on tampering.
        return 1
    return 0


def _cmd_prove(args: argparse.Namespace) -> int:
    try:
        proof = inclusion_proof(args.ledger, args.index)
    except (IndexError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    _print(proof, args.format)
    return 0 if proof["included"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description=(
            "Tamper-evident, hash-chained audit log of patient-data access and "
            "consent events (HIPAA audit controls as a verifiable ledger)."
        ),
        epilog=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version", action="version", version=f"{TOOL_NAME} {TOOL_VERSION}"
    )
    parser.add_argument(
        "--format",
        choices=("table", "json"),
        default="table",
        help="output format (default: table; use json for piping/CI)",
    )

    sub = parser.add_subparsers(dest="command", metavar="command")

    p_app = sub.add_parser("append", help="record a new access/consent event")
    p_app.add_argument("--ledger", required=True, help="path to ledger .jsonl file")
    p_app.add_argument("--ts", required=True, help="ISO-8601 event timestamp")
    p_app.add_argument("--actor", required=True, help="who performed the action")
    p_app.add_argument("--patient", required=True, help="patient identifier/pseudonym")
    p_app.add_argument(
        "--action", required=True,
        help="e.g. VIEW, EXPORT, MODIFY, GRANT_CONSENT, REVOKE_CONSENT",
    )
    p_app.add_argument("--resource", required=True, help="resource touched, e.g. chart")
    p_app.add_argument(
        "--meta", action="append", metavar="KEY=VALUE",
        help="extra metadata (repeatable); included in the hash",
    )
    p_app.set_defaults(func=_cmd_append)

    p_list = sub.add_parser("list", help="list recorded events")
    p_list.add_argument("--ledger", required=True, help="path to ledger .jsonl file")
    p_list.set_defaults(func=_cmd_list)

    p_ver = sub.add_parser("verify", help="verify chain integrity (exit 1 if tampered)")
    p_ver.add_argument("--ledger", required=True, help="path to ledger .jsonl file")
    p_ver.set_defaults(func=_cmd_verify)

    p_proof = sub.add_parser("prove", help="prove a single entry is in the chain")
    p_proof.add_argument("--ledger", required=True, help="path to ledger .jsonl file")
    p_proof.add_argument(
        "--index", type=int, required=True, help="entry index (0-based)"
    )
    p_proof.set_defaults(func=_cmd_prove)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\ninterrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"unexpected error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
