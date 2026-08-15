from decimal import Decimal
import unittest

from unpaid_invoice_escalator.calculators.uk_late_payment import UKLatePaymentCalculator


class TestUKLatePaymentCalculator(unittest.TestCase):
    def test_compensation_thresholds(self) -> None:
        self.assertEqual(UKLatePaymentCalculator.fixed_compensation(Decimal("999.99")), Decimal("40"))
        self.assertEqual(UKLatePaymentCalculator.fixed_compensation(Decimal("1000")), Decimal("70"))
        self.assertEqual(UKLatePaymentCalculator.fixed_compensation(Decimal("10000")), Decimal("100"))

    def test_calculate_with_statutory_rate(self) -> None:
        result = UKLatePaymentCalculator.calculate(
            principal=Decimal("2000"),
            base_rate=Decimal("0.05"),
            overdue_days=10,
        )
        self.assertEqual(result.annual_rate, Decimal("0.13"))
        self.assertEqual(result.fixed_compensation, Decimal("70"))
        self.assertGreater(result.interest_amount, Decimal("0"))


if __name__ == "__main__":
    unittest.main()

