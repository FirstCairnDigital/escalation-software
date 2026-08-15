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
- Dual-ledger engine with strict debtor-claim and FCD-client-fee isolation.
- Pre-overdue contract hygiene workflow with legal-review disclaimer handling.
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

### Production Security Configuration
Set these before startup in production:

```powershell
$env:FCD_APP_ENV="production"
$env:FCD_MANIFEST_SIGNING_KEY="<strong-secret-or-kms-material>"
$env:FCD_MANIFEST_KEY_ID="fcd-kms-key-1"
$env:FCD_MANIFEST_VERIFY_KEYS="fcd-kms-key-1:<current-key>,fcd-kms-key-0:<previous-key>"
$env:FCD_API_KEYS="admin-key:admin,ops-key:operator,ro-key:viewer"
$env:FCD_RATE_LIMIT_PER_MINUTE="120"
$env:FCD_AUTH_FAILURE_ALERT_THRESHOLD="10"
$env:FCD_RATE_LIMIT_ALERT_THRESHOLD="10"
$env:FCD_SERVER_ERROR_ALERT_THRESHOLD="5"
$env:FCD_MAX_UPLOAD_BYTES="5242880"
$env:FCD_ALLOWED_UPLOAD_CONTENT_TYPES="application/pdf,text/plain,image/png,image/jpeg"
$env:FCD_ALLOWED_UPLOAD_EXTENSIONS=".pdf,.txt,.png,.jpg,.jpeg"
$env:FCD_QUARANTINE_DIR="data/quarantine"
```

Notes:
- `FCD_APP_ENV=production` enforces non-default signing keys.
- API keys are supplied via `x-api-key` header.
- Role levels: `viewer` (read), `operator` (write), `admin` (metrics/ops).
- `FCD_MANIFEST_VERIFY_KEYS` enables key-rotation verification windows.
- `FCD_MAX_UPLOAD_BYTES` enforces maximum uploaded artifact size.
- `FCD_ALLOWED_UPLOAD_CONTENT_TYPES` restricts evidence uploads by MIME type.
- `FCD_ALLOWED_UPLOAD_EXTENSIONS` restricts evidence uploads by filename extension.
- `FCD_QUARANTINE_DIR` stores rejected upload payloads and metadata for audit review.

### Web Interface
- Open `http://127.0.0.1:8000/` for the in-app operations UI.
- Open `http://127.0.0.1:8000/ui/invoices/{invoice_id}` for a tabbed invoice workspace.

