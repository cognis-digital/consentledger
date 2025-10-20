"""Smoke tests for CONSENTLEDGER.

These import the real core engine, build/verify ledgers, and assert tamper
detection. No network access. The demo `ledger.jsonl` is regenerated from
canonical hashes here so the on-disk demo file always self-verifies.
"""

import json
import os

import pytest

from consentledger import (
    TOOL_NAME,
    TOOL_VERSION,
    GENESIS_HASH,
    append_event,
    compute_entry_hash,
    load_ledger,
    verify_ledger,
    inclusion_proof,
)
from consentledger.cli import main

DEMO_DIR = os.path.join(os.path.dirname(__file__), "..", "demos", "01-basic")
DEMO_LEDGER = os.path.abspath(os.path.join(DEMO_DIR, "ledger.jsonl"))


def _sample_events():
    return [
        {"ts": "2026-06-08T09:15:00Z", "actor": "dr.adams", "patient": "P-1001",
         "action": "VIEW", "resource": "chart"},
        {"ts": "2026-06-08T09:20:00Z", "actor": "dr.adams", "patient": "P-1001",
         "action": "EXPORT", "resource": "labs"},
        {"ts": "2026-06-08T10:00:00Z", "actor": "nurse.lee", "patient": "P-1002",
         "action": "VIEW", "resource": "chart"},
        {"ts": "2026-06-08T11:30:00Z", "actor": "patient.P-1001", "patient": "P-1001",
         "action": "GRANT_CONSENT", "resource": "consent:research"},
    ]


def _build(path):
    for ev in _sample_events():
        append_event(path, ev)


def test_metadata():
    assert TOOL_NAME == "consentledger"
    assert isinstance(TOOL_VERSION, str) and TOOL_VERSION


def test_build_and_verify_clean(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    entries = load_ledger(path)
    assert len(entries) == 4
    assert entries[0].prev_hash == GENESIS_HASH
    # Each entry chains to the prior one.
    for i in range(1, len(entries)):
        assert entries[i].prev_hash == entries[i - 1].entry_hash
    res = verify_ledger(path)
    assert res.ok is True
    assert res.count == 4
    assert res.errors == []


def test_tamper_field_detected(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    # Mutate entry 1's action on disk to hide an EXPORT as a VIEW.
    lines = open(path, encoding="utf-8").read().splitlines()
    obj = json.loads(lines[1])
    obj["event"]["action"] = "VIEW"
    lines[1] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")

    res = verify_ledger(path)
    assert res.ok is False
    bad = [e for e in res.errors if e["index"] == 1]
    assert bad, "expected a tamper error at index 1"
    assert any("tampered" in e["problem"] for e in bad)


def test_deletion_breaks_chain(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    lines = open(path, encoding="utf-8").read().splitlines()
    del lines[1]  # remove the EXPORT row entirely
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    res = verify_ledger(path)
    assert res.ok is False


def test_reject_malformed_event(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    with pytest.raises(ValueError):
        append_event(path, {"actor": "x"})  # missing required fields
    assert load_ledger(path) == []


def test_inclusion_proof(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    proof = inclusion_proof(path, 1)
    assert proof["hash_matches"] is True
    assert proof["linked_to_next"] is True
    assert proof["included"] is True


def test_compute_entry_hash_deterministic():
    ev = {"ts": "t", "actor": "a", "patient": "p", "action": "VIEW", "resource": "r"}
    h1 = compute_entry_hash(0, GENESIS_HASH, ev)
    # Key order must not matter.
    ev2 = {"resource": "r", "action": "VIEW", "patient": "p", "actor": "a", "ts": "t"}
    h2 = compute_entry_hash(0, GENESIS_HASH, ev2)
    assert h1 == h2 and len(h1) == 64


def test_cli_verify_clean_exit_zero(tmp_path, capsys):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    rc = main(["--format", "json", "verify", "--ledger", path])
    out = capsys.readouterr().out
    assert rc == 0
    assert json.loads(out)["ok"] is True


def test_cli_verify_tampered_exit_one(tmp_path):
    path = str(tmp_path / "audit.jsonl")
    _build(path)
    lines = open(path, encoding="utf-8").read().splitlines()
    obj = json.loads(lines[0])
    obj["event"]["patient"] = "P-9999"
    lines[0] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    open(path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
    rc = main(["verify", "--ledger", path])
    assert rc == 1


def test_regenerate_and_verify_demo_ledger():
    """Regenerate the shipped demo ledger from canonical hashes and verify it.

    This guarantees demos/01-basic/ledger.jsonl is always a self-consistent,
    verifiable chain regardless of any hand-edited placeholder hashes.
    """
    if os.path.exists(DEMO_LEDGER):
        os.remove(DEMO_LEDGER)
    _build(DEMO_LEDGER)
    res = verify_ledger(DEMO_LEDGER)
    assert res.ok is True
    assert res.count == 4
