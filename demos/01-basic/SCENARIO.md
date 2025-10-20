# Demo 01 — Basic: verifying a tamper-evident consent ledger

This demo shows CONSENTLEDGER detecting tampering in a HIPAA-style audit log.

## The input

`ledger.jsonl` is a pre-built, **valid** hash-chained ledger of 4 patient-data
events (chart views, an export, and a consent grant). Each line commits to the
hash of the previous line, so the whole history is sealed.

## What it shows

### 1. A clean ledger verifies

```
python -m consentledger verify --ledger demos/01-basic/ledger.jsonl --format json
```

Expected: `"ok": true`, `"count": 4`, an empty `errors` list, and **exit code 0**.

### 2. List the events

```
python -m consentledger list --ledger demos/01-basic/ledger.jsonl
```

Expected: a 4-row table (index, ts, actor, patient, action, resource, hash).

### 3. Tampering is detected

If any field of any historical event is edited (e.g. changing the `action` of
entry 1 from `EXPORT` to `VIEW` to hide a data exfiltration), the recomputed
`entry_hash` no longer matches and the chain link to the next entry breaks.
`verify` then reports `"ok": false` with the offending index and **exits 1** —
the non-zero exit is what makes it usable as a CI / audit gate.

The smoke tests in `tests/test_smoke.py` exercise all three behaviors
programmatically, including building a fresh ledger, mutating a row on disk,
and asserting verification fails.

## Why it matters

HIPAA §164.312(b) requires audit controls that record and examine activity in
systems containing electronic protected health information. A plain log can be
silently edited after the fact. A hash-chained ledger makes any retroactive
edit, deletion, reordering, or forgery cryptographically detectable.
