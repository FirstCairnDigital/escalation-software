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
- Company-status checks, Breathing Space controls, insolvency-review workflows, and restricted-note segregation.
- Portfolio retention queue reporting plus in-process ops scripts for compliance workflows.

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
$env:FCD_DATA_RETENTION_DAYS="2190"
$env:FCD_DATA_RETENTION_CRON_SCHEDULE="0 2 * * *"
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
- `FCD_DATA_RETENTION_DAYS` sets minimum case age before controlled evidence-file disposal is permitted.
- `FCD_DATA_RETENTION_CRON_SCHEDULE` declares the retention review cadence surfaced by startup validation and reporting.

### Web Interface
- Open `http://127.0.0.1:8000/` for the overview dashboard.
- Open `http://127.0.0.1:8000/ui/cases` for the dedicated case board.
- Open `http://127.0.0.1:8000/ui/debtors` for debtor-oriented segmentation and portal review.
- Open `http://127.0.0.1:8000/ui/creditors` for creditor-facing exposure and formal-stage review.
- Open `http://127.0.0.1:8000/ui/disputes` for restricted/disputed case review.
- Open `http://127.0.0.1:8000/ui/operations` for intake and quick actions.
- Open `http://127.0.0.1:8000/ui/compliance` for audit and compliance review.
- Open `http://127.0.0.1:8000/ui/reports` for operational reporting cards and queue summaries.
- Open `http://127.0.0.1:8000/ui/invoices/{invoice_id}` for a focused invoice workspace.

