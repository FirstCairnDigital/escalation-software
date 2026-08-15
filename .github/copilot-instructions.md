# GitHub Copilot System Specification: FCD Commercial Invoice Recovery Assistant

## Core Concept & Operating Boundaries
The system is an autonomous software-as-a-service application for **Credit Control, Tamper-Evident Evidence Assembly, Dual-Ledger Financial Management, Data Governance, and Procedural Recovery Workflows**.

- **DEFINITIVE PRODUCT BOUNDARY**:
  - The software helps businesses administer and document recovery of their own direct commercial trade invoices (B2B).
  - It provides **procedural information** and **prepares claim-ready evidence bundles**.
  - **CRITICAL**: The system is **NEVER** a debt collection agency, legal firm, process server, or FCA-regulated entity. It does **NOT** provide personalized legal advice, represent creditors, charge percentage recovery success commissions, file court proceedings directly, or conduct litigation.
  - **EXCLUSIONS**: Regulated consumer credit, sole-trader/individual personal loans, mortgages, residential rent, tax debts, insolvency proceedings, factored or purchased debts, or third-party collection.
  - **ABSOLUTE COURT HANDOFF BOUNDARY**:
    - FCD software operates strictly up to the pre-action phase. Once automated processing ends or a legal threshold is reached, the system executes `CLIENT_HANDOFF`.
    - **FCD CAN**: Monitor, remind, record, calculate, prepare, organize, explain procedural options, and compile structured evidence packs.
    - **FCD CANNOT**: Decide whether to sue, file proceedings on behalf of a client, conduct litigation, represent a client in court, provide solicitor representation, or enforce judgments.

## Data Governance, ICO Compliance & Security Architecture

### 1. Data Controller vs. Data Processor Model
- **Creditor (Client)**: Acts as the **Data Controller** under UK GDPR.
- **First Cairn Digital (FCD)**: Acts as the **Data Processor** for recovery-platform case data; acts as **Data Controller** only for own client-account, billing, platform security logs, and statutory records.
- **Regulatory Registration**: FCD maintains active ICO Data Protection Fee registration before processing personal data.

### 2. Dual Privacy Experiences & Debtor Transparency
- **Client/User Privacy Experience**: Detailed privacy policy for account management and telemetry.
- **Debtor Privacy Notice**: Every debtor communication includes explicit transparency information on behalf of the Data Controller.
- **Debtor Interaction & Rights Portal** links in all formal communications:
  - `[ I have already paid ]`
  - `[ I dispute this invoice ]`
  - `[ These details are incorrect ]`
  - `[ I need to contact the creditor ]`
  - `[ Data protection / privacy ]`
- **Marketing Isolation**: Debtor recovery communications must never contain promotions, upsells, or cross-sell content.

### 3. Special-Category Data & Sensitivity Handling
- Never duplicate/store special-category data in plain-text operational logs.
- On sensitive health/respite information, set `PROTECTED_RECOVERY_PAUSE = true`, store raw artifact only in encrypted restricted storage, and log only structured state flag.

### 4. System Security Standards
- **Authentication**: MFA required for administrative and client accounts.
- **Encryption**: TLS 1.3 in transit; AES-256 at rest. Short-lived signed URLs for document access.
- **Access Control**: Row-level multi-tenant isolation.
- **Auditability**: SHA-256 cryptographic event logs.
- **Compliance Goal**: Cyber Essentials-aligned architecture, with 72-hour ICO incident response procedures.

## 5-Ledger Compliance & Architectural Framework
Maintain five isolated ledgers per case; never merge or auto cross-post:
1. **Financial Ledger (Debtor / Ledger A)**: principal, interest, compensation, recovery costs, official court fees, payments/credits.
2. **Evidence Ledger**: append-only contracts/invoices/proof/correspondence with SHA-256 + metadata.
3. **Event/Audit Ledger**: chained actor events with timestamp and previous hash.
4. **Compliance Ledger**: privacy notices, data requests, disputes, restrictions, Breathing Space flags, rule versions, human approvals.
5. **FCD Billing Ledger (Ledger B)**: SaaS fees and explicit action-based charges.

## Pre-Overdue Contract Setup & Discrepancy Safeguards

### 1. Data Validation & False Information Fail-Safes
Confidence states:
- `UNVERIFIED`
- `CLIENT_ASSERTED`
- `DOCUMENT_SUPPORTED`
- `DEBTOR_CONFIRMED`
- `DISPUTED`
- `INCONSISTENT`
- `HUMAN_REVIEWED`

