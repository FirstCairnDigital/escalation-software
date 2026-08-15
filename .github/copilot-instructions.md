# GitHub Copilot System Specification: FCD Controlled Commercial Debt-Resolution Workflow

## Core Concept & Product Philosophy
The system is an autonomous software-as-a-service application for **Credit Control, Controlled Commercial Debt-Resolution, Tamper-Evident Evidence Assembly, 5-Ledger Financial & Compliance Management, and Procedural Recovery Workflows**.

- **THE CORE PRODUCT PHILOSOPHY**:

> *"First Cairn Digital (FCD) makes it easier to recover a valid debt and harder to pursue an invalid one. Firm, factual, and progressive — court is not the default success state, resolution is."*

- **DEFINITIVE PRODUCT BOUNDARY**:

- The software helps businesses administer and document recovery of their own direct commercial trade invoices (B2B).
- It provides **procedural information**, facilitates **bilateral debt-resolution / payment plans**, and **prepares claim-ready evidence bundles**.
- **CRITICAL**: The system is **NEVER** a debt collection agency, legal firm, process server, or FCA-regulated entity. It does **NOT** provide personalized legal advice, represent creditors, charge percentage recovery success commissions, file court proceedings directly, or conduct litigation.
- **DEBTOR COACHING BAN**: FCD communicates facts and official procedural links, but **NEVER** coaches debtors on tactics to evade, delay, or frustrate payment of a valid commercial debt.
- **EXCLUSIONS**: Regulated consumer credit, sole-trader/individual personal loans, mortgages, residential rent, tax debts, insolvency proceedings, factored or purchased debts, or third-party collection.
- **ABSOLUTE COURT HANDOFF BOUNDARY**:

- FCD software operates strictly up to the pre-action phase. Once automated processing ends or a legal threshold is reached, the system executes `CLIENT_HANDOFF`:
- **FCD CAN**: Monitor, remind, record, calculate, prepare, organize, explain procedural options, offer settlement structures, and compile structured evidence packs.
- **FCD CANNOT**: Decide whether to sue, file proceedings on behalf of a client, conduct litigation, represent a client in court, provide solicitor representation, or enforce judgments.

## Red-Team Dual-Perspective Architecture

### 1. Creditor Safeguards & Pre-Escalation Gatekeeping

#### A. Pre-Escalation Invoice Health Check
Before any escalation step is unlocked, the system MUST execute a pre-flight validation check evaluating the claim against 16 structural criteria:

```
[ CASE HEALTH CHECK: INV-004821 ]
[✓] Correct customer legal entity         [✓] Description of work/goods
[✓] Invoice number & date verified        [✓] Amount agrees with contract/quote
[✓] Correct billing address               [✓] VAT numbers checked
[✓] Purchase order supplied (if required) [✓] Payment terms & due date established
[✓] Delivery / Acceptance proof attached   [✓] No unresolved credit notes
[✓] Direct payments checked               [✓] No known dispute
[✓] Creditor authority verified           [✓] Limitation period checked

CASE CONFIDENCE: READY / REVIEW / STOP
```

#### B. Devil’s Advocate Pre-Escalation Verification Engine
Before permitting a user to execute an escalation action, the core engine MUST independently evaluate counter-arguments against continuation:

- *Verification Queries*: Active disputes? Payment/credit discrepancy? Unverified delivery evidence? Pending settlement/promise-to-pay date unreached? Debtor data accuracy challenge pending? Insolvency/Breathing space flag?
- *Execution Rule*: If any counter-condition evaluates to `TRUE`, block automated escalation and present the explicit reason with a recommended resolution path.

#### C. Viability & Proportionality Calculator
Before escalating low-value debts or claims against financially distressed entities:

- Perform a public company status/insolvency check.
- Compare debt value against cumulative FCD action fees, anticipated court fees, and time expenditure.
- Display a mandatory notice if costs are disproportionate: *"Recovery costs and effort may be disproportionate to the amount outstanding (£X)."*

### 2. Debtor Protection, Transparency & Verification Portal (`/portal`)

#### A. Anti-Phishing Case Verification (`/verify`)

- All debtor communications MUST include an independent verification route using a non-sensitive case ID and verification code:

`firstcairndigital.co.uk/verify?case=FCD-R-2027-001847`

