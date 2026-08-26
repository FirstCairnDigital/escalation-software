from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any


class Jurisdiction(str, Enum):
    SCOTLAND = "SCOTLAND"
    ENGLAND_WALES = "ENGLAND_WALES"
    NORTHERN_IRELAND = "NORTHERN_IRELAND"


class DebtorType(str, Enum):
    LIMITED = "LIMITED"
    SOLE_TRADER = "SOLE_TRADER"
    INDIVIDUAL = "INDIVIDUAL"
    CONSUMER_CREDIT = "CONSUMER_CREDIT"


class Actor(str, Enum):
    SYSTEM = "SYSTEM"
    CLIENT = "CLIENT"
    DEBTOR = "DEBTOR"


class ArtifactType(str, Enum):
    CONTRACT = "CONTRACT"
    PROOF_OF_DELIVERY = "PROOF_OF_DELIVERY"
    PAYMENT_EVIDENCE = "PAYMENT_EVIDENCE"
    PRE_ACTION_NOTICE = "PRE_ACTION_NOTICE"
    PROMISE_TO_PAY = "PROMISE_TO_PAY"
    FULL_AND_FINAL_SETTLEMENT = "FULL_AND_FINAL_SETTLEMENT"
    OTHER = "OTHER"


class RecoveryCostCategory(str, Enum):
    CLIENT_COST_ONLY = "CLIENT_COST_ONLY"
    STATUTORY_REASONABLE_RECOVERY_COST = "STATUTORY_REASONABLE_RECOVERY_COST"
    CONTRACTUAL_RECOVERY_COST = "CONTRACTUAL_RECOVERY_COST"
    OFFICIAL_COURT_FEE = "OFFICIAL_COURT_FEE"


class DebtorLedgerEntryType(str, Enum):
    ORIGINAL_PRINCIPAL = "ORIGINAL_PRINCIPAL"
    CREDIT_NOTE = "CREDIT_NOTE"
    STATUTORY_INTEREST = "STATUTORY_INTEREST"
    FIXED_COMPENSATION = "FIXED_COMPENSATION"
    CONTRACTUAL_RECOVERY_COST = "CONTRACTUAL_RECOVERY_COST"
    OFFICIAL_COURT_FEE = "OFFICIAL_COURT_FEE"
    SETTLEMENT_DISCOUNT = "SETTLEMENT_DISCOUNT"
    RETENTION_HOLD = "RETENTION_HOLD"
    DISPUTED_CARVE_OUT = "DISPUTED_CARVE_OUT"
    PAYMENT_RECEIVED = "PAYMENT_RECEIVED"
    ADJUSTMENT = "ADJUSTMENT"


class ClientFeeAction(str, Enum):
    MONTHLY_SAAS_TIER = "MONTHLY_SAAS_TIER"
    FORMAL_ESCALATION = "FORMAL_ESCALATION"
    NOTICE_PACK = "NOTICE_PACK"
    PRE_ACTION_PACK = "PRE_ACTION_PACK"
    COURT_READY_PACK = "COURT_READY_PACK"
    REVIEW_SETUP_SERVICE = "REVIEW_SETUP_SERVICE"


class InvoiceState(str, Enum):
    ISSUED = "ISSUED"
    FRIENDLY_REMINDER = "FRIENDLY_REMINDER"
    OVERDUE_CHASER = "OVERDUE_CHASER"
    FORMAL_NOTICE = "FORMAL_NOTICE"
    PRE_ACTION_PROTOCOL = "PRE_ACTION_PROTOCOL"
    JURISDICTION_UNCERTAIN = "JURISDICTION_UNCERTAIN"
    DISPUTED = "DISPUTED"
    DISPUTE_REVIEW = "DISPUTE_REVIEW"
    BREATHING_SPACE_PAUSE = "BREATHING_SPACE_PAUSE"
    CLIENT_HANDOFF = "CLIENT_HANDOFF"
    RESOLVED_PAID = "RESOLVED_PAID"


class CommunicationDeliveryState(str, Enum):
    CREATED = "CREATED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    DELIVERED = "DELIVERED"
    OPENED = "OPENED"
    BOUNCED = "BOUNCED"
    REJECTED = "REJECTED"
    RETURNED = "RETURNED"
    CANCELLED = "CANCELLED"


