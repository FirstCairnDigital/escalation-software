from datetime import date
from decimal import Decimal
import unittest

from unpaid_invoice_escalator.models import ClientFeeAction, Jurisdiction
from unpaid_invoice_escalator.rulepacks.fee_loader import FeePackLoader


class TestFeePackLoader(unittest.TestCase):
    def test_pricing_schedule_and_court_quote(self) -> None:
        loader = FeePackLoader()
        schedule = loader.load_pricing_schedule(date(2026, 8, 15))
        self.assertEqual(schedule.version, "v1.2-2026Q3")
        self.assertEqual(schedule.action_fees[ClientFeeAction.FORMAL_ESCALATION], Decimal("9.95"))

        fee_ew_mid = loader.quote_court_fee(Jurisdiction.ENGLAND_WALES, Decimal("1250"), date(2026, 8, 15))
        self.assertEqual(fee_ew_mid, Decimal("80"))
        fee_ew = loader.quote_court_fee(Jurisdiction.ENGLAND_WALES, Decimal("12000"), date(2026, 8, 15))
        self.assertEqual(fee_ew, Decimal("600.00"))
        fee_scotland = loader.quote_court_fee(Jurisdiction.SCOTLAND, Decimal("250"), date(2026, 8, 15))
        self.assertEqual(fee_scotland, Decimal("23"))


if __name__ == "__main__":
    unittest.main()