- The public verification endpoint confirms solely:

`"This is a genuine First Cairn Digital communication issued on behalf of [Creditor Name] regarding Invoice [Number]."` (No sensitive figures or personal data exposed prior to authentication).

#### B. Debtor Resolution Options
Every formal communication and portal view MUST provide clear, neutral resolution actions:

`[ Pay Full Balance Now ]` | `[ Confirm Payment Date ]` | `[ I Have Already Paid ]` | `[ Propose Payment Plan / Settlement ]` | `[ Ask Question About Invoice ]` | `[ Dispute All or Part of Amount ]` | `[ Correct Inaccurate Information ]` | `[ View Independent Legal Advice Links ]`

#### C. Code-Enforced Data Accuracy Challenge Workflow
When a debtor triggers `[ Correct Inaccurate Information ]` or `[ Dispute All or Part of Amount ]`:

1. Set `RECOVERY_RESTRICTED = TRUE` in the Compliance Ledger.
2. Freeze all automated chasers and escalation timers immediately.
3. Notify the creditor with the debtor's exact challenge payload.
4. Require creditor evidence upload or balance adjustment before recovery can resume.

#### D. Transparent "Source of Data" & Independent Advice
Debtor portal MUST state explicitly:

> *"First Cairn Digital holds your contact details as a Data Processor on behalf of [Creditor Name] (Data Controller) for the sole purpose of invoice administration. You may obtain independent legal or professional advice at any time from Citizens Advice, Business Debtline, or a solicitor."*

## Communication Severity & Tone Framework
Automation MUST progressively adapt communication tone based on case stage and facts. Manufactured panic, fake countdown timers, or misrepresenting legal status is **STRICTLY BANNED**.

**Stage Level****Stage Name****Communication Tone & Philosophy****LEVEL 0**Pre-Due CourtesyHelpful informational note; reminder of upcoming due date.**LEVEL 1**Friendly ReminderSoft check-in; assumption of administrative oversight or PO delay.**LEVEL 2**Overdue NotificationFormal reminder; clear balance breakdown and payment options.**LEVEL 3**Request for ResolutionFirm request for payment or formal dispute entry; offer of settlement/plan.**LEVEL 4**Formal NoticeNotice of Intent to escalate under commercial contract/late payment statutory rules.**LEVEL 5**Pre-Action Procedural NoticeStatutory/Pre-Action Protocol letter; explicit statement of procedural next steps.**LEVEL 6**Client HandoffAutomated processing ENDS. Case handed off for creditor decision / legal review.

## Complex Financial Ledger Engine (Ledger 1 Specification)
The Financial Ledger MUST support complex B2B accounting realities beyond simple invoice values.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       LEDGER 1: FINANCIAL BALANCE                       │
├─────────────────────────────────────────────────────────────────────────┤
│ (+) Original Invoice Principal                                          │
│ (-) Approved Credit Notes                                               │
│ (-) Verified Direct Payments / Partial Payments                        │
│ (-) Agreed Early Settlement Discounts                                   │
│ (-) Retention Amounts (Pending Completion)                              │
│ (-) Disputed Portion (Carved Out to Dispute Sub-Ledger)                  │
│ (+) Statutory Interest (BoE + 8%, dynamically paused on payment events) │
│ (+) Fixed Statutory Recovery Compensation (£40 / £70 / £100)           │
│ (+) Contractual Recovery Charges (where contractually valid)            │
├─────────────────────────────────────────────────────────────────────────┤
│ (=) AGREED NET OUTSTANDING CLAIM AMOUNT                                 │
└─────────────────────────────────────────────────────────────────────────┘
```

- **Immediate Cancellation Rule**: Upon entry of any payment or credit record, all pending automated communications MUST be cancelled instantly.
- **Pre-Send Balance Lock**: The system MUST perform a real-time recalculation and verification of the net outstanding balance immediately before dispatching any communication.

## Settlement & Debt-Resolution Engine
The engine prioritizes resolution through structured bilateral tools:

1. **Payment Plan Engine**:

- Allows debtors or creditors to propose installment schedules (e.g., £X/month over Y months).
- Generates timestamped, legally formatted "Promise to Pay" schedules.
- Automatically pauses chasers while installment payments are met; resumes gracefully at Level 2 if an installment defaults.

2. **Settlement Offer Engine**:

- Supports "Full & Final Settlement" proposals (e.g., pay £3,600 of £4,000 within 7 days to extinguish debt).
- Formalizes offers into timestamped agreement artifacts signed off by both parties.

3. **Dispute Carve-Out**:

- If £1,000 of a £5,000 invoice is disputed, the system allows the £4,000 undisputed balance to proceed through resolution while isolating the £1,000 into a `DISPUTE_REVIEW` state.

## 5-Ledger Architecture & Compliance Framework
The system MUST maintain five strictly isolated, independent ledgers per recovery case. Cross-posting entries between ledgers is **FORBIDDEN**.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                  RECOVERY CASE ENGINE                                  │
└──────┬──────────────────┬──────────────────┬──────────────────┬──────────────────┬─────┘
       │                  │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
│  LEDGER 1:   │   │  LEDGER 2:   │   │  LEDGER 3:   │   │  LEDGER 4:   │   │  LEDGER 5:   │
│  FINANCIAL   │   │   EVIDENCE   │   │ EVENT/AUDIT  │   │  COMPLIANCE  │   │ FCD BILLING  │
│  (Debtor)    │   │  ARTIFACTS   │   │  (Chained)   │   │ (GDPR & State│   │ (SaaS / Fees)│
└──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘   └──────────────┘
```

