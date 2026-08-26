from datetime import date
from decimal import Decimal
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger
from unpaid_invoice_escalator.services.late_payment_engine import LatePaymentEngine


class TestLatePaymentEngine(unittest.TestCase):
    def test_eligible_calculation_and_ledger_logging(self) -> None:
        ledger = InvoiceLedger()
        engine = LatePaymentEngine(ledger=ledger)
        invoice = Invoice(
            invoice_id="inv-late-1",
            currency="GBP",
            principal_amount=Decimal("2000"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        result = engine.calculate(
            invoice=invoice,
            as_of_date=date(2026, 2, 10),
            is_commercial_transaction=True,
            base_rate_override=Decimal("0.05"),
        )
        self.assertTrue(result.eligible)
        self.assertIsNotNone(result.breakdown)
        events = ledger.events_for_invoice(invoice.invoice_id)
        self.assertEqual(events[-1].event_type, "LATE_PAYMENT_CALCULATION")
        self.assertEqual(events[-1].data_payload["rule_version"], result.rule_version)

    def test_eligible_calculation_uses_outstanding_amount(self) -> None:
        ledger = InvoiceLedger()
        engine = LatePaymentEngine(ledger=ledger)
        invoice = Invoice(
            invoice_id="inv-late-3",
            currency="GBP",
            principal_amount=Decimal("2000"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        result = engine.calculate(
            invoice=invoice,
            as_of_date=date(2026, 2, 10),
            is_commercial_transaction=True,
            base_rate_override=Decimal("0.05"),
            outstanding_amount=Decimal("500"),
        )
        self.assertTrue(result.eligible)
        self.assertIsNotNone(result.breakdown)
        self.assertEqual(result.breakdown.fixed_compensation, Decimal("40"))

    def test_ineligible_non_commercial(self) -> None:
        ledger = InvoiceLedger()
        engine = LatePaymentEngine(ledger=ledger)
        invoice = Invoice(
            invoice_id="inv-late-2",
            currency="GBP",
            principal_amount=Decimal("2000"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.SCOTLAND,
            debtor_type=DebtorType.LIMITED,
        )
        result = engine.calculate(
            invoice=invoice,
            as_of_date=date(2026, 2, 10),
            is_commercial_transaction=False,
        )
        self.assertFalse(result.eligible)
        self.assertIn("Non-commercial", result.reason)


if __name__ == "__main__":
    unittest.main()
