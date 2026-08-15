import unittest

from unpaid_invoice_escalator.services.pre_overdue_hygiene_engine import PreOverdueHygieneEngine


class TestPreOverdueHygieneEngine(unittest.TestCase):
    def test_assess_identifies_missing_items_and_disclaimer(self) -> None:
        engine = PreOverdueHygieneEngine()
        assessment = engine.assess(
            creditor_legal_entity_name="",
            creditor_companies_house_number="SC123456",
            creditor_vat_number="GB123456789",
            creditor_trading_address="1 Example Street",
            debtor_legal_entity_name="Buyer Ltd",
            debtor_companies_house_number="NI654321",
            debtor_vat_number="GB987654321",
            debtor_trading_address="2 Example Road",
            po_required=True,
            po_reference="",
            payment_terms_days=0,
            contractual_interest_clause_present=False,
            contractual_recovery_clause_present=True,
            proof_of_delivery_required=False,
            suggested_clause_text="Draft clause",
        )
        self.assertFalse(assessment.checklist_complete)
        self.assertIn("Creditor legal entity name", assessment.missing_items)
        self.assertIn("Purchase order reference", assessment.missing_items)
        self.assertIn("Payment terms (days)", assessment.missing_items)
        self.assertIn("Contractual late-payment interest clause", assessment.missing_items)
        self.assertIn("Proof-of-delivery/acceptance requirement", assessment.missing_items)
        self.assertEqual(assessment.warning_tier, "NONE")
        self.assertEqual(assessment.format_warnings, ())
        self.assertTrue(assessment.suggested_clause_requires_legal_review)
        self.assertEqual(assessment.disclaimer, "Requires Client Independent Legal Review")

    def test_assess_assigns_warning_tier_for_format_issues(self) -> None:
        engine = PreOverdueHygieneEngine()
        assessment = engine.assess(
            creditor_legal_entity_name="First Cairn Digital Ltd",
            creditor_companies_house_number="BAD-123",
            creditor_vat_number="XX999",
            creditor_trading_address="1 Example Street",
            debtor_legal_entity_name="Buyer Ltd",
            debtor_companies_house_number="BAD-456",
            debtor_vat_number="YY999",
            debtor_trading_address="2 Example Road",
            po_required=False,
            po_reference=None,
            payment_terms_days=30,
            contractual_interest_clause_present=True,
            contractual_recovery_clause_present=True,
            proof_of_delivery_required=True,
            suggested_clause_text=None,
        )
        self.assertTrue(assessment.checklist_complete)
        self.assertEqual(assessment.warning_tier, "HIGH")
        self.assertEqual(len(assessment.format_warnings), 4)


if __name__ == "__main__":
    unittest.main()
