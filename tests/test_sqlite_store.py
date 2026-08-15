from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import (
    Actor,
    ClientFeeAction,
    ComplianceLedgerEntry,
    DebtorVerificationCase,
    DebtorType,
    Invoice,
    Jurisdiction,
    PreOverdueHygieneRecord,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.dual_ledger_engine import DualLedgerEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestSQLiteStore(unittest.TestCase):
    def test_persists_invoice_and_ledger_chain(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            invoice = Invoice(
                invoice_id="inv-db-1",
                currency="GBP",
                principal_amount=Decimal("999.99"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            ledger.append_event(
                invoice_id=invoice.invoice_id,
                actor=Actor.SYSTEM,
                event_type="INVOICE_CREATED",
                data_payload={"hello": "world"},
            )

            loaded = store.get_invoice(invoice.invoice_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.invoice_id, invoice.invoice_id)
            self.assertTrue(store.verify_chain(invoice.invoice_id))

    def test_append_only_triggers_block_update_and_delete(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            invoice = Invoice(
                invoice_id="inv-db-2",
                currency="GBP",
                principal_amount=Decimal("1200"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            ledger.append_event(
                invoice_id=invoice.invoice_id,
                actor=Actor.SYSTEM,
                event_type="INVOICE_CREATED",
                data_payload={"step": 1},
            )

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(
                        "UPDATE ledger_events SET event_type = ? WHERE invoice_id = ?",
                        ("ALTERED", invoice.invoice_id),
                    )
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(
                        "DELETE FROM ledger_events WHERE invoice_id = ?",
                        (invoice.invoice_id,),
                    )
                conn.rollback()
            finally:
                conn.close()

    def test_debtor_verification_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-6",
                currency="GBP",
                principal_amount=Decimal("650"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_debtor_verification_case(
                DebtorVerificationCase(
                    case_id="FCD-R-2026-000001",
                    invoice_id=invoice.invoice_id,
                    creditor_name="Creditor Ltd",
                    invoice_reference="INV-6",
                    verification_code_hash="abc123",
                    created_at=datetime.now(timezone.utc),
                )
            )
            self.assertIsNotNone(store.debtor_verification_case_for_invoice(invoice.invoice_id))
            self.assertIsNotNone(store.debtor_verification_case_by_case_id("FCD-R-2026-000001"))

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE debtor_verification_cases SET creditor_name = 'X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM debtor_verification_cases")
                conn.rollback()
            finally:
                conn.close()

    def test_dual_ledger_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            event_ledger = SQLiteInvoiceLedger(store)
            dual = DualLedgerEngine(store=store, event_ledger=event_ledger)
            invoice = Invoice(
                invoice_id="inv-db-3",
                currency="GBP",
                principal_amount=Decimal("2000"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            dual.add_client_action_fee(
                case_id="CASE-3",
                client_id="CLI-3",
                invoice_id=invoice.invoice_id,
                action_selected=ClientFeeAction.FORMAL_ESCALATION,
                accepted_by_user="Tester",
            )

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE client_fee_entries SET fee_amount_gbp = '99.99'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM client_fee_entries")
                conn.rollback()
            finally:
                conn.close()

    def test_pre_overdue_hygiene_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-4",
                currency="GBP",
                principal_amount=Decimal("1500"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_pre_overdue_hygiene_record(
                PreOverdueHygieneRecord(
                    record_id="hyg-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    creditor_legal_entity_name="First Cairn Digital Ltd",
                    creditor_companies_house_number="SC123456",
                    creditor_vat_number="GB123456789",
                    creditor_trading_address="1 Example Street",
                    debtor_legal_entity_name="Buyer Ltd",
                    debtor_companies_house_number="NI654321",
                    debtor_vat_number="GB987654321",
                    debtor_trading_address="2 Example Road",
                    po_required=True,
                    po_reference="PO-1",
                    payment_terms_days=30,
                    contractual_interest_clause_present=True,
                    contractual_recovery_clause_present=True,
                    proof_of_delivery_required=True,
                    suggested_clause_text="Clause",
                    suggested_clause_requires_legal_review=True,
                    checklist_complete=True,
                    missing_items=(),
                    warning_tier="MEDIUM",
                    format_warnings=("Creditor VAT number format is non-standard.",),
                    notes="ok",
                )
            )
            records = store.pre_overdue_hygiene_records_for_invoice(invoice.invoice_id)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].warning_tier, "MEDIUM")
            self.assertEqual(records[0].format_warnings, ("Creditor VAT number format is non-standard.",))

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE pre_overdue_hygiene_records SET notes = 'changed'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM pre_overdue_hygiene_records")
                conn.rollback()
            finally:
                conn.close()

    def test_compliance_ledger_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-5",
                currency="GBP",
                principal_amount=Decimal("900"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_compliance_entry(
                ComplianceLedgerEntry(
                    entry_id="cmp-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    event_type="LEGAL_SAFETY_GATE_ACCEPTED",
                    details={"user_id": "USER-1"},
                )
            )
            entries = store.compliance_entries_for_invoice(invoice.invoice_id)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].event_type, "LEGAL_SAFETY_GATE_ACCEPTED")

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE compliance_ledger_entries SET event_type = 'X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM compliance_ledger_entries")
                conn.rollback()
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
