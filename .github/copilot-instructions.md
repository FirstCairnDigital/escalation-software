# GitHub Copilot System Specification: FCD Controlled Commercial Debt-Resolution Workflow

## Core Concept & Product Philosophy
The system is an autonomous software-as-a-service application for **Credit Control, Controlled Commercial Debt-Resolution, Tamper-Evident Evidence Assembly, 5-Ledger Financial & Compliance Management, and Procedural Recovery Workflows**.

- **THE CORE PRODUCT PHILOSOPHY**:
  - *"First Cairn Digital (FCD) makes it easier to recover a valid debt and harder to pursue an invalid one. Court is not the default success state — resolution is."*

- **DEFINITIVE PRODUCT BOUNDARY**:
  - The software helps businesses administer and document recovery of their own direct commercial trade invoices (B2B).
  - It provides **procedural information**, facilitates **bilateral debt-resolution / payment plans**, and **prepares claim-ready evidence bundles**.
  - **CRITICAL**: The system is **NEVER** a debt collection agency, legal firm, process server, or FCA-regulated entity. It does **NOT** provide personalized legal advice, represent creditors, charge percentage recovery success commissions, file court proceedings directly, or conduct litigation.
  - **EXCLUSIONS**: Regulated consumer credit, sole-trader/individual personal loans, mortgages, residential rent, tax debts, insolvency proceedings, factored or purchased debts, or third-party collection.
  - **ABSOLUTE COURT HANDOFF BOUNDARY**:
    - FCD software operates strictly up to the pre-action phase.
    - Once automated processing ends or a legal threshold is reached, the system executes `CLIENT_HANDOFF`.
    - **FCD CAN**: Monitor, remind, record, calculate, prepare, organize, explain procedural options, offer settlement structures, and compile structured evidence packs.
    - **FCD CANNOT**: Decide whether to sue, file proceedings on behalf of a client, conduct litigation, represent a client in court, provide solicitor representation, or enforce judgments.

## Red-Team Dual-Perspective Architecture

### 1. Creditor Safeguards & Pre-Escalation Gatekeeping

#### A. Pre-Escalation Invoice Health Check
Before any escalation step is unlocked, run a pre-flight validation against 16 structural criteria and classify confidence as:
- `READY`
- `REVIEW`
- `STOP`

#### B. Devil’s Advocate Pre-Escalation Verification Engine
Before escalation execution, evaluate blocking counter-conditions:
- active disputes,
- payment/credit discrepancies,
- unverified delivery evidence,
- pending settlement dates not yet reached,
- unresolved debtor data-accuracy challenge,
- insolvency/Breathing Space flags.

If any counter-condition is true, escalation is blocked and an explicit resolution path is shown.

#### C. Viability & Proportionality Calculator
Before escalating low-value/distressed cases:
- run status/insolvency checks,
- compare expected recoverable value vs process cost/effort,
- show proportionality warning where applicable.

### 2. Debtor Protection, Transparency & Verification Portal

#### A. Anti-Phishing Case Verification (`/verify`)
All debtor communications include a non-sensitive verification route:
- `firstcairndigital.co.uk/verify?case=FCD-R-YYYY-NNNNNN`

Verification confirms only authenticity and issuer context until authenticated.

#### B. Frictionless Debtor Action Options
Formal communications should provide actions for:
- viewing invoice/breakdown,
- reporting paid status,
- lodging full/partial dispute,
- proposing payment plan/settlement,
- submitting data protection / accuracy challenge,
- contacting creditor.

#### C. Code-Enforced Data Accuracy Challenge Workflow
On debtor accuracy challenge:
1. Set `RECOVERY_RESTRICTED = TRUE` in compliance tracking.
2. Freeze automated chasers and escalation timers immediately.
3. Notify creditor with debtor challenge payload.
4. Require creditor correction/evidence before recovery resumes.

#### D. Transparent Data Source Notice
Debtor portal notice:
- FCD acts as Data Processor for the named creditor (Data Controller) for invoice administration only.

## Communication Severity & Tone Framework
Automation must adapt tone by stage and facts. False urgency, fake countdowns, or legal-status misrepresentation are forbidden.