Automated discrepancy circuit breakers:
- If `claim_amount != invoice_file_extracted_amount` -> `AUTOMATION_STOPPED_DISCREPANCY`.
- If `(principal - payments_recorded) != outstanding_entered` -> block escalation until human reconciliation.

### 2. Pre-Overdue Contract Hygiene Engine
Validate:
- legal entities + Companies House numbers,
- VAT + addresses,
- PO requirements + proof of delivery,
- explicit late-payment remedy clauses.

Suggested clause disclaimer:
- `"Requires Client Independent Legal Review"`.

## Legal Safety Gates & Code-Enforced Circuit Breakers

### 1. Code-Enforced Declaration Gate
Before formal escalation, enforce explicit confirmations and write immutable accepted declaration to Event/Audit + Compliance ledgers including user ID, UTC timestamp, text version, and case snapshot.

### 2. Legal Disclaimer Safety Gate
Display legal notice that FCD provides software/procedural information only and is not legal representation/advice.

### 3. Hard Stop Conditions
Immediately halt and move to `DISPUTED`, `BREATHING_SPACE_PAUSE`, `RESTRICTED_DATA_PAUSE`, or `CLIENT_HANDOFF` if:
1. `debtor_feedback == 'DISPUTE'` or `debtor_feedback == 'DATA_INACCURATE'`
2. `system_flag == 'BREATHING_SPACE'` or `system_flag == 'INSOLVENCY'`
3. `debtor_type == 'CONSUMER_CREDIT'`
4. `jurisdiction == 'JURISDICTION_UNCERTAIN'`
5. `claim_amount != evidence_document_amount`

## Technical Stack & Versioned Architecture

### 1. Versioned Data & Rule Pack Schema
Never hardcode legal values. Load from versioned packs:
- `JURISDICTION_RULES`
- `PRICING_SCHEDULES`
- `STATUTORY_RATES`
- `COURT_FEE_SCHEDULES`
- `LEGAL_DISCLAIMERS_AND_TEMPLATES`

Required metadata:
- `rule_id`
- `version`
- `effective_date`
- `source_authority`
- `last_verified_date`
- `automation_allowed`
- `human_approval_required`

### 2. Cryptographic Audit Ledger Engine
Hash chain:
`current_event_hash = SHA256(event_id + timestamp + actor + payload + previous_event_hash)`

Database must be append-only (`UPDATE`/`DELETE` denied by role/policy).

## Jurisdictional Escalation Workflows & External Fees

### Scotland (`SCOTLAND`)
- Simple Procedure <= £5,000.
- SCTS fees:
  - <= £300: £23
  - £300.01–£5,000: £127
- > £5,000 -> immediate `CLIENT_HANDOFF` for solicitor/Ordinary Cause workflow.

### England & Wales (`ENGLAND_WALES`)
- Sole trader/individual -> PAP Debt Claims + mandatory 30-day delay.
- Limited company -> 14-day LBA.
- HMCTS issue fees:
  - <= £300: £35
  - £3,000.01–£5,000: £205
  - £5,000.01–£10,000: £455
  - > £10,000: 5% of claim
- Automation limit £10,000 -> handoff after protocol completion.

### Northern Ireland (`NORTHERN_IRELAND`)
- Small claims limit £5,000.
- NI fees:
  - <= £300: £49
  - £300.01–£500: £81
  - £500.01–£1,000: £113
  - £1,000.01–£3,000: £163
  - £3,000.01–£5,000: £244
- Enforcement reference must cite **EJO**.

## Statutory Calculation Engine (`Calculators/UKLatePayment`)
Daily statutory interest:
`Daily Interest = (Invoice Principal * (BoE Base Rate + 0.08)) / 365`

Pipeline:
1. Verify qualifying B2B transaction.
2. Respect contractual override if present.
3. Query dynamic BoE rate for overdue period.
4. Compute daily interest.
5. Apply fixed compensation:
   - < £1,000 -> £40
   - £1,000–£9,999.99 -> £70
   - >= £10,000 -> £100
6. Record details/rates/rule version into Financial + Event/Audit ledgers.

## Priority Coding Tasks for Copilot
1. Build `FiveLedgerEngine` for Financial, Evidence, Event/Audit, Compliance, and FCD Billing ledgers.
2. Build `DataDiscrepancyValidator` for claim vs artifact and payment math checks.
3. Build `LegalSafetyGateManager` for declarations/disclaimers and immutable logging.
4. Build `VersionedRulePackLoader` for rules/fees/rates/disclaimers/templates.
5. Build `EvidencePackCompiler` with invoices/contracts/proofs/5-ledger audit histories/pre-action notices for SCTS/MMCO/NI Direct handoff.
