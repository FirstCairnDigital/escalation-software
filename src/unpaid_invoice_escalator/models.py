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
    PRE_ACTION_NOTICE = "PRE_ACTION_NOTICE"
    OTHER = "OTHER"


class RecoveryCostCategory(str, Enum):
    CLIENT_COST_ONLY = "CLIENT_COST_ONLY"
    STATUTORY_REASONABLE_RECOVERY_COST = "STATUTORY_REASONABLE_RECOVERY_COST"
    CONTRACTUAL_RECOVERY_COST = "CONTRACTUAL_RECOVERY_COST"
    OFFICIAL_COURT_FEE = "OFFICIAL_COURT_FEE"


class DebtorLedgerEntryType(str, Enum):
    ORIGINAL_PRINCIPAL = "ORIGINAL_PRINCIPAL"
    STATUTORY_INTEREST = "STATUTORY_INTEREST"
    FIXED_COMPENSATION = "FIXED_COMPENSATION"
    CONTRACTUAL_RECOVERY_COST = "CONTRACTUAL_RECOVERY_COST"
    OFFICIAL_COURT_FEE = "OFFICIAL_COURT_FEE"
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
    BREATHING_SPACE_PAUSE = "BREATHING_SPACE_PAUSE"
    CLIENT_HANDOFF = "CLIENT_HANDOFF"
    RESOLVED_PAID = "RESOLVED_PAID"


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