1. **Financial Ledger (Debtor Account)**: Tracks Net Principal, Credits, Payments, Retentions, Statutory/Contractual Interest, Fixed Charges, and Court Fees.
2. **Evidence Ledger**: Immutable append-only storage for contracts, invoices, proofs of delivery, POs, and correspondence. Stores document ID, SHA-256 hash, and upload metadata.
3. **Event/Audit Ledger**: Cryptographic event chain documenting every action (`SYSTEM`, `CLIENT`, `DEBTOR`), user ID, timestamp, delivery log, and previous block hash.
4. **Compliance Ledger**: Tracks privacy notices served, debtor data requests, dispute states, accuracy challenges, Breathing Space flags, welfare concerns, rule pack versions, and human approval declarations.
5. **FCD Billing Ledger (Client Account)**: Tracks SaaS subscription tier fees and per-action escalation charges. Requires explicit user action before writing a transaction record.

## Circuit Breakers & Humane Recovery Pauses
Automation MUST immediately halt and transition state under any of the following conditions:

```
                          ┌──────────────────────────┐
                          │    TRIGGER DETECTED      │
                          └────────────┬─────────────┘
                                       │
      ┌────────────────┬───────────────┼───────────────┬────────────────┐
      ▼                ▼               ▼               ▼                ▼
[ DEBTOR DISPUTE ] [ DATA ACCURACY ] [ WELFARE / ]   [ BREATHING ]    [ INSOLVENCY / ]
                   [   CHALLENGE  ]  [ VULNERABILITY] [   SPACE   ]   [ DISSOLUTION  ]
      │                │               │               │                │
      └────────────────┴───────────────┼───────────────┴────────────────┘
                                       ▼
                     ┌──────────────────────────────────┐
                     │   AUTOMATION KILL SWITCH ACTIVATED│
                     │  • Freeze All Chasers/Timers     │
                     │  • Record Event in Compliance L4 │
                     │  • Transition to HANDOFF / PAUSE │
                     └──────────────────────────────────┘
```

1. **Debtor Dispute / Accuracy Challenge**: `RECOVERY_RESTRICTED = TRUE`.
2. **Breathing Space / Debt Respite Scheme**: Mandatory pause for protected statutory period.
3. **Welfare & Vulnerability Concern**: Set `HUMANE_PAUSE = TRUE`. Log minimal necessary details, restrict access to raw medical notices, and pause all automated messages.
4. **Insolvency / Deceased / Dissolved**: Transition case immediately to `CLIENT_HANDOFF` with appropriate procedural guidance.
5. **System Balance Correction**: If an error is identified, the system MUST NOT overwrite history. It writes an `ERROR_CORRECTED` log into Ledger 3, issues a formal withdrawal notice of the incorrect communication, and dispatches a corrected statement.

## Versioned Technical Architecture
All rules, fee structures, thresholds, and notice wording MUST be loaded dynamically from versioned rule packs. **NEVER** hardcode regulatory values in source code.

