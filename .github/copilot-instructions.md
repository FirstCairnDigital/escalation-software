## Core Concept & Operating Boundaries
The system is an autonomous software-as-a-service application for **Credit Control, Tamper-Evident Evidence Assembly, and Procedural Workflow Management**.

- **DEFINITIVE PRODUCT BOUNDARY**:
  - The software helps businesses administer and document recovery of their own direct commercial invoices (B2B).
  - It provides **procedural information** and **prepares evidence bundles**.
- **CRITICAL**: The system is **NEVER** a debt collection agency, legal firm, process server, or FCA-regulated entity. It does **NOT** provide personalized legal advice, represent creditors, or file proceedings directly.
- **EXCLUSIONS**: Regulated consumer credit, sole-trader/individual personal loans, mortgages, residential rent, tax debts, insolvency proceedings, factored or purchased debts, or third-party collection.
- **OFF-RAMPS**: At key procedural junctions (Disputed Debts, Breathing Space, Complex/Uncertain Jurisdiction, or reaching internal system limits), the software MUST halt automated outreach, freeze state, and instruct the client to download their timestamped Evidence Pack for independent resolution or legal review.

## Architecture & Technical Stack Guidelines

### 1. Versioned Rule Pack Architecture
Legal and procedural rules MUST NOT be hard-coded inside state machine controllers or application code. Load rules dynamically using decoupled, versioned data schemas.

```text
CORE ENGINE (State Machine, Evidence Ledger, Communications, Calculations)
       │
       ▼
VERSIONED RULE PACKS (JSON/YAML Schemas)
  ├── SCOTLAND (Simple Procedure vs. Ordinary Cause)
  ├── ENGLAND_WALES (B2B LBA vs. Debt Claims Protocol)
  └── NORTHERN_IRELAND (Small Claims vs. County Court Commercial Protocol)
```

Each Rule Pack entity must expose:
- `rule_id`, `jurisdiction`, `rule_version`
- `effective_from`, `effective_to`
- `source_authority`, `source_reference`
- `fcd_automation_limit` (Internal risk-control threshold, e.g., £10,000 E&W, £5,000 Scotland, £5,000 NI)
- `human_approval_required` (Boolean)

### 2. Tamper-Evident Evidence Ledger (Audit Log)
Implement an append-only, cryptographic event ledger.

- **Data Models**:
  - `Invoices`: ID, Currency, Principal Amount, Issue Date, Due Date, Jurisdiction (`ENGLAND_WALES` | `SCOTLAND` | `NORTHERN_IRELAND`), Debtor Type (`LIMITED` | `SOLE_TRADER` | `INDIVIDUAL`).
  - `EvidenceArtifacts`: Document ID, Invoice ID, File Hash (SHA-256), File Path, Upload Timestamp.
  - `LedgerEvents`: Event ID, Invoice ID, Timestamp, Actor (`SYSTEM` | `CLIENT` | `DEBTOR`), Event Type, Data Payload, Hash (chained to previous log entry).
- **Cryptographic Hash Chaining**:
  - `current_event_hash = SHA256(event_id + timestamp + actor + payload + previous_event_hash)`
- **Database Rules**: Deny `UPDATE` and `DELETE` operations at the database permission level.
- **Exports**: Generate signed PDF/JSON manifests containing complete hash validation trees for court evidence submission.

### 3. State Machine Design
Implement a strict, deterministic state machine (`xstate` or equivalent) with explicit off-ramp states:

```text
[ISSUED] ──► [FRIENDLY_REMINDER] ──► [OVERDUE_CHASER] ──► [FORMAL_NOTICE] ──► [PRE_ACTION_PROTOCOL]
                                                                                      │
  ┌───────────────────────────────────────────────────────────────────────────────────┘
  ▼
Circuit Breakers / Off-Ramps:
  ├──► [DISPUTED] (Hard Freeze)
  ├──► [BREATHING_SPACE_PAUSE] (Hard Freeze)
  ├──► [JURISDICTION_UNCERTAIN] (Off-ramp)
  ├──► [CLIENT_HANDOFF] (Claim-Ready Evidence Pack Export)
  └──► [RESOLVED_PAID]
```

### 4. Multi-Factor Jurisdiction Engine
Do NOT rely solely on a single user dropdown. Determine jurisdiction by evaluating:
1. Creditor Legal Entity & Registered/Trading Address
2. Debtor Legal Entity Type & Registered/Trading Address
3. Contract Governing Law & Jurisdiction Clauses (if supplied)
4. Place of Goods/Services Delivery

*Rule*: If facts conflict or ambiguity exists, transition immediately to `JURISDICTION_UNCERTAIN` -> `CLIENT_HANDOFF`.

## Jurisdictional Escalation Workflows

