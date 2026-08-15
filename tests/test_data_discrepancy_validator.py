from decimal import Decimal
import unittest

from unpaid_invoice_escalator.services.data_discrepancy_validator import DataDiscrepancyValidator


class TestDataDiscrepancyValidator(unittest.TestCase):
    def test_valid_amounts(self) -> None:
        validator = DataDiscrepancyValidator()
        result = validator.validate(
            claim_amount=Decimal("1000"),
            evidence_document_amount=Decimal("1000"),
            principal=Decimal("1000"),
            payments_recorded=Decimal("100"),
            outstanding_entered=Decimal("900"),
        )
        self.assertTrue(result.valid)
        self.assertEqual(result.status, "VALIDATED")
        self.assertFalse(result.circuit_breaker_triggered)

    def test_discrepancy_triggers_stop(self) -> None:
        validator = DataDiscrepancyValidator()
        result = validator.validate(
            claim_amount=Decimal("1000"),
            evidence_document_amount=Decimal("999"),
            principal=Decimal("1000"),
            payments_recorded=Decimal("100"),
            outstanding_entered=Decimal("850"),
        )
        self.assertFalse(result.valid)
        self.assertEqual(result.status, "AUTOMATION_STOPPED_DISCREPANCY")
        self.assertTrue(result.circuit_breaker_triggered)
        self.assertEqual(result.suggested_state, "CLIENT_HANDOFF")
        self.assertEqual(len(result.reasons), 2)


if __name__ == "__main__":
    unittest.main()