```
CORE ENGINE (State Machine, 5 Ledgers, Circuit Breakers, Resolution Engine)
       │
       ▼
VERSIONED RULE & FEE PACKS
  ├── JURISDICTION_RULES (E&W, Scotland, Northern Ireland)
  ├── PRICING_SCHEDULES (SaaS Tiers & Per-Action Fees)
  ├── STATUTORY_RATES (BoE Base Rate, Late Payment Compensation)
  ├── COURT_FEE_SCHEDULES (HMCTS, SCTS, NI Direct Portal Fees)
  ├── COMMUNICATION_TEMPLATES (Severity Levels 0-6)
  └── LEGAL_DISCLAIMERS_AND_TEMPLATES (Versioned Notice Texts)
```

## Jurisdictional Escalation Workflows & External Fees

### Branch A: Scotland (`SCOTLAND`)

- **Small Claims Limit**: Simple Procedure threshold applies at **£5,000 or less** (SCTS Civil Online).
- **SCTS Court Fees (Separated in UI from FCD fees)**:

- Claims ≤ £300: **£23**
- Claims £300.01–£5,000: **£127** (Paid directly to SCTS; never marked as FCD revenue).
- **Workflow**:

- Claims ≤ £5,000: Auto-generate resolution options and formal demands. Upon expiry, compile **SCTS Civil Online Form 3A Evidence Pack** -> `CLIENT_HANDOFF`.
- Claims > £5,000: Auto-escalate ONLY to Formal Notice. Immediately transition to `CLIENT_HANDOFF` (*"Exceeds automated workflow limit (£5,000). Export Evidence Pack for Ordinary Cause / Scottish Solicitor review"*).

### Branch B: England & Wales (`ENGLAND_WALES`)

- **Debtor Type Routing**:

- `SOLE_TRADER` or `INDIVIDUAL`: Trigger **Pre-Action Protocol for Debt Claims**. Issue Letter of Claim, Reply Form, and Information Sheet. Apply a **mandatory 30-day delay timer**.
- `LIMITED` / Corporate B2B: Issue formal 14-day Letter Before Action.
- **HMCTS Court Issue Fees (Separated in UI)**:

- Up to £300: **£35** | £3,000.01–£5,000: **£205** | £5,000.01–£10,000: **£455** | > £10,000: **5% of claim value**.
- **Automation Limit (`FCD_AUTOMATION_LIMIT = £10,000`)**: Assemble **Money Claim Online (MMCO) / County Court Evidence Pack** -> `CLIENT_HANDOFF`.

### Branch C: Northern Ireland (`NORTHERN_IRELAND`)

- **Small Claims Limit**: **£5,000** (processed via NI Direct portal).
- **Pre-Action Protocol**: Apply **County Court Commercial Actions Pre-Action Protocol**.
- **NI Small Claims Court Fees (Separated in UI)**:

- Up to £300: **£49** | £300.01–£500: **£81** | £500.01–£1,000: **£113** | £1,000.01–£3,000: **£163** | £3,000.01–£5,000: **£244**.
- **Enforcement Body**: Specify the **Enforcement of Judgments Office (EJO)** for NI judgment enforcement documentation.

## Priority Coding Tasks for Copilot

1. **Build `FiveLedgerEngine`**: Implement isolated sub-engines for `FinancialLedger` (1), `EvidenceLedger` (2), `EventAuditLedger` (3), `ComplianceLedger` (4), and `FCDBillingLedger` (5).
2. **Build `CaseHealthCheck` & `DevilsAdvocateEngine`**: Construct pre-escalation validation rules and automated counter-argument checks to block invalid or risky escalations.
3. **Build `ResolutionAndSettlementEngine`**: Implement installment plan generators, settlement agreement workflows, and partial dispute carve-outs.
4. **Build `DebtorVerificationPortal` (`/portal` & `/verify`)**: Build anti-phishing case validation, transparent non-confrontational resolution options, and data accuracy challenge mechanisms.
5. **Build `EvidencePackCompiler`**: Implement PDF export generation compiling invoices, contracts, delivery proofs, 5-ledger audit histories, and pre-action notices tailored for SCTS Civil Online, MMCO, or NI Direct court handoffs.
