from datetime import date, timedelta
from decimal import Decimal
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.services.jurisdiction_engine import EscalationContext, JurisdictionEngine


class TestJurisdictionEngine(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = JurisdictionEngine()

    def test_scotland_over_5k_immediate_handoff(self) -> None:
        invoice = Invoice(
            invoice_id="inv-sco-1",
            currency="GBP",
            principal_amount=Decimal("6500"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.SCOTLAND,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(current_state=InvoiceState.ISSUED, today=date(2026, 2, 1)),
        )
        self.assertEqual(decision.next_state, InvoiceState.CLIENT_HANDOFF)
        self.assertTrue(decision.outreach_frozen)

    def test_ew_sole_trader_starts_30_day_protocol(self) -> None:
        today = date(2026, 2, 1)
        invoice = Invoice(
            invoice_id="inv-ew-1",
            currency="GBP",
            principal_amount=Decimal("500"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.SOLE_TRADER,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(current_state=InvoiceState.OVERDUE_CHASER, today=today),
        )
        self.assertEqual(decision.next_state, InvoiceState.PRE_ACTION_PROTOCOL)
        self.assertEqual(decision.wait_until, today + timedelta(days=30))

    def test_circuit_breaker_dispute(self) -> None:
        invoice = Invoice(
            invoice_id="inv-ew-2",
            currency="GBP",
            principal_amount=Decimal("1800"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 20),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.FORMAL_NOTICE,
                today=date(2026, 2, 1),
                debtor_feedback="DISPUTE",
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.DISPUTED)
        self.assertTrue(decision.outreach_frozen)

    def test_ew_over_10k_returns_solicitor_pack(self) -> None:
        invoice = Invoice(
            invoice_id="inv-ew-3",
            currency="GBP",
            principal_amount=Decimal("15000"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 20),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.FORMAL_NOTICE,
                today=date(2026, 2, 20),
                state_entered_on=date(2026, 2, 1),
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.CLIENT_HANDOFF)
        self.assertEqual(decision.documents_to_generate, ("County Court / Solicitor Briefing Pack",))

    def test_ni_above_5k_handoff_pack(self) -> None:
        invoice = Invoice(
            invoice_id="inv-ni-1",
            currency="GBP",
            principal_amount=Decimal("6500"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 20),
            jurisdiction=Jurisdiction.NORTHERN_IRELAND,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.FORMAL_NOTICE,
                today=date(2026, 2, 20),
                state_entered_on=date(2026, 2, 1),
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.CLIENT_HANDOFF)
        self.assertEqual(decision.documents_to_generate, ("County Court Civil Bill / NI Solicitor Briefing Pack",))
        self.assertIn("EJO", decision.instructions)

    def test_contract_clause_conflict_routes_to_jurisdiction_uncertain(self) -> None:
        from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts

        invoice = Invoice(
            invoice_id="inv-jur-1",
            currency="GBP",
            principal_amount=Decimal("1200"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.ISSUED,
                today=date(2026, 2, 1),
                jurisdiction_facts=JurisdictionFacts(contract_jurisdiction=Jurisdiction.SCOTLAND),
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.JURISDICTION_UNCERTAIN)
        self.assertTrue(decision.outreach_frozen)

    def test_ni_sole_trader_uses_30_day_protocol(self) -> None:
        today = date(2026, 2, 1)
        invoice = Invoice(
            invoice_id="inv-ni-2",
            currency="GBP",
            principal_amount=Decimal("2800"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 10),
            jurisdiction=Jurisdiction.NORTHERN_IRELAND,
            debtor_type=DebtorType.SOLE_TRADER,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(current_state=InvoiceState.OVERDUE_CHASER, today=today),
        )
        self.assertEqual(decision.next_state, InvoiceState.PRE_ACTION_PROTOCOL)
        self.assertEqual(decision.wait_until, today + timedelta(days=30))

    def test_insolvency_system_flag_forces_handoff(self) -> None:
        invoice = Invoice(
            invoice_id="inv-stop-1",
            currency="GBP",
            principal_amount=Decimal("1800"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 20),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.FORMAL_NOTICE,
                today=date(2026, 2, 1),
                system_flag="INSOLVENCY",
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.CLIENT_HANDOFF)
        self.assertTrue(decision.outreach_frozen)

    def test_payment_plan_feedback_forces_handoff(self) -> None:
        invoice = Invoice(
            invoice_id="inv-stop-2",
            currency="GBP",
            principal_amount=Decimal("1800"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 20),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.FORMAL_NOTICE,
                today=date(2026, 2, 1),
                debtor_feedback="PAYMENT_PLAN_REQUEST",
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.CLIENT_HANDOFF)
        self.assertTrue(decision.outreach_frozen)

    def test_country_code_conflict_routes_to_jurisdiction_uncertain(self) -> None:
        from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts

        invoice = Invoice(
            invoice_id="inv-jur-2",
            currency="GBP",
            principal_amount=Decimal("1200"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        decision = self.engine.decide(
            invoice,
            EscalationContext(
                current_state=InvoiceState.ISSUED,
                today=date(2026, 2, 1),
                jurisdiction_facts=JurisdictionFacts(debtor_country_code="GB-SCT"),
            ),
        )
        self.assertEqual(decision.next_state, InvoiceState.JURISDICTION_UNCERTAIN)
        self.assertTrue(decision.outreach_frozen)


if __name__ == "__main__":
    unittest.main()