### Branch A: Scotland (`SCOTLAND`)
- **Small Claims Limit**: Simple Procedure threshold applies at **£5,000 or less** (submitted via SCTS Civil Online).
- **Workflow**:
  - Claims <= £5,000: Auto-generate pre-court settlement chasers and formal demands. Upon expiry, compile **Scottish Civil Online Form 3A Evidence Pack** -> `CLIENT_HANDOFF`.
  - Claims > £5,000: Auto-escalate ONLY to Formal Notice. Immediately transition to `CLIENT_HANDOFF` with instructions: *"Exceeds automated workflow limit (£5,000). Export Evidence Pack for Ordinary Cause / Scottish Solicitor review."*

### Branch B: England & Wales (`ENGLAND_WALES`)
- **Debtor Type Routing**:
  - `SOLE_TRADER` or `INDIVIDUAL`: Trigger the **Pre-Action Protocol for Debt Claims**. Issue Letter of Claim, Reply Form, and Information Sheet. Apply a **mandatory 30-day delay timer** (extendable if debtor requests documents, debt advice, or submits financial statements).
  - `LIMITED` / Corporate B2B: Issue formal 14-day Letter Before Action.
- **Workflow Limit (`FCD_AUTOMATION_LIMIT = £10,000`)**:
  - Upon expiry of protocol periods, assemble **Money Claim Online (MMCO) / County Court Evidence Pack** -> `CLIENT_HANDOFF`.
  - UI Framing: *"This case has reached the FCD automated workflow limit. Download your timestamped evidence pack for court submission or legal instruction."*

### Branch C: Northern Ireland (`NORTHERN_IRELAND`)
- **Small Claims Limit**: General Small Claims limit is **£5,000** (processed via NI Direct Online portal).
- **Pre-Action Protocol**: Apply **County Court Commercial Actions Pre-Action Protocol** for corporate debts.
- **Workflow**:
  - Claims <= £5,000: Issue pre-action chasers under NI commercial protocol rules. Compile **NI Direct Small Claims Evidence Pack** on expiry -> `CLIENT_HANDOFF`.
  - Claims > £5,000: Issue Formal Notice only. Transition immediately to `CLIENT_HANDOFF` with instructions: *"Exceeds NI Small Claims limit (£5,000). Export Evidence Pack for County Court Civil Bill / NI Solicitor review."*
- **Enforcement Body**: All judgment enforcement documentation MUST reference the **Enforcement of Judgments Office (EJO)** (not High Court Enforcement Officers or Sheriff Officers).

## Statutory Calculation Helper (`Calculators/UKLatePayment`)
Do NOT assume every invoice automatically qualifies, and do NOT hard-code static interest reference rates.

- `Daily Interest = (Invoice Principal * (BoE Base Rate + 0.08)) / 365`

**Calculation Pipeline**:
1. Verify qualifying B2B commercial transaction.
2. Check if contractual terms specify an explicit late-payment remedy that overrides statutory terms.
3. Query dynamic reference rate table for Bank of England Base Rate active during the overdue period.
4. Calculate statutory interest (`Base Rate + 8%`) per day overdue.
5. Apply Statutory Fixed Recovery Compensation:
  - Debt < £1,000 -> **£40**
  - Debt £1,000 to £9,999.99 -> **£70**
  - Debt >= £10,000 -> **£100**
6. Record calculation payload, reference rates, and rule pack version into the Tamper-Evident Ledger.

## Circuit Breakers & Hard Stop Conditions
Enforce immediate state shifts to `DISPUTED`, `BREATHING_SPACE_PAUSE`, or `CLIENT_HANDOFF` if:
1. `debtor_feedback == 'DISPUTE'` (e.g., alleged defective work, invoice paid, short-shipped, counter-claim).
2. `system_flag == 'BREATHING_SPACE'` (UK Debt Respite Scheme notification received).
3. `system_flag == 'INSOLVENCY'` (Liquidation, administration, trust deed, or bankruptcy notification).
4. `debtor_feedback == 'PAYMENT_PLAN_REQUEST'` or `PARTIALLY_PAID`.
5. `debtor_type == 'CONSUMER_CREDIT'` (Reject during onboarding; regulated debts are strictly excluded).
6. `jurisdiction == 'JURISDICTION_UNCERTAIN'` (Conflicting address/contract facts).

## Priority Coding Tasks for Copilot
1. Build `InvoiceLedger` service featuring append-only SHA-256 chain tracking and signed export verification.
2. Implement `VersionedRulePack` loader supporting `ENGLAND_WALES`, `SCOTLAND`, and `NORTHERN_IRELAND` schema definitions.
3. Build `Calculators/UKLatePayment` helper class for dynamic interest, base rate lookup, and fixed recovery compensation tiers.
4. Build `JurisdictionEngine` supporting multi-factor rule evaluation (address, entity type, contract clauses).
5. Build `EvidencePackCompiler` (PDF generator) that compiles the invoice, contract, proof of delivery, complete tamper-evident audit trail, and pre-action notices into a court-ready PDF bundle tailored to SCTS Civil Online, MMCO, or NI Direct portals.