class RetentionVariant(str, Enum):
    STANDARD_COMMERCIAL = "STANDARD_COMMERCIAL"
    SCOTTISH_SIMPLE_PROCEDURE = "SCOTTISH_SIMPLE_PROCEDURE"
    VAT_TAX_AUDIT = "VAT_TAX_AUDIT"
    LEGAL_HOLD_ACTIVE = "LEGAL_HOLD_ACTIVE"


class LegalHoldType(str, Enum):
    LITIGATION_PENDING = "LITIGATION_PENDING"
    SBC_ADJUDICATION = "SBC_ADJUDICATION"
    REGULATORY_INQUIRY = "REGULATORY_INQUIRY"
    TAX_AUDIT = "TAX_AUDIT"


class ConfirmationOfPayeeResult(str, Enum):
    EXACT_MATCH = "EXACT_MATCH"
    CLOSE_MATCH = "CLOSE_MATCH"
    NO_MATCH = "NO_MATCH"


class BankDetailVerificationState(str, Enum):
    COP_UNVERIFIED = "COP_UNVERIFIED"
    COP_EXACT_MATCH = "COP_EXACT_MATCH"
    COP_CLOSE_MATCH = "COP_CLOSE_MATCH"
    COP_FAILED = "COP_FAILED"


@dataclass(frozen=True)
class Invoice:
    invoice_id: str
    currency: str
    principal_amount: Decimal
    issue_date: date
    due_date: date
    jurisdiction: Jurisdiction
    debtor_type: DebtorType


@dataclass(frozen=True)
class EvidenceArtifact:
    document_id: str
    invoice_id: str
    artifact_type: ArtifactType
    file_hash: str
    file_path: str
    upload_timestamp: datetime
    user_id: str


@dataclass(frozen=True)
class LedgerEvent:
    event_id: str
    invoice_id: str
    timestamp: datetime
    actor: Actor
    event_type: str
    data_payload: dict[str, Any] = field(default_factory=dict)
    previous_hash: str = "GENESIS"
    hash: str = ""


@dataclass(frozen=True)
class EngineDecision:
    next_state: InvoiceState
    outreach_frozen: bool
    instructions: str
    documents_to_generate: tuple[str, ...] = ()
    wait_until: date | None = None


@dataclass(frozen=True)
class DebtorLedgerEntry:
    entry_id: str
    invoice_id: str
    timestamp: datetime
    entry_type: DebtorLedgerEntryType
    amount_gbp: Decimal
    description: str
    recovery_cost_category: RecoveryCostCategory | None = None
    linked_client_fee_entry_id: str | None = None


@dataclass(frozen=True)
class ClientFeeEntry:
    entry_id: str
    case_id: str
    client_id: str
    invoice_id: str
    timestamp: datetime
    pricing_schedule_version: str
    action_selected: ClientFeeAction
    fee_amount_gbp: Decimal
    vat_gbp: Decimal
    accepted_by_user: str
    external_fee: bool = False


@dataclass(frozen=True)
class PreOverdueHygieneRecord:
    record_id: str
    invoice_id: str
    timestamp: datetime
    creditor_legal_entity_name: str
    creditor_companies_house_number: str
    creditor_vat_number: str
    creditor_trading_address: str
    debtor_legal_entity_name: str
    debtor_companies_house_number: str
    debtor_vat_number: str
    debtor_trading_address: str
    po_required: bool
    po_reference: str | None
    payment_terms_days: int
    contractual_interest_clause_present: bool
    contractual_recovery_clause_present: bool
    proof_of_delivery_required: bool
    suggested_clause_text: str | None
    suggested_clause_requires_legal_review: bool
    checklist_complete: bool
    missing_items: tuple[str, ...] = ()
    warning_tier: str = "NONE"
    format_warnings: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True)
class ComplianceLedgerEntry:
    entry_id: str
    invoice_id: str
    timestamp: datetime
    event_type: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class AuditTrailEntry:
    entry_id: str
    invoice_id: str
    timestamp: datetime
    category: str
    action: str
    actor: str
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class DebtorVerificationCase:
    case_id: str
    invoice_id: str
    creditor_name: str
    invoice_reference: str
    verification_code_hash: str
    created_at: datetime


class ReportedPaymentStatus(str, Enum):
    PAYMENT_VERIFICATION_PENDING = "PAYMENT_VERIFICATION_PENDING"
    NEEDS_EVIDENCE = "NEEDS_EVIDENCE"
    PAYMENT_CONFIRMED_BY_CREDITOR = "PAYMENT_CONFIRMED_BY_CREDITOR"
    PAYMENT_NOT_VERIFIED = "PAYMENT_NOT_VERIFIED"


