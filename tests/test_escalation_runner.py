from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.services.escalation_runner import EscalationRunner


class TestEscalationRunner(unittest.TestCase):
    def test_run_step_records_ledger_events(self) -> None:
        runner = EscalationRunner()
        invoice = Invoice(
            invoice_id="inv-runner-1",
            currency="GBP",
            principal_amount=Decimal("1200"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.SOLE_TRADER,
        )
        result = runner.run_step(
            invoice=invoice,
            current_state=InvoiceState.OVERDUE_CHASER,
            today=date(2026, 2, 1),
        )
        self.assertEqual(result.decision.next_state, InvoiceState.PRE_ACTION_PROTOCOL)
        self.assertTrue(runner.ledger.verify_chain(invoice.invoice_id))
        self.assertGreaterEqual(len(runner.ledger.events_for_invoice(invoice.invoice_id)), 2)

    def test_compile_evidence_bundle_records_generation(self) -> None:
        runner = EscalationRunner()
        invoice = Invoice(
            invoice_id="inv-runner-2",
            currency="GBP",
            principal_amount=Decimal("2500"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.NORTHERN_IRELAND,
            debtor_type=DebtorType.LIMITED,
        )
        runner.run_step(
            invoice=invoice,
            current_state=InvoiceState.FORMAL_NOTICE,
            today=date(2026, 2, 20),
            state_entered_on=date(2026, 2, 1),
        )
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "bundle.pdf"
            bundle_path = runner.compile_evidence_bundle(
                invoice=invoice,
                output_path=str(output_path),
                communications=("LBA sent",),
                contract_paths=(),
                proof_of_supply_paths=(),
                formal_notices=("14-day Letter Before Action",),
            )
            self.assertTrue(Path(bundle_path).exists())
        self.assertTrue(runner.ledger.verify_chain(invoice.invoice_id))


if __name__ == "__main__":
    unittest.main()
