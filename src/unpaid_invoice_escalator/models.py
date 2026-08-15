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
