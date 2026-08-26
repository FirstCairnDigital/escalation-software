from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import ClientFeeAction, DebtorLedgerEntryType, DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.dual_ledger_engine import DualLedgerEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestDualLedgerEngine(unittest.TestCase):
    def test_client_and_debtor_ledgers_are_independent(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "dual.db"))
            event_ledger = SQLiteInvoiceLedger(store)
            engine = DualLedgerEngine(store=store, event_ledger=event_ledger)
            invoice = Invoice(
                invoice_id="inv-dual-1",
                currency="GBP",
                principal_amount=Decimal("3850"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)

            fee_entry = engine.add_client_action_fee(
                case_id="FCD-R-2026-000184",
                client_id="CLI-8841",
                invoice_id=invoice.invoice_id,
                action_selected=ClientFeeAction.FORMAL_ESCALATION,
                accepted_by_user="John Smith (USER-102)",
            )
            self.assertEqual(fee_entry.fee_amount_gbp, Decimal("9.95"))
            self.assertEqual(store.client_fee_balance_for_invoice(invoice.invoice_id), Decimal("11.94"))
            self.assertEqual(store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("3850.00"))
            self.assertEqual(store.debtor_ledger_entries_for_invoice(invoice.invoice_id)[0].entry_type, DebtorLedgerEntryType.ORIGINAL_PRINCIPAL)

            debtor_entry = engine.add_debtor_entry(
                invoice_id=invoice.invoice_id,
                entry_type=DebtorLedgerEntryType.STATUTORY_INTEREST,
                amount_gbp=Decimal("12.45"),
                description="Accrued statutory late-payment interest",
            )
            self.assertEqual(debtor_entry.amount_gbp, Decimal("12.45"))
            self.assertEqual(store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("3862.45"))
            self.assertEqual(store.client_fee_balance_for_invoice(invoice.invoice_id), Decimal("11.94"))


if __name__ == "__main__":
    unittest.main()
