<a name="top"></a>
<div align="center">

<img src="https://capsule-render.vercel.app/api?type=rect&color=0:6b46c1,100:2b6cb0&height=120&section=header&text=CONSENTLEDGER&fontSize=48&fontColor=ffffff&fontAlignY=58" width="100%" alt="CONSENTLEDGER"/>

# CONSENTLEDGER

### Maintain a tamper-evident, hash-chained audit log of patient-data access and consent events.

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&size=18&duration=3500&pause=1000&color=6B46C1&center=true&vCenter=true&width=720&lines=Maintain+a+tamperevident+hashchained+audit+log+of+patientdat;Self-hostable+%C2%B7+MCP-native+%C2%B7+CI-ready+%C2%B7+polyglot" width="720"/>

[![PyPI](https://img.shields.io/pypi/v/cognis-consentledger.svg?color=6b46c1)](https://pypi.org/project/cognis-consentledger/) [![CI](https://github.com/cognis-digital/consentledger/actions/workflows/ci.yml/badge.svg)](https://github.com/cognis-digital/consentledger/actions) [![License: COCL 1.0](https://img.shields.io/badge/License-COCL%201.0-2b6cb0.svg)](LICENSE) [![Suite](https://img.shields.io/badge/Cognis-Neural%20Suite-6b46c1.svg)](https://github.com/cognis-digital)

*Healthcare & Life-Sciences — HIPAA, PHI, FHIR/HL7, and clinical data.*

</div>

```bash
pip install cognis-consentledger
consentledger scan .            # → prioritized findings in seconds
```

## Usage — step by step

1. **Install:**

   ```bash
   pip install -e .
   ```

2. **Append a tamper-evident event** to a hash-chained JSONL ledger with the `append` subcommand. All fields are required; `--meta KEY=VALUE` is repeatable and is folded into the entry hash:

   ```bash
   consentledger append --ledger audit.jsonl \
     --actor dr.adams --patient P-1001 --action VIEW --resource chart \
     --ts 2026-06-08T09:15:00Z
   ```

3. **List the recorded events** as a table (or `--format json`):

   ```bash
   consentledger list --ledger audit.jsonl
   ```

4. **Verify chain integrity** — this is the core check, and it **exits 1 if the ledger was tampered with**. You can also produce an inclusion proof for a single entry with `prove --index`:

   ```bash
   consentledger verify --ledger audit.jsonl --format json
   consentledger prove --ledger audit.jsonl --index 0 --format json
   ```

5. **Use it in CI / compliance jobs** — fail the job if the audit log has been altered:

   ```bash
   consentledger verify --ledger audit.jsonl --format json || {
     echo "Consent ledger integrity FAILED"; exit 1; }
   ```


## Contents

- [Why consentledger?](#why) · [Features](#features) · [Quick start](#quick-start) · [Example](#example) · [Architecture](#architecture) · [AI stack](#ai-stack) · [How it compares](#how-it-compares) · [Integrations](#integrations) · [Install anywhere](#install-anywhere) · [Related](#related) · [Contributing](#contributing)

<a name="why"></a>
## Why consentledger?

Turns the HIPAA 'audit controls' requirement into a verifiable append-only ledger you can prove to auditors — compliance-as-code virality.

`consentledger` is single-purpose, scriptable, and self-hostable: point it at a target, get prioritized results in the format your workflow already speaks (table · JSON · SARIF), gate CI on it, and let agents drive it over MCP.

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="features"></a>
## Features

- ✅ Canonical Event
- ✅ Compute Entry Hash
- ✅ Validate Event
- ✅ Load Ledger
- ✅ Head Hash
- ✅ Append Event
- ✅ Verify Ledger
- ✅ Inclusion Proof
- ✅ Runs on Linux/macOS/Windows · Docker · devcontainer
- ✅ Ports in Python, JavaScript, Go, and Rust (`ports/`)

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="quick-start"></a>
## Quick start

```bash
pip install cognis-consentledger
consentledger --version
consentledger scan .                       # scan current project
consentledger scan . --format json         # machine-readable
consentledger scan . --fail-on high        # CI gate (non-zero exit)
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="example"></a>
## Example

```text
$ consentledger scan .
  [HIGH    ] CON-001  example finding             (./src/app.py)
  [MEDIUM  ] CON-002  another signal              (./config.yaml)

  2 findings · risk score 5 · 38ms
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="architecture"></a>
## Architecture

```mermaid
flowchart LR
  IN[addresses + transactions] --> P[consentledger<br/>cluster + trace]
  P --> OUT[sanctions xref / report]
```

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="ai-stack"></a>
## Use it from any AI stack

`consentledger` is interoperable with every popular way of using AI:

- **MCP server** — `consentledger mcp` (Claude Desktop, Cursor, Cognis.Studio, [uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet))
- **OpenAI-compatible / JSON** — pipe `consentledger scan . --format json` into any agent or LLM
- **LangChain · CrewAI · AutoGen · LlamaIndex** — wrap the CLI/JSON as a tool in one line
- **CI / scripts** — exit codes + SARIF for non-AI pipelines

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="how-it-compares"></a>
## How it compares

| | **Cognis consentledger** | sigstore |
|---|:---:|:---:|
| Self-hostable, no account | ✅ | varies |
| Single command, zero config | ✅ | ⚠️ |
| JSON + SARIF for CI | ✅ | varies |
| MCP-native (AI agents) | ✅ | ❌ |
| Polyglot ports (JS/Go/Rust) | ✅ | ❌ |
| Open license | ✅ COCL | varies |

*Built in the spirit of **sigstore/rekor + git**, re-framed the Cognis way. Missing a credit? Open a PR.*

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="integrations"></a>
## Integrations

Pipes into your stack: **SARIF** for code-scanning, **JSON** for anything, an **MCP server** (`consentledger mcp`) for AI agents, and a webhook forwarder for SIEM/Slack/Jira. See [`docs/INTEGRATIONS.md`](docs/INTEGRATIONS.md).

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="install-anywhere"></a>
## Install — every way, every platform

```bash
pip install "git+https://github.com/cognis-digital/consentledger.git"    # pip (works today)
pipx install "git+https://github.com/cognis-digital/consentledger.git"   # isolated CLI
uv tool install "git+https://github.com/cognis-digital/consentledger.git" # uv
pip install cognis-consentledger                                          # PyPI (when published)
docker run --rm ghcr.io/cognis-digital/consentledger:latest --help        # Docker
brew install cognis-digital/tap/consentledger                             # Homebrew tap
curl -fsSL https://raw.githubusercontent.com/cognis-digital/consentledger/main/install.sh | sh
```

| Linux | macOS | Windows | Docker | Cloud |
|---|---|---|---|---|
| `scripts/setup-linux.sh` | `scripts/setup-macos.sh` | `scripts/setup-windows.ps1` | `docker run ghcr.io/cognis-digital/consentledger` | [DEPLOY.md](docs/DEPLOY.md) (AWS/Azure/GCP/k8s) |

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="related"></a>
## Related Cognis tools

- [`phiscrub`](https://github.com/cognis-digital/phiscrub) — Stream-scan logs, CSVs, and free-text notes for PHI (names, MRNs, SSNs, dates, addresses) and redact or tokenize in place.
- [`dicomsweep`](https://github.com/cognis-digital/dicomsweep) — De-identify DICOM imaging studies per the DICOM PS3.15 Annex E profile, scrubbing tags and burned-in pixel text.
- [`fhirlint`](https://github.com/cognis-digital/fhirlint) — Validate FHIR R4/R5 resources and bundles against profiles (US Core, etc.) with precise, line-level error reporting.
- [`hl7tap`](https://github.com/cognis-digital/hl7tap) — Parse, pretty-print, diff, and replay HL7 v2 messages over MLLP from the terminal.
- [`synthcohort`](https://github.com/cognis-digital/synthcohort) — Generate statistically realistic synthetic patient cohorts (FHIR/CSV) from a schema spec for dev and testing.
- [`trialwatch`](https://github.com/cognis-digital/trialwatch) — Query, diff, and monitor ClinicalTrials.gov records, alerting on status, enrollment, or result changes.

**Explore the suite →** [🗂️ all 170+ tools](https://github.com/cognis-digital/cognis-neural-suite) · [⭐ awesome-cognis](https://github.com/cognis-digital/awesome-cognis) · [🔗 cognis-sources](https://github.com/cognis-digital/cognis-sources) · [🤖 uncensored-fleet](https://github.com/cognis-digital/uncensored-fleet) · [🧠 engram](https://github.com/cognis-digital/engram)

<div align="right"><a href="#top">↑ back to top</a></div>

<a name="contributing"></a>
## Contributing

PRs, new rules, and demo scenarios are welcome under the collaboration-pull model — see [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).

> ### ⭐ If `consentledger` saved you time, **star it** — it genuinely helps others find it.

## License

Source-available under the **Cognis Open Collaboration License (COCL) v1.0** — free for personal, internal-evaluation, research, and educational use; **commercial / production use requires a license** (licensing@cognis.digital). See [LICENSE](LICENSE).

---

<div align="center"><sub><b><a href="https://cognis.digital">Cognis Digital</a></b> · one of 170+ tools in the <a href="https://github.com/cognis-digital/cognis-neural-suite">Cognis Neural Suite</a> · <i>Making Tomorrow Better Today</i></sub></div>
