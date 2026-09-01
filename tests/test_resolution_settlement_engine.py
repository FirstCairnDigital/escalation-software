from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import (
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    DebtorType,
    Invoice,
    Jurisdiction,
    ReportedPayment,
    ReportedPaymentDecision,
    ReportedPaymentStatus,
    SettlementAcceptance,
    SettlementOffer,
)
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
            first_due_date = date.today() + timedelta(days=5)
            plan, installments = engine.propose_payment_plan(
                invoice_id=invoice.invoice_id,
                proposed_by="USER-1",
                proposer_role="CREDITOR",
                installment_amount_gbp=Decimal("100"),
                installment_count=2,
                first_due_date=first_due_date,
                frequency_days=30,
            )
            proposed = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date.today())
            self.assertEqual(proposed.status, "PROPOSED")
            engine.accept_payment_plan(plan_id=plan.plan_id, accepted_by="debtor", accepter_role="DEBTOR")
            active = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date.today())
            self.assertEqual(active.status, "ACTIVE")
            defaulted = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=first_due_date + timedelta(days=70))
            self.assertEqual(defaulted.status, "DEFAULTED")

            engine.record_confirmed_installment_payment(
                invoice_id=invoice.invoice_id,
                plan_id=plan.plan_id,
                installment_id=installments[0].installment_id,
                amount_gbp=Decimal("100"),
                recorded_by="USER-1",
            )
            engine.record_confirmed_installment_payment(
                invoice_id=invoice.invoice_id,
                plan_id=plan.plan_id,
                installment_id=installments[1].installment_id,
                amount_gbp=Decimal("100"),
                recorded_by="USER-1",
            )
            completed = engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date(2026, 4, 10))
            self.assertEqual(completed.status, "COMPLETED")

    def test_settlement_finalization_requires_confirmed_payment(self) -> None:
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
                expiry_date=date(2026, 12, 1),
            )
            engine.accept_settlement_offer(offer_id=offer.offer_id, accepted_by="debtor", accepter_role="DEBTOR")
            _, finalized = engine.accept_settlement_offer(
                offer_id=offer.offer_id, accepted_by="creditor", accepter_role="CREDITOR"
            )
            self.assertFalse(finalized)
            awaiting_payment = engine.settlement_offer_status(offer_id=offer.offer_id, as_of_date=date.today())
            self.assertEqual(awaiting_payment.status, "AWAITING_PAYMENT")

            store.append_reported_payment(
                ReportedPayment(
                    report_id="settlement-report-1",
                    invoice_id=invoice.invoice_id,
                    case_id="FCD-R-2026-000222",
                    debtor_identifier="debtor@example.com",
                    reported_at=datetime.now(timezone.utc),
                    amount_gbp=Decimal("900.00"),
                    payment_reference="SETTLEMENT-1",
                    payment_date=date(2026, 11, 20),
                    settlement_offer_id=offer.offer_id,
                )
            )
            store.append_debtor_ledger_entry(
                DebtorLedgerEntry(
                    entry_id="debtor-payment-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    entry_type=DebtorLedgerEntryType.PAYMENT_RECEIVED,
                    amount_gbp=Decimal("-900.00"),
                    description="Creditor confirmed settlement payment.",
                )
            )
            store.append_reported_payment_decision(
                ReportedPaymentDecision(
                    decision_id="settlement-decision-1",
                    report_id="settlement-report-1",
                    invoice_id=invoice.invoice_id,
                    decided_at=datetime.now(timezone.utc),
                    decided_by="USER-1",
                    status=ReportedPaymentStatus.PAYMENT_CONFIRMED_BY_CREDITOR,
                    confirmed_amount_gbp=Decimal("900.00"),
                    linked_debtor_entry_id="debtor-payment-1",
                )
            )

            finalization = engine.finalize_settlement_offer_if_paid(
                offer_id=offer.offer_id,
                finalized_by="USER-1",
                triggering_report_id="settlement-report-1",
            )
            self.assertIsNotNone(finalization)
            finalized_status = engine.settlement_offer_status(offer_id=offer.offer_id, as_of_date=date.today())
            self.assertEqual(finalized_status.status, "FINALIZED")
            self.assertEqual(store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("0.00"))
            events = store.events_for_invoice(invoice.invoice_id)
            self.assertTrue(any(evt.event_type == "SETTLEMENT_OFFER_FINALIZED" for evt in events))

    def test_settlement_offer_expiry_is_enforced(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "engine-3.db"))
            ledger = SQLiteInvoiceLedger(store)
            engine = ResolutionAndSettlementEngine(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-res-3",
                currency="GBP",
                principal_amount=Decimal("1000"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            utc_today = datetime.now(timezone.utc).date()

            boundary_offer = engine.propose_settlement_offer(
                invoice_id=invoice.invoice_id,
                offered_by="USER-1",
                offered_amount_gbp=Decimal("900"),
                expiry_date=utc_today,
            )
            self.assertEqual(
                engine.settlement_offer_status(offer_id=boundary_offer.offer_id, as_of_date=utc_today).status,
                "OPEN",
            )
            self.assertEqual(
                engine.settlement_offer_status(offer_id=boundary_offer.offer_id, as_of_date=utc_today + timedelta(days=1)).status,
                "EXPIRED",
            )

            valid_offer = engine.propose_settlement_offer(
                invoice_id=invoice.invoice_id,
                offered_by="USER-2",
                offered_amount_gbp=Decimal("800"),
                expiry_date=utc_today + timedelta(days=30),
            )
            engine.accept_settlement_offer(offer_id=valid_offer.offer_id, accepted_by="debtor", accepter_role="DEBTOR")
            engine.accept_settlement_offer(offer_id=valid_offer.offer_id, accepted_by="creditor", accepter_role="CREDITOR")
            self.assertEqual(
                engine.settlement_offer_status(offer_id=valid_offer.offer_id, as_of_date=utc_today).status,
                "AWAITING_PAYMENT",
            )

            expired_offer = engine.propose_settlement_offer(
                invoice_id=invoice.invoice_id,
                offered_by="USER-3",
                offered_amount_gbp=Decimal("700"),
                expiry_date=utc_today - timedelta(days=1),
            )
            with self.assertRaisesRegex(ValueError, "expired"):
                engine.accept_settlement_offer(offer_id=expired_offer.offer_id, accepted_by="debtor", accepter_role="DEBTOR")
            with self.assertRaisesRegex(ValueError, "expired"):
                engine.accept_settlement_offer(offer_id=expired_offer.offer_id, accepted_by="creditor", accepter_role="CREDITOR")
            self.assertEqual(engine.settlement_offer_status(offer_id=expired_offer.offer_id, as_of_date=utc_today).status, "EXPIRED")

            expired_finalization_offer = engine.propose_settlement_offer(
                invoice_id=invoice.invoice_id,
                offered_by="USER-4",
                offered_amount_gbp=Decimal("200"),
                expiry_date=utc_today - timedelta(days=2),
            )
            store.append_settlement_acceptance(
                SettlementAcceptance(
                    acceptance_id="accept-expired-1",
                    offer_id=expired_finalization_offer.offer_id,
                    invoice_id=invoice.invoice_id,
                    accepted_at=datetime.now(timezone.utc),
                    accepted_by="debtor",
                    accepter_role="DEBTOR",
                )
            )
            store.append_settlement_acceptance(
                SettlementAcceptance(
                    acceptance_id="accept-expired-2",
                    offer_id=expired_finalization_offer.offer_id,
                    invoice_id=invoice.invoice_id,
                    accepted_at=datetime.now(timezone.utc),
                    accepted_by="creditor",
                    accepter_role="CREDITOR",
                )
            )
            with self.assertRaisesRegex(ValueError, "expired"):
                engine.finalize_settlement_offer_if_paid(
                    offer_id=expired_finalization_offer.offer_id,
                    finalized_by="USER-1",
                    triggering_report_id=None,
                )

    def test_payment_plan_counter_offer_requires_counterparty_acceptance(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "engine-4.db"))
            ledger = SQLiteInvoiceLedger(store)
            engine = ResolutionAndSettlementEngine(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-res-4",
                currency="GBP",
                principal_amount=Decimal("500"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            first_due_date = date.today() + timedelta(days=7)
            plan, _ = engine.propose_payment_plan(
                invoice_id=invoice.invoice_id,
                proposed_by="debtor-portal",
                proposer_role="DEBTOR",
                installment_amount_gbp=Decimal("100"),
                installment_count=3,
                first_due_date=first_due_date,
                frequency_days=30,
            )
            counter_plan, _ = engine.propose_payment_plan(
                invoice_id=invoice.invoice_id,
                proposed_by="USER-1",
                proposer_role="CREDITOR",
                installment_amount_gbp=Decimal("125"),
                installment_count=3,
                first_due_date=first_due_date + timedelta(days=9),
                frequency_days=30,
                parent_plan_id=plan.plan_id,
            )
            self.assertEqual(engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=date.today()).status, "COUNTER_OFFERED")
            self.assertEqual(
                engine.payment_plan_status(plan_id=counter_plan.plan_id, as_of_date=date.today()).status,
                "COUNTER_OFFERED",
            )
            engine.accept_payment_plan(plan_id=counter_plan.plan_id, accepted_by="debtor", accepter_role="DEBTOR")
            self.assertEqual(engine.payment_plan_status(plan_id=counter_plan.plan_id, as_of_date=date.today()).status, "ACTIVE")


if __name__ == "__main__":
    unittest.main()
