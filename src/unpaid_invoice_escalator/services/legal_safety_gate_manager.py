from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

from unpaid_invoice_escalator.models import Actor, ComplianceLedgerEntry, Invoice
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


@dataclass(frozen=True)
class LegalSafetyGateResult:
    accepted: bool
    declaration_version: str
    disclaimer_text: str
    compliance_entry_id: str
    recorded_at: datetime


class LegalSafetyGateManager:
    DISCLAIMER_TEXT = (
        "Important Legal Notice: First Cairn Digital provides credit-control software and procedural information. "
        "It does not determine whether you are legally entitled to recover a debt and does not replace advice from "
        "a solicitor. You remain responsible for the accuracy of the claim and decisions about legal proceedings. "
        "Formal court proceedings involve costs and legal consequences. If liability, jurisdiction, limitation, or "
        "amounts are uncertain, stop and obtain professional legal advice."
    )
    DECLARATION_VERSION = "v1.0-legal-safety-gate"

    def __init__(self, *, store: SQLiteStore, event_ledger: InvoiceLedger) -> None:
        self._store = store
        self._event_ledger = event_ledger

    def confirm(
        self,
        *,
        invoice: Invoice,
        user_id: str,
        amount_claimed_gbp: Decimal,
        payments_recorded_gbp: Decimal,
        declarations: dict[str, bool],
    ) -> LegalSafetyGateResult:
        now = datetime.now(timezone.utc)
        compliance_entry = ComplianceLedgerEntry(
            entry_id=str(uuid4()),
            invoice_id=invoice.invoice_id,
            timestamp=now,
            event_type="LEGAL_SAFETY_GATE_ACCEPTED",
            details={
                "declaration_version": self.DECLARATION_VERSION,
                "user_id": user_id,
                "amount_claimed_gbp": str(amount_claimed_gbp),
                "payments_recorded_gbp": str(payments_recorded_gbp),
                "declarations": declarations,
                "disclaimer_text": self.DISCLAIMER_TEXT,
                "case_snapshot": {
                    "invoice_id": invoice.invoice_id,
                    "jurisdiction": invoice.jurisdiction.value,
                    "debtor_type": invoice.debtor_type.value,
                },
            },
        )
        self._store.append_compliance_entry(compliance_entry)
        self._event_ledger.append_event(
            invoice_id=invoice.invoice_id,
            actor=Actor.CLIENT,
            event_type="LEGAL_SAFETY_GATE_ACCEPTED",
            timestamp=now,
            data_payload={
                "compliance_entry_id": compliance_entry.entry_id,
                "declaration_version": self.DECLARATION_VERSION,
                "user_id": user_id,
            },
        )
        return LegalSafetyGateResult(
            accepted=True,
            declaration_version=self.DECLARATION_VERSION,
            disclaimer_text=self.DISCLAIMER_TEXT,
            compliance_entry_id=compliance_entry.entry_id,
            recorded_at=now,
        )
