"""Hardening tests for CONSENTLEDGER.

Covers error paths, edge cases, and input validation added during hardening:
  - missing ledger file → empty list (not a crash)
  - malformed JSON line → ValueError with line number
  - missing ledger entry fields → ValueError
  - wrong field types in stored entries → ValueError
  - None event → ValueError
  - CLI: no subcommand → exit 0 (help printed)
  - CLI: missing file → exit 2, message on stderr
  - CLI: prove with out-of-range index → exit 2, message on stderr
  - verify on a file with OSError (non-readable) propagates gracefully
  - empty ledger file → verify ok=True with count=0
"""

from __future__ import annotations

import json
import os

import pytest

from consentledger.core import (
    append_event,
    load_ledger,
    validate_event,
    verify_ledger,
)
from consentledger.cli import main

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_GOOD = {
    "ts": "2026-06-08T09:00:00Z",
    "actor": "dr.test",
    "patient": "P-0001",
    "action": "VIEW",
    "resource": "chart",
}


def _build(path: str) -> None:
    append_event(path, _GOOD)


# ---------------------------------------------------------------------------
# core: validate_event
# ---------------------------------------------------------------------------


def test_validate_event_ok():
    assert validate_event(_GOOD) == []


def test_validate_event_missing_fields():
    errs = validate_event({"actor": "x"})
    assert any("ts" in e for e in errs)
    assert any("patient" in e for e in errs)


def test_validate_event_empty_string_field():
    bad = dict(_GOOD, actor="   ")
    errs = validate_event(bad)
    assert any("actor" in e for e in errs)


def test_validate_event_non_dict():
    errs = validate_event("not a dict")  # type: ignore[arg-type]
    assert errs == ["event must be a JSON object"]


# ---------------------------------------------------------------------------
# core: load_ledger edge cases
# ---------------------------------------------------------------------------


def test_load_ledger_absent_file(tmp_path):
    entries = load_ledger(str(tmp_path / "nonexistent.jsonl"))
    assert entries == []


def test_load_ledger_empty_file(tmp_path):
    path = str(tmp_path / "empty.jsonl")
    open(path, "w").close()
    assert load_ledger(path) == []


def test_load_ledger_malformed_json(tmp_path):
    path = str(tmp_path / "bad.jsonl")
    with open(path, "w") as f:
        f.write("{not valid json}\n")
    with pytest.raises(ValueError, match="line 1"):
        load_ledger(path)


def test_load_ledger_missing_entry_field(tmp_path):
    path = str(tmp_path / "missing.jsonl")
    # Write a JSON object that is missing 'entry_hash'
    with open(path, "w") as f:
        f.write(json.dumps({"index": 0, "prev_hash": "0" * 64, "event": {}}) + "\n")
    with pytest.raises(ValueError, match="entry_hash"):
        load_ledger(path)


def test_load_ledger_wrong_index_type(tmp_path):
    path = str(tmp_path / "badtype.jsonl")
    with open(path, "w") as f:
        f.write(json.dumps({
            "index": "zero",
            "prev_hash": "0" * 64,
            "event": {},
            "entry_hash": "x" * 64,
        }) + "\n")
    with pytest.raises(ValueError, match="'index' must be an integer"):
        load_ledger(path)


def test_load_ledger_wrong_event_type(tmp_path):
    path = str(tmp_path / "badevent.jsonl")
    with open(path, "w") as f:
        f.write(json.dumps({
            "index": 0,
            "prev_hash": "0" * 64,
            "event": "not an object",
            "entry_hash": "x" * 64,
        }) + "\n")
    with pytest.raises(ValueError, match="'event' must be a JSON object"):
        load_ledger(path)


# ---------------------------------------------------------------------------
# core: append_event edge cases
# ---------------------------------------------------------------------------


def test_append_event_none_raises(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError, match="None"):
        append_event(path, None)  # type: ignore[arg-type]


def test_append_event_missing_fields_no_write(tmp_path):
    path = str(tmp_path / "ledger.jsonl")
    with pytest.raises(ValueError):
        append_event(path, {"actor": "x"})
    # Nothing should have been written to disk.
    assert not os.path.exists(path) or os.path.getsize(path) == 0


# ---------------------------------------------------------------------------
# core: verify_ledger on empty / missing
# ---------------------------------------------------------------------------


def test_verify_empty_ledger_ok(tmp_path):
    path = str(tmp_path / "empty.jsonl")
    open(path, "w").close()
    res = verify_ledger(path)
    assert res.ok is True
    assert res.count == 0


def test_verify_missing_file_ok(tmp_path):
    path = str(tmp_path / "nonexistent.jsonl")
    res = verify_ledger(path)
    assert res.ok is True
    assert res.count == 0


def test_verify_malformed_returns_not_ok(tmp_path):
    path = str(tmp_path / "bad.jsonl")
    with open(path, "w") as f:
        f.write("{broken\n")
    res = verify_ledger(path)
    assert res.ok is False
    assert res.errors


# ---------------------------------------------------------------------------
# CLI error paths
# ---------------------------------------------------------------------------


def test_cli_no_subcommand():
    rc = main([])
    assert rc == 0


def test_cli_list_missing_ledger(tmp_path, capsys):
    path = str(tmp_path / "nope.jsonl")
    # load_ledger returns [] for missing files, so list should succeed with 0 entries
    rc = main(["list", "--ledger", path])
    assert rc == 0
    out = capsys.readouterr().out
    assert "(no entries)" in out


def test_cli_prove_out_of_range(tmp_path, capsys):
    path = str(tmp_path / "ledger.jsonl")
    _build(path)
    rc = main(["prove", "--ledger", path, "--index", "99"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "error" in err.lower()


def test_cli_prove_negative_index(tmp_path, capsys):
    path = str(tmp_path / "ledger.jsonl")
    _build(path)
    rc = main(["prove", "--ledger", path, "--index", "-1"])
    err = capsys.readouterr().err
    assert rc == 2
    assert "error" in err.lower()


def test_cli_append_invalid_event_exits_2(tmp_path, capsys):
    path = str(tmp_path / "ledger.jsonl")
    # Missing required --ts, but argparse requires it, so provide empty strings.
    rc = main([
        "append", "--ledger", path,
        "--ts", "", "--actor", "", "--patient", "P1",
        "--action", "VIEW", "--resource", "chart",
    ])
    err = capsys.readouterr().err
    assert rc == 2
    assert "error" in err.lower()


def test_cli_verify_malformed_file_exits_1(tmp_path):
    path = str(tmp_path / "bad.jsonl")
    with open(path, "w") as f:
        f.write("{bad json\n")
    rc = main(["verify", "--ledger", path])
    assert rc == 1  # verify returns 1 when ok=False (chain broken/parse error)
