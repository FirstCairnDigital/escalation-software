from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.resolution_settlement_engine import ResolutionAndSettlementEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestResolutionSettlementEngine(unittest.TestCase):
    def test_payment_plan_status_progression(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "engine.db"))
            ledger = SQLiteInvoiceLedger(store)
            engine = ResolutionAndSettlementEngine(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-res-1",
                currency="GBP",
                principal_amount=Decimal("500"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            plan, installments = engine.propose_payment_plan(
                invoice_id=invoice.invoice_id,
                proposed_by="USER-1",
                installment_amount_gbp=Decimal("100"),
                installment_count=2,
                first_due_date=date(2026, 2, 1),
                frequency_days=30,
            )
            active = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date(2026, 1, 31))
            self.assertEqual(active.status, "ACTIVE")
            defaulted = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date(2026, 4, 10))
            self.assertEqual(defaulted.status, "DEFAULTED")

            engine.record_installment_payment(
                invoice_id=invoice.invoice_id,
                plan_id=plan.plan_id,
                installment_id=installments[0].installment_id,
                amount_gbp=Decimal("100"),
                recorded_by="USER-1",
            )
            engine.record_installment_payment(
                invoice_id=invoice.invoice_id,
                plan_id=plan.plan_id,
                installment_id=installments[1].installment_id,
                amount_gbp=Decimal("100"),
                recorded_by="USER-1",
            )
            completed = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date(2026, 4, 10))
            self.assertEqual(completed.status, "COMPLETED")

    def test_settlement_finalization_applies_discount(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "engine-2.db"))
            ledger = SQLiteInvoiceLedger(store)
            engine = ResolutionAndSettlementEngine(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-res-2",
                currency="GBP",
                principal_amount=Decimal("1000"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            offer = engine.propose_settlement_offer(
                invoice_id=invoice.invoice_id,
                offered_by="USER-1",
                offered_amount_gbp=Decimal("900"),
                expiry_date=date(2026, 3, 1),
            )
            engine.accept_settlement_offer(offer_id=offer.offer_id, accepted_by="debtor", accepter_role="DEBTOR")
            _, finalized = engine.accept_settlement_offer(
                offer_id=offer.offer_id, accepted_by="creditor", accepter_role="CREDITOR"
            )
            self.assertTrue(finalized)
            events = store.events_for_invoice(invoice.invoice_id)
            self.assertTrue(any(evt.event_type == "SETTLEMENT_OFFER_FINALIZED" for evt in events))


if __name__ == "__main__":
    unittest.main()
