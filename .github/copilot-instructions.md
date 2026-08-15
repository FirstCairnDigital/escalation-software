# GitHub Copilot System Specification: FCD Commercial Invoice Recovery Assistant

## Core Concept & Operating Boundaries
The system is an autonomous software-as-a-service application for **Credit Control, Tamper-Evident Evidence Assembly, Dual-Ledger Financial Management, and Procedural Recovery Workflows**.

- **DEFINITIVE PRODUCT BOUNDARY**:
  - The software helps businesses administer and document recovery of their own direct commercial trade invoices (B2B).
  - It provides **procedural information** and **prepares claim-ready evidence bundles**.
  - **CRITICAL**: The system is **NEVER** a debt collection agency, legal firm, process server, or FCA-regulated entity. It does **NOT** provide personalized legal advice, represent creditors, charge percentage recovery success commissions, or file court proceedings directly.
  - **EXCLUSIONS**: Regulated consumer credit, sole-trader/individual personal loans, mortgages, residential rent, tax debts, insolvency proceedings, factored or purchased debts, or third-party collection.
  - **OFF-RAMPS**: At key procedural junctions (Disputed Debts, Breathing Space, Complex/Uncertain Jurisdiction, or reaching internal system limits), the software MUST halt automated outreach, freeze state, and instruct the client to download their timestamped Evidence Pack for independent resolution or legal review.

## Architecture & Dual-Ledger System Guidelines

### 1. The Dual-Ledger Financial Architecture
The system MUST strictly isolate and maintain two independent ledgers for every case. **NEVER** automatically merge or cross-post entries between these ledgers.

- **Ledger A (Debtor Account)** tracks debtor-claim amounts.
- **Ledger B (FCD Client Fee Account)** tracks SaaS and action-based client charges.

#### Ledger A (Debtor Account)
- Tracks original principal, statutory interest, compensation, contractual recovery costs, official court fees, and payments.
- For costs incurred on Ledger B, `Calculators/RecoveryCostEligibility` must classify eligibility into:
  1. `CLIENT_COST_ONLY`
  2. `STATUTORY_REASONABLE_RECOVERY_COST`
  3. `CONTRACTUAL_RECOVERY_COST`
  4. `OFFICIAL_COURT_FEE`
- Mandatory disclosure: *"£X recovery cost incurred. Eligibility to add this to the amount claimed has been assessed under ruleset Y."*

#### Ledger B (FCD Client Account & Action-Based Authorizations)
- Tracks SaaS subscription and per-action escalation fees owed by client.
- Paid escalation actions require explicit user authorization.
- Every fee action must create immutable versioned pricing acceptance records.

## Pre-Overdue Contract Setup & Hygiene Workflow
- Capture legal entity data, VAT/addresses, PO requirements, payment terms, contractual late payment remedies, and proof artifacts.
- Any suggested contract clause must be marked: `"Requires Client Independent Legal Review"`.

## Technical Stack & Architecture Guidelines

### 1. Versioned Data & Rule Pack Schema
Load legal rules, pricing schedules, statutory rates, and court fees from versioned data contracts:
- `JURISDICTION_RULES`
- `PRICING_SCHEDULES`
- `STATUTORY_RATES`
- `COURT_FEE_SCHEDULES`

### 2. Tamper-Evident Evidence Ledger (Audit Log)
Append-only cryptographic event ledger with hash chaining:
- `current_event_hash = SHA256(event_id + timestamp + actor + payload + previous_event_hash)`
- Deny `UPDATE` and `DELETE` at DB permission level.

### 3. Multi-Factor Jurisdiction Engine
Use creditor/debtor location facts, contract clauses, and place of supply.
If ambiguity/conflict exists: `JURISDICTION_UNCERTAIN` -> `CLIENT_HANDOFF`.

## Jurisdictional Escalation Workflows & External Fees
- Scotland: Simple Procedure <= £5,000; SCTS fees treated as external court fees.
- England & Wales: PAP Debt Claims for sole trader/individual; corporate LBA; HMCTS fees treated as external.
- Northern Ireland: Small Claims <= £5,000; NI Direct fees treated as external; enforcement reference EJO.

## Statutory Calculation Engine (`Calculators/UKLatePayment`)
- Dynamic BoE base rate + 8%, fixed compensation bands, contractual override support.
- Record payload and rule version into debtor and tamper-evident ledgers.

## Circuit Breakers & Hard Stop Conditions
Immediate state shifts for:
1. `DISPUTE`
2. `BREATHING_SPACE`
3. `INSOLVENCY`
4. `PAYMENT_PLAN_REQUEST` / `PARTIALLY_PAID`
5. `CONSUMER_CREDIT`
6. `JURISDICTION_UNCERTAIN`

## Priority Coding Tasks for Copilot
1. Build `DualLedgerEngine` with strict ledger isolation.
2. Build append-only `InvoiceLedger` with signed export verification.
3. Implement versioned rule/fee/rate/court fee pack loaders.
4. Build `UKLatePayment` + `RecoveryCostEligibility`.
5. Build `EvidencePackCompiler` with dual-ledger breakdown and audit trail.
