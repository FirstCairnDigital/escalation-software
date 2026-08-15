from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class FiveLedgerSummary:
    financial_balance_gbp: Decimal
    evidence_artifacts_count: int
    event_audit_events_count: int
    compliance_events_count: int
    fcd_billing_balance_gbp: Decimal


class FiveLedgerEngine:
    def __init__(self, *, store: SQLiteStore) -> None:
        self._store = store

    def summarize(self, *, invoice_id: str) -> FiveLedgerSummary:
        return FiveLedgerSummary(
            financial_balance_gbp=self._store.debtor_ledger_balance_for_invoice(invoice_id),
            evidence_artifacts_count=len(self._store.artifacts_for_invoice(invoice_id)),
            event_audit_events_count=len(self._store.events_for_invoice(invoice_id)),
            compliance_events_count=len(self._store.compliance_entries_for_invoice(invoice_id)),
            fcd_billing_balance_gbp=self._store.client_fee_balance_for_invoice(invoice_id),
        )