@dataclass(frozen=True)
class ReportedPayment:
    report_id: str
    invoice_id: str
    case_id: str
    debtor_identifier: str
    reported_at: datetime
    amount_gbp: Decimal
    payment_reference: str = ""
    payment_date: date | None = None
    details: str = ""
    plan_id: str | None = None
    installment_id: str | None = None
    settlement_offer_id: str | None = None


class PaymentPlanDecisionStatus(str, Enum):
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    WITHDRAWN = "WITHDRAWN"
    EXPIRED = "EXPIRED"
    ACTIVATED = "ACTIVATED"


@dataclass(frozen=True)
class ReportedPaymentDecision:
    decision_id: str
    report_id: str
    invoice_id: str
    decided_at: datetime
    decided_by: str
    status: ReportedPaymentStatus
    reason: str = ""
    notes: str = ""
    confirmed_amount_gbp: Decimal | None = None
    linked_debtor_entry_id: str | None = None


@dataclass(frozen=True)
class ReportedPaymentEvidenceLink:
    link_id: str
    report_id: str
    invoice_id: str
    document_id: str
    linked_at: datetime
    linked_by: str


@dataclass(frozen=True)
class PaymentPlanAgreement:
    plan_id: str
    invoice_id: str
    created_at: datetime
    proposed_by: str
    installment_amount_gbp: Decimal
    installment_count: int
    first_due_date: date
    frequency_days: int
    notes: str = ""
    proposer_role: str = "CREDITOR"
    parent_plan_id: str | None = None
    version_number: int = 1


@dataclass(frozen=True)
class PaymentPlanInstallment:
    installment_id: str
    plan_id: str
    invoice_id: str
    due_date: date
    amount_gbp: Decimal
    sequence_number: int


@dataclass(frozen=True)
class PaymentPlanPayment:
    payment_id: str
    plan_id: str
    installment_id: str
    invoice_id: str
    paid_at: datetime
    amount_gbp: Decimal
    recorded_by: str
    reported_payment_id: str | None = None


@dataclass(frozen=True)
class PaymentPlanDecision:
    decision_id: str
    plan_id: str
    invoice_id: str
    decided_at: datetime
    decided_by: str
    actor_role: str
    status: PaymentPlanDecisionStatus
    notes: str = ""


@dataclass(frozen=True)
class SettlementOffer:
    offer_id: str
    invoice_id: str
    offered_at: datetime
    offered_by: str
    offered_amount_gbp: Decimal
    expiry_date: date
    notes: str = ""


@dataclass(frozen=True)
class SettlementAcceptance:
    acceptance_id: str
    offer_id: str
    invoice_id: str
    accepted_at: datetime
    accepted_by: str
    accepter_role: str


@dataclass(frozen=True)
class SettlementOfferFinalization:
    finalization_id: str
    offer_id: str
    invoice_id: str
    finalized_at: datetime
    finalized_by: str
    triggering_report_id: str | None
    confirmed_payment_total_gbp: Decimal
    outstanding_before_gbp: Decimal
    settlement_discount_applied_gbp: Decimal


@dataclass(frozen=True)
class DisputeCarveOut:
    carve_out_id: str
    invoice_id: str
    created_at: datetime
    disputed_amount_gbp: Decimal
    undisputed_amount_gbp: Decimal
    reason: str
    created_by: str


@dataclass(frozen=True)
class CommunicationRecord:
    communication_id: str
    invoice_id: str
    channel: str
    recipient: str
    subject: str
    body_summary: str
    automated: bool
    created_at: datetime


@dataclass(frozen=True)
class CommunicationDeliveryEvent:
    event_id: str
    communication_id: str
    invoice_id: str
    state: CommunicationDeliveryState
    timestamp: datetime
    note: str = ""


@dataclass(frozen=True)
class SettlementBankDetailRecord:
    record_id: str
    invoice_id: str
    created_at: datetime
    updated_by: str
    account_holder_name: str
    sort_code: str
    account_number_last4: str
    iban_last4: str | None
    cop_state: BankDetailVerificationState
    cop_result: ConfirmationOfPayeeResult | None = None
    expected_payee_name: str | None = None
    dual_control_approved_by: str | None = None
    mfa_reauthenticated: bool = False
