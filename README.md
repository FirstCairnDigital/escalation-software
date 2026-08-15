# P26003 Commercial Invoice Recovery Assistant

Credit-control and evidence-assembly software for B2B invoice recovery workflows.

## Product Boundary
- Supports direct commercial invoice recovery workflows for business users.
- Provides procedural workflow automation and evidence preparation.
- Does **not** act as a debt collector, legal representative, or filing agent.
- Excludes consumer credit and other out-of-scope debt categories defined in [copilot-instructions.md](C:/Dev/projects/P26003-escalation-software/.github/copilot-instructions.md).

## Current Implementation
- Versioned jurisdiction rule packs (England & Wales, Scotland, Northern Ireland).
- Deterministic escalation state machine with hard-stop/off-ramp handling.
- Append-only tamper-evident ledger with SHA-256 chain verification.
- SQLite persistence with triggers preventing `UPDATE`/`DELETE` on evidence tables.
- Signed ledger manifests (JSON + PDF) and verification endpoint.
- Late-payment calculator with BoE base-rate reference data and ledger logging.
- Claim-ready evidence bundle PDF generation.

## Project Structure
- Source: [src/unpaid_invoice_escalator/](C:/Dev/projects/P26003-escalation-software/src/unpaid_invoice_escalator)
- Tests: [tests/](C:/Dev/projects/P26003-escalation-software/tests)
- Rule packs: [src/unpaid_invoice_escalator/rulepacks/packs/](C:/Dev/projects/P26003-escalation-software/src/unpaid_invoice_escalator/rulepacks/packs)
- Copilot system spec: [copilot-instructions.md](C:/Dev/projects/P26003-escalation-software/.github/copilot-instructions.md)

## Requirements
- Python 3.11+

Install dependencies:

```powershell
pip install -e .
```

## Run the API

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unpaid_invoice_escalator.api
```

Server default: `http://127.0.0.1:8000`

### Web Interface
- Open `http://127.0.0.1:8000/` for the in-app operations UI.

## Run the CLI

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unpaid_invoice_escalator.cli --invoice-id inv-1 --principal 1200 --issue-date 2026-01-01 --due-date 2026-01-31 --jurisdiction ENGLAND_WALES --debtor-type LIMITED --today 2026-02-15
```

## API Endpoints
- `GET /health`
- `GET /` (Web UI)
- `GET /rule-packs/{jurisdiction}/active?on_date=YYYY-MM-DD`
- `POST /invoices`
- `GET /invoices/{invoice_id}`
- `GET /invoices/{invoice_id}/evidence-artifacts`
- `GET /invoices/{invoice_id}/ledger-events?limit=100`
- `POST /invoices/{invoice_id}/escalate`
- `POST /invoices/{invoice_id}/evidence-artifacts` (multipart; supports `artifact_type`)
- `POST /invoices/{invoice_id}/evidence-bundles`
- `POST /invoices/{invoice_id}/ledger-manifests` (`json` or `pdf`)
- `POST /invoices/{invoice_id}/ledger-manifests/verify`
- `POST /invoices/{invoice_id}/late-payment-calculations`

## Test

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unittest discover -s tests -v
```

## Evidence Artifact Types
Defined in [models.py](C:/Dev/projects/P26003-escalation-software/src/unpaid_invoice_escalator/models.py):
- `CONTRACT`
- `PROOF_OF_DELIVERY`
- `PRE_ACTION_NOTICE`
- `OTHER`

## Rule Pack Notes
Current automation limits from rule packs:
- England & Wales: £10,000
- Scotland: £5,000
- Northern Ireland: £5,000

These limits and protocol timings are data-driven via JSON rule packs, not hard-coded constants.
