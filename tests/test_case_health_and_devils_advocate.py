import unittest

from unpaid_invoice_escalator.services.case_health_check import CaseHealthCheck
from unpaid_invoice_escalator.services.devils_advocate_engine import DevilsAdvocateEngine


class TestCaseHealthAndDevilsAdvocate(unittest.TestCase):
    def test_case_health_ready(self) -> None:
        engine = CaseHealthCheck()
        criteria = {
            "correct_customer_legal_entity": True,
            "description_of_goods_or_services": True,
            "invoice_number_and_date_verified": True,
            "amount_matches_contract_or_quote": True,
            "correct_billing_address": True,
            "vat_numbers_checked": True,
            "purchase_order_supplied_if_required": True,
            "payment_terms_and_due_date_established": True,
            "delivery_or_acceptance_proof_attached": True,
            "no_unresolved_credit_notes": True,
            "direct_payments_checked": True,
            "no_known_dispute": True,
            "creditor_authority_verified": True,
            "limitation_period_checked": True,
            "debtor_contact_details_verified": True,
            "court_handoff_boundary_acknowledged": True,
        }
        result = engine.evaluate(criteria=criteria)
        self.assertEqual(result.confidence, "READY")
        self.assertEqual(result.failed_criteria, ())

    def test_case_health_stop_on_critical_failure(self) -> None:
        engine = CaseHealthCheck()
        result = engine.evaluate(criteria={"correct_customer_legal_entity": False})
        self.assertEqual(result.confidence, "STOP")

    def test_devils_advocate_blocks(self) -> None:
        engine = DevilsAdvocateEngine()
        result = engine.evaluate(
            active_dispute=False,
            payment_or_credit_discrepancy=True,
            delivery_evidence_unverified=False,
            settlement_pending_and_not_due=False,
            data_accuracy_challenge_pending=True,
            insolvency_or_breathing_space_flag=False,
        )
        self.assertTrue(result.blocked)
        self.assertEqual(len(result.reasons), 2)


if __name__ == "__main__":
    unittest.main()