## Run the CLI

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unpaid_invoice_escalator.cli --invoice-id inv-1 --principal 1200 --issue-date 2026-01-01 --due-date 2026-01-31 --jurisdiction ENGLAND_WALES --debtor-type LIMITED --today 2026-02-15
python -m unpaid_invoice_escalator.cli startup-config-report --db-path data\escalator.db
python -m unpaid_invoice_escalator.cli retention-queue --db-path data\escalator.db
python -m unpaid_invoice_escalator.cli company-status-check --db-path data\escalator.db --invoice-id inv-1 --checked-by USER-1 --company-status ACTIVE --source COMPANIES_HOUSE --evidence-summary "Register reviewed"
```

## Run workflow admin scripts

```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python scripts\ops\workflow-admin.py retention-queue --db-path data\escalator.db
python scripts\ops\workflow-admin.py company-status-check --db-path data\escalator.db --invoice-id inv-1 --checked-by USER-1 --company-status ACTIVE --source COMPANIES_HOUSE --evidence-summary "Register reviewed"
```

## Ops Runbook Assets
- Simple all-in-one guide: [everything-manual-for-dummies.md](C:/Dev/projects/P26003-escalation-software/scripts/ops/everything-manual-for-dummies.md)
- Go-live command sheet: [go-live-command-sheet.ps1](C:/Dev/projects/P26003-escalation-software/scripts/ops/go-live-command-sheet.ps1)
- Red/green signoff script: [go-live-red-green-signoff.ps1](C:/Dev/projects/P26003-escalation-software/scripts/ops/go-live-red-green-signoff.ps1)
- Operator runbook template: [operator-go-live-runbook-template.md](C:/Dev/projects/P26003-escalation-software/scripts/ops/operator-go-live-runbook-template.md)
- Production validator: [validate-production-config.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/validate-production-config.py)
- Ledger reconciliation utility: [reconcile-ledger.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/reconcile-ledger.py)
- SBC export utility: [export-sbc-bundle.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/export-sbc-bundle.py)
- Retention audit utility: [audit-retention-holds.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/audit-retention-holds.py)
- Workflow admin utility: [workflow-admin.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/workflow-admin.py)

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
- `GET /ui/dashboard`
- `GET /ui/cases`
- `GET /ui/debtors`
- `GET /ui/creditors`
- `GET /ui/disputes`
- `GET /ui/operations`
- `GET /ui/compliance`
- `GET /ui/reports`
- `GET /ui/invoices/{invoice_id}` (Focused invoice workspace)
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
- `GET /data-retention-policy`
- `GET /data-retention-queue?as_of_date=YYYY-MM-DD&upcoming_within_days=45`
- `GET /invoices/{invoice_id}/data-retention-review?as_of_date=YYYY-MM-DD`
- `POST /invoices/{invoice_id}/data-retention-legal-holds/open`
- `POST /invoices/{invoice_id}/data-retention-legal-holds/release`
- `POST /invoices/{invoice_id}/data-retention-disposals`
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
- `POST /invoices/{invoice_id}/settlement-bank-details`
- `GET /invoices/{invoice_id}/settlement-bank-details`
- `POST /portal/actions/data-accuracy-challenge`
- `POST /portal/actions/disputes`
- `POST /portal/actions/questions`
- `POST /portal/actions/confirm-payment-date`
- `POST /portal/actions/already-paid`
- `POST /portal/actions/payment-plan-proposals`
- `POST /portal/actions/settlement-offers`
- `POST /portal/actions/confirm-paid`
- `POST /invoices/{invoice_id}/debtor-actions/dispute/resolve`
- `POST /invoices/{invoice_id}/humane-pauses/open`
- `POST /invoices/{invoice_id}/humane-pauses/release`
- `POST /invoices/{invoice_id}/company-status-checks`
- `GET /invoices/{invoice_id}/company-status-checks`
- `POST /invoices/{invoice_id}/breathing-space/open`
- `POST /invoices/{invoice_id}/breathing-space/release`
- `POST /invoices/{invoice_id}/insolvency-reviews/open`
- `POST /invoices/{invoice_id}/insolvency-reviews/release`
- `POST /invoices/{invoice_id}/restricted-notes`
- `GET /invoices/{invoice_id}/restricted-notes?viewer_id=USER-1`
- `GET /invoices/{invoice_id}/governance-summary`
- `GET /invoices/{invoice_id}/client-handoff`
- `POST /invoices/{invoice_id}/client-handoff/review`
- `GET /invoices/{invoice_id}/debtor-portal-summary`
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

## Compliance and retention operations
- The compliance workspace now exposes company-status checks, Breathing Space controls, insolvency review actions, and restricted-note summaries in the browser UI.
- `GET /data-retention-queue` provides a portfolio view of eligible, legal-hold, and near-threshold retention cases for reports and ops scripts.
- Startup validation and the reports UI now surface `FCD_DATA_RETENTION_CRON_SCHEDULE` so retention automation posture is visible before go-live.
- [audit-retention-holds.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/audit-retention-holds.py) now calls the same retention-queue API logic used by the product, avoiding hard-coded retention thresholds in ops reporting.
- [workflow-admin.py](C:/Dev/projects/P26003-escalation-software/scripts/ops/workflow-admin.py) and [cli.py](C:/Dev/projects/P26003-escalation-software/src/unpaid_invoice_escalator/cli.py) let operators run compliance actions without standing up a separate HTTP server.

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
- Payment plans are append-only proposal records with generated installment schedules, append-only decision history, and immutable confirmed-payment records.
- Payment-plan proposals remain `PROPOSED` until the counterparty accepts; only then does the plan become `ACTIVE` and pause chasers.
- Installment payments are reported for creditor verification first; debtor assertions do not post directly to the debtor ledger.
- While a payment plan is `ACTIVE`, escalation is blocked and chasers remain paused; if it later defaults, escalation is re-evaluated from the live workflow state rather than forcing a hard-coded resume state.
- Settlement offers move to `AWAITING_PAYMENT` after bilateral acceptance and only become `FINALIZED` after linked payment is creditor-confirmed.
- Promise-to-Pay and Full & Final Settlement artifacts can be generated as tamper-evident PDF records.
- Dispute carve-outs isolate disputed amounts from the immediately pursued undisputed balance.
- Debtor portal verification view returns neutral resolution options and independent advice links messaging.
- Debtor portal actions are executable workflows for dispute intake, questions, promised payment-date confirmations, data accuracy challenges, payment plan proposals, settlement offers, and payment reporting.
- Escalation is blocked while an open debtor dispute exists, while a creditor-confirmation payment check remains open, while a confirmed debtor payment date remains in the future, or while a bilaterally accepted settlement is still awaiting payment.
- Settlement bank detail updates require MFA re-authentication or dual-control approval and are CoP-scored (`EXACT_MATCH`, `CLOSE_MATCH`, `NO_MATCH`).
- Debtor portal hides settlement destination and payment links when CoP state is `COP_UNVERIFIED` or `COP_FAILED`.
- Data-retention disposal is blocked when a case-level retention legal hold is open; holds are opened/released via dedicated endpoints with immutable audit entries.
- Evidence bundle generation can include resolution artifacts via `include_resolution_artifacts=true`.
- Humane pause controls now provide a summary-only welfare/vulnerability hold that blocks escalation without storing raw sensitive medical details in workflow records.
- Governance summaries expose live restriction codes, pause reasons, and next operator action so the UI can warn before unsafe progression.
- Client handoff summaries provide jurisdiction destination, required documents, rule-pack version, official court-fee context, and review signoff history.
- Debtor portal JSON/HTML now includes case status, restriction summary, settlement destination visibility, and recent portal activity for operator reconciliation.

## SQLite Upgrade / Rollout Notes
- [sqlite_store.py](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/src/unpaid_invoice_escalator/persistence/sqlite_store.py) remains the schema authority and automatically creates the new payment-verification and settlement-finalization tables on startup.
- Existing SQLite databases are upgraded in place by adding any missing resolution columns, including:
  - `reported_payments.plan_id`
  - `reported_payments.installment_id`
  - `reported_payments.settlement_offer_id`
  - `payment_plan_agreements.proposer_role`
  - `payment_plan_agreements.parent_plan_id`
  - `payment_plan_agreements.version_number`
  - `payment_plan_payments.reported_payment_id`
- Historical records are not rewritten. Legacy events remain visible as historical artifacts and should be reviewed in context during rollout validation.
- Recommended rollout check:
  1. start the app against a copy of the target SQLite database
  2. confirm `/health` and `/ready`
  3. open [ui.py](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/src/unpaid_invoice_escalator/ui.py) operations/workspace pages
  4. verify reported-payment review and settlement-progress controls render
  5. verify humane-pause controls, governance snapshot, and handoff readiness panels render on the compliance/workspace pages
  6. verify one non-production payment-verification and client-handoff review flow before promoting the upgraded databasese

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
