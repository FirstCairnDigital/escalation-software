from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from unpaid_invoice_escalator.calculators.recovery_cost_eligibility import (
    RecoveryCostEligibilityCalculator,
    RecoveryCostEligibilityResult,
)
from unpaid_invoice_escalator.models import (
    Actor,
    ClientFeeAction,
    ClientFeeEntry,
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    Invoice,
    RecoveryCostCategory,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.rulepacks.fee_loader import FeePackLoader
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class LedgerBalances:
    debtor_ledger_balance: Decimal
    client_fee_balance: Decimal


class DualLedgerEngine:
    """Maintains strict separation between debtor claim ledger and FCD client fee ledger."""

    def __init__(
        self,
        *,
        store: SQLiteStore,
        event_ledger: InvoiceLedger,
        fee_pack_loader: FeePackLoader | None = None,
    ) -> None:
        self._store = store
        self._event_ledger = event_ledger
        self._fee_pack_loader = fee_pack_loader or FeePackLoader()

    def add_debtor_entry(
        self,
        *,
        invoice_id: str,
        entry_type: DebtorLedgerEntryType,
        amount_gbp: Decimal,
        description: str,
        recovery_cost_category: RecoveryCostCategory | None = None,
        linked_client_fee_entry_id: str | None = None,
    ) -> DebtorLedgerEntry:
        now = datetime.now(timezone.utc)
        entry = DebtorLedgerEntry(
            entry_id=str(uuid4()),
            invoice_id=invoice_id,
            timestamp=now,
            entry_type=entry_type,
            amount_gbp=amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            description=description,
            recovery_cost_category=recovery_cost_category,
            linked_client_fee_entry_id=linked_client_fee_entry_id,
        )
        self._store.append_debtor_ledger_entry(entry)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="DEBTOR_LEDGER_ENTRY_ADDED",
            timestamp=now,
            data_payload={
                "entry_id": entry.entry_id,
                "entry_type": entry.entry_type.value,
                "amount_gbp": str(entry.amount_gbp),
                "description": entry.description,
                "recovery_cost_category": (
                    None if entry.recovery_cost_category is None else entry.recovery_cost_category.value
                ),
                "linked_client_fee_entry_id": entry.linked_client_fee_entry_id,
            },
        )
        return entry

    def add_client_action_fee(
        self,
        *,
        case_id: str,
        client_id: str,
        invoice_id: str,
        action_selected: ClientFeeAction,
        accepted_by_user: str,
    ) -> ClientFeeEntry:
        now = datetime.now(timezone.utc)
        schedule = self._fee_pack_loader.load_pricing_schedule(now.date())
        fee_amount = schedule.action_fees[action_selected].quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        vat_amount = (fee_amount * schedule.vat_rate).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        entry = ClientFeeEntry(
            entry_id=str(uuid4()),
            case_id=case_id,
            client_id=client_id,
            invoice_id=invoice_id,
            timestamp=now,
            pricing_schedule_version=schedule.version,
            action_selected=action_selected,
            fee_amount_gbp=fee_amount,
            vat_gbp=vat_amount,
            accepted_by_user=accepted_by_user,
            external_fee=False,
        )
        self._store.append_client_fee_entry(entry)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="CLIENT_ACTION_FEE_ACCEPTED",
            timestamp=now,
            data_payload={
                "case_id": entry.case_id,
                "client_id": entry.client_id,
                "invoice_id": entry.invoice_id,
                "pricing_schedule_version": entry.pricing_schedule_version,
                "action_selected": entry.action_selected.value,
                "fee_amount_gbp": str(entry.fee_amount_gbp),
                "vat_gbp": str(entry.vat_gbp),
                "accepted_by_user": entry.accepted_by_user,
            },
        )
        return entry

    def quote_official_court_fee(self, *, invoice: Invoice, claim_value_gbp: Decimal) -> Decimal:
        now = datetime.now(timezone.utc).date()
        return self._fee_pack_loader.quote_court_fee(invoice.jurisdiction, claim_value_gbp, now)

    def assess_recovery_cost_eligibility(
        self,
        *,
        invoice_id: str,
        recovery_cost_gbp: Decimal,
        has_contractual_recovery_clause: bool,
        is_official_court_fee: bool,
        statutory_reasonable_recovery_allowed: bool,
    ) -> RecoveryCostEligibilityResult:
        result = RecoveryCostEligibilityCalculator.assess(
            has_contractual_recovery_clause=has_contractual_recovery_clause,
            is_official_court_fee=is_official_court_fee,
            statutory_reasonable_recovery_allowed=statutory_reasonable_recovery_allowed,
        )
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="RECOVERY_COST_ELIGIBILITY_ASSESSED",
            data_payload={
                "recovery_cost_gbp": str(recovery_cost_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)),
                "category": result.category.value,
                "ruleset": result.ruleset,
                "rationale": result.rationale,
                "disclosure": (
                    f"£{recovery_cost_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)} recovery cost incurred. "
                    f"Eligibility to add this to the amount claimed has been assessed under ruleset {result.ruleset}."
                ),
            },
        )
        return result

    def balances_for_invoice(self, invoice_id: str) -> LedgerBalances:
        return LedgerBalances(
            debtor_ledger_balance=self._store.debtor_ledger_balance_for_invoice(invoice_id),
            client_fee_balance=self._store.client_fee_balance_for_invoice(invoice_id),
        )