Levels:
- **0** Pre-Due Courtesy
- **1** Friendly Reminder
- **2** Overdue Notification
- **3** Request for Resolution
- **4** Formal Notice
- **5** Pre-Action Procedural Notice
- **6** Client Handoff (automation ends)

## Complex Financial Ledger Engine (Ledger 1)
Ledger 1 supports:
- principal,
- approved credits,
- verified payments/partials,
- settlement discounts,
- retentions,
- disputed carve-out portions,
- statutory interest,
- fixed compensation,
- contractual recovery charges.

Rules:
- payment/credit entry immediately cancels pending automated comms,
- pre-send real-time balance lock required before communication dispatch.

## Settlement & Debt-Resolution Engine
Priority is bilateral resolution:
1. Payment plans with timestamped promise-to-pay schedules and pause/resume logic.
2. Full-and-final settlement workflows with timestamped agreement artifacts.
3. Dispute carve-out to progress undisputed balance while isolating disputed portions.

## 5-Ledger Architecture & Compliance Framework
Keep 5 ledgers isolated; no cross-posting:
1. Financial Ledger (Debtor Account)
2. Evidence Ledger
3. Event/Audit Ledger (hash-chained)
4. Compliance Ledger
5. FCD Billing Ledger (explicit user action required)

## Communication Delivery Tracking & Fail-Safes
Delivery lifecycle:
- `CREATED -> QUEUED -> SENT -> DELIVERED -> OPENED -> BOUNCED/REJECTED/RETURNED`

If delivery fails, halt escalation timers and require contact-detail verification.

## Circuit Breakers & Humane Recovery Pauses
Immediate halt/transition triggers:
- debtor dispute / data-accuracy challenge,
- Breathing Space protections,
- welfare/vulnerability concern (`HUMANE_PAUSE`),
- insolvency/deceased/dissolution,
- system balance correction requiring `ERROR_CORRECTED` append-only remediation and corrected communication.

## Versioned Technical Architecture
Never hardcode legal/regulatory values. Load dynamically from versioned packs:
- jurisdiction rules,
- pricing schedules,
- statutory rates,
- court fee schedules,
- communication templates (severity 0-6),
- legal disclaimers/templates.

Rule pack metadata fields:
- `rule_id`
- `version`
- `effective_date`
- `source_authority`
- `last_verified_date`
- `automation_allowed`
- `human_approval_required`

## Jurisdictional Escalation Workflows & External Fees

### Scotland (`SCOTLAND`)
- Small Claims / Simple Procedure <= £5,000.
- SCTS fees:
  - <= £300: £23
  - £300.01–£5,000: £127
- > £5,000: formal notice then immediate `CLIENT_HANDOFF`.

### England & Wales (`ENGLAND_WALES`)
- Sole trader/individual: PAP Debt Claims + mandatory 30-day delay.
- Limited companies: 14-day LBA.
- HMCTS issue fee schedule:
  - <= £300: £35
  - £3,000.01–£5,000: £205
  - £5,000.01–£10,000: £455
  - > £10,000: 5%
- `FCD_AUTOMATION_LIMIT = £10,000` then handoff.

### Northern Ireland (`NORTHERN_IRELAND`)
- Small Claims limit £5,000.
- NI pre-action protocol for county court commercial actions.
- NI fee schedule:
  - <= £300: £49
  - £300.01–£500: £81
  - £500.01–£1,000: £113
  - £1,000.01–£3,000: £163
  - £3,000.01–£5,000: £244
- Enforcement reference: EJO.

## Priority Coding Tasks for Copilot
1. Build `FiveLedgerEngine` with isolated sub-engines for ledgers 1–5.
2. Build `CaseHealthCheck` & `DevilsAdvocateEngine` pre-escalation blockers.
3. Build `ResolutionAndSettlementEngine` for plans/settlements/dispute carve-outs.
4. Build `DebtorVerificationPortal` (`/verify`) and data-accuracy challenge controls.
5. Build `EvidencePackCompiler` for SCTS/MMCO/NI Direct handoff-ready bundles.