## Run the CLI

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unpaid_invoice_escalator.cli --invoice-id inv-1 --principal 1200 --issue-date 2026-01-01 --due-date 2026-01-31 --jurisdiction ENGLAND_WALES --debtor-type LIMITED --today 2026-02-15
```

## API Endpoints
- `GET /health`
- `GET /ready` (readiness check; public)
- `GET /verify?case=&code=` (public anti-phishing verification)
- `GET /portal?case=&code=` (public debtor verification portal view)
- `GET /metrics` (admin role when auth enabled)
- `GET /deployment/startup-config-validation` (admin role when auth enabled)
- `GET /deployment/startup-config-validation/report` (admin role when auth enabled)
- `GET /deployment/runbook` (admin role when auth enabled)
- `GET /` (Web UI)
- `GET /ui/invoices/{invoice_id}` (Tabbed invoice workspace)
- `GET /rule-packs/{jurisdiction}/active?on_date=YYYY-MM-DD`
- `POST /invoices`
- `GET /invoices/{invoice_id}`
- `GET /invoices/{invoice_id}/communication-preview?state=&on_date=YYYY-MM-DD`
- `POST /invoices/{invoice_id}/communications`
- `POST /invoices/{invoice_id}/communications/{communication_id}/delivery-events`
- `GET /invoices/{invoice_id}/communications`
- `POST /invoices/{invoice_id}/case-health-check`
- `POST /invoices/{invoice_id}/devils-advocate-check`
- `GET /invoices/{invoice_id}/five-ledger-summary`
- `POST /invoices/{invoice_id}/legal-safety-gate/confirm`
- `POST /invoices/{invoice_id}/discrepancy-check`
- `GET /invoices/{invoice_id}/compliance-ledger`
- `POST /invoices/{invoice_id}/debtor-verification/register`
- `POST /invoices/{invoice_id}/debtor-actions/data-accuracy-challenge`
- `POST /invoices/{invoice_id}/debtor-actions/data-accuracy-challenge/resolve`
- `POST /invoices/{invoice_id}/resolution/payment-plans`
- `GET /invoices/{invoice_id}/resolution/payment-plans?as_of_date=YYYY-MM-DD`
- `POST /invoices/{invoice_id}/resolution/payment-plans/{plan_id}/payments`
- `POST /invoices/{invoice_id}/resolution/settlement-offers`
- `GET /invoices/{invoice_id}/resolution/settlement-offers`
- `POST /invoices/{invoice_id}/resolution/settlement-offers/{offer_id}/accept`
- `POST /invoices/{invoice_id}/resolution/dispute-carve-outs`
- `GET /invoices/{invoice_id}/resolution/dispute-carve-outs`
- `POST /invoices/{invoice_id}/resolution/artifacts/promise-to-pay`
- `POST /invoices/{invoice_id}/resolution/artifacts/settlement-agreement`
- `POST /invoices/{invoice_id}/communications/{communication_id}/balance-corrections`
- `POST /portal/actions/data-accuracy-challenge`
- `POST /portal/actions/payment-plan-proposals`
- `POST /portal/actions/settlement-offers`
- `POST /portal/actions/confirm-paid`
- `GET /invoices/{invoice_id}/evidence-artifacts?artifact_type=&limit=100&offset=0`
- `GET /invoices/{invoice_id}/ledger-events?event_type=&limit=100&offset=0`
- `GET /invoices/{invoice_id}/debtor-ledger`
- `GET /invoices/{invoice_id}/client-fee-ledger`
- `POST /invoices/{invoice_id}/escalate`
- `POST /invoices/{invoice_id}/client-fee-ledger/actions`
- `POST /invoices/{invoice_id}/debtor-ledger/entries`
- `POST /invoices/{invoice_id}/recovery-cost-assessments`
- `POST /invoices/{invoice_id}/court-fee-quotes`
- `POST /invoices/{invoice_id}/viability-proportionality-assessments`
- `POST /invoices/{invoice_id}/pre-overdue-hygiene`
- `GET /invoices/{invoice_id}/pre-overdue-hygiene`
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
- `PROMISE_TO_PAY`
- `FULL_AND_FINAL_SETTLEMENT`
- `OTHER`

## Rule Pack Notes
Current automation limits from rule packs:
- England & Wales: £10,000
- Scotland: £5,000
- Northern Ireland: £5,000

These limits and protocol timings are data-driven via JSON rule packs, not hard-coded constants.

## Pre-Overdue Contract Hygiene
- Captures creditor/debtor legal entity, Companies House number, VAT number, trading address metadata, PO requirement flags, payment terms, and contractual remedy clauses.
- Returns checklist completeness and missing items for credit-control setup quality.
- Applies strict format checks for Companies House and VAT numbers with warning tiers (`NONE`, `MEDIUM`, `HIGH`).
- Any suggested clause text is automatically marked with the disclaimer:
  - `Requires Client Independent Legal Review`

## Monitoring & Alerts
- Use `GET /metrics` for request counters, auth failures, 429s, and 5xx totals.
- `GET /metrics` also returns structured `recent_audit_events`, `alert_policy`, and `active_alerts`.
- Alert on sustained increases in:
  - `auth_failures_total`
  - `rate_limited_total`
  - `server_errors_total`
- Treat non-null `last_alert` as an operational signal to review logs.
- All responses include `x-request-id` and security headers (`x-content-type-options`, `x-frame-options`, `referrer-policy`, `cache-control`) for traceability and browser hardening.

## Readiness & Deployment Validation
- `GET /ready` returns:
  - `200` with `status=ready` when all error-severity checks pass.
  - `503` with `status=not_ready` when any error-severity check fails.
- `GET /deployment/startup-config-validation` returns a full startup/runtime config validation report with:
  - environment and effective security settings
  - check list (pass/fail + severity + detail)
  - aggregated `errors` and `warnings`
- `GET /deployment/startup-config-validation/report` returns startup validation plus runbook summary in one payload.
- `GET /deployment/runbook` returns deployment action steps with completion flags based on current checks.

## Upload Rejection & Quarantine
- Rejected uploads (size/type/extension/filename policy) are quarantined with a reference ID.
- Quarantine actions are written to the tamper-evident event ledger.
- `GET /metrics` includes:
  - `upload_rejected_total`
  - `upload_quarantined_total`
  - `upload_rejections_by_reason`

## Resolution & Settlement Controls
- Payment plans are append-only records with generated installment schedules and immutable payment records.
- While a payment plan is `ACTIVE`, escalation is blocked and chasers remain paused.
- If a plan defaults, escalation resumes from `OVERDUE_CHASER` (Level 2 equivalent flow).
- Settlement offers are finalized only after both debtor and creditor accept.
- Promise-to-Pay and Full & Final Settlement artifacts can be generated as tamper-evident PDF records.
- Dispute carve-outs isolate disputed amounts from the immediately pursued undisputed balance.
- Debtor portal verification view returns neutral resolution options and independent advice links messaging.
- Debtor portal actions are executable workflows for data accuracy challenges, payment plan proposals, settlement offers, and payment reporting.
- Evidence bundle generation can include resolution artifacts via `include_resolution_artifacts=true`.

## Viability & Proportionality
- Viability assessments combine projected FCD action fee, projected court fee, and estimated time-cost against current outstanding amount.
- Escalation calls include `viability_assessment` and block when the supplied company status indicates financial distress (`INSOLVENT`, `DISSOLVED`, `IN_ADMINISTRATION`, `CEASED`).
- When costs look disproportionate, responses include the mandatory notice:
  - `Recovery costs and effort may be disproportionate to the amount outstanding (£X).`

## Communication Severity Framework
- Escalation responses include `communication_preview` with:
  - `level` (0-6)
  - `stage_name`
  - `template_version`
  - `message`
  - `guardrail_flags`
- Guardrails automatically rewrite banned urgency/legal-pressure phrases into neutral procedural language.

## Communication Delivery Lifecycle
- Delivery states are tracked as append-only events:
  - `CREATED -> QUEUED -> SENT -> DELIVERED -> OPENED`
  - failure branches: `BOUNCED`, `REJECTED`, `RETURNED`
  - operational cancellation state: `CANCELLED`
- If a communication is in a failure state, escalation is blocked until contact details are corrected and delivery is re-queued.
- Automated communications enforce a pre-send balance lock and require a positive outstanding balance at send time.
- Recording payment or credit entries automatically cancels pending automated communications (`CREATED`/`QUEUED`).
- Evidence bundles now include a communication delivery timeline and correction/withdrawal notice section sourced from compliance events.
- Evidence bundles also include an artifact inventory, compliance snapshot, and event-chain attestation (validity, event count, latest hash).
- Balance corrections now log `ERROR_CORRECTED`, issue a withdrawal notice, and dispatch a corrected statement with immutable audit entries.

## Deployment Runbook (Minimal)
1. Set production environment variables (above).
2. Start service (`python -m unpaid_invoice_escalator.api`) behind TLS/reverse proxy.
3. Smoke test:
   - `GET /health` (no auth)
   - `GET /metrics` with admin API key
   - `POST /invoices` with operator API key
4. Verify signing and verification flow:
   - `POST /invoices/{id}/ledger-manifests`
   - `POST /invoices/{id}/ledger-manifests/verify`
5. Configure alerting on `metrics` counters and HTTP 5xx logs.
