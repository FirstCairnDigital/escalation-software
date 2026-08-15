from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.viability_proportionality_calculator import ViabilityProportionalityCalculator


class TestViabilityProportionalityCalculator(unittest.TestCase):
    def test_disproportionate_notice(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "viability.db"))
            invoice = Invoice(
                invoice_id="inv-viability-1",
                currency="GBP",
                principal_amount=Decimal("100"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            calc = ViabilityProportionalityCalculator(store=store)
            result = calc.assess(
                invoice=invoice,
                on_date=date(2026, 2, 1),
                estimated_time_cost_gbp=Decimal("80"),
                company_status="ACTIVE",
            )
            self.assertTrue(result.disproportionate)
            self.assertIsNotNone(result.notice)

    def test_financial_distress_blocks(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "viability-2.db"))
            invoice = Invoice(
                invoice_id="inv-viability-2",
                currency="GBP",
                principal_amount=Decimal("500"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.SCOTLAND,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            calc = ViabilityProportionalityCalculator(store=store)
            result = calc.assess(
                invoice=invoice,
                on_date=date(2026, 2, 1),
                company_status="INSOLVENT",
            )
            self.assertTrue(result.blocked)


if __name__ == "__main__":
    unittest.main()
