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
    CommunicationDeliveryEvent,
    CommunicationDeliveryState,
    CommunicationRecord,
    ComplianceLedgerEntry,
    DebtorVerificationCase,
    DebtorType,
    Invoice,
    Jurisdiction,
    PaymentPlanAgreement,
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

    def test_payment_plan_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-7",
                currency="GBP",
                principal_amount=Decimal("900"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_payment_plan_agreement(
                PaymentPlanAgreement(
                    plan_id="plan-1",
                    invoice_id=invoice.invoice_id,
                    created_at=datetime.now(timezone.utc),
                    proposed_by="USER-1",
                    installment_amount_gbp=Decimal("100"),
                    installment_count=3,
                    first_due_date=date(2026, 2, 10),
                    frequency_days=30,
                )
            )
            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE payment_plan_agreements SET proposed_by = 'USER-X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM payment_plan_agreements")
                conn.rollback()
            finally:
                conn.close()

    def test_communication_delivery_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-8",
                currency="GBP",
                principal_amount=Decimal("300"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            record = CommunicationRecord(
                communication_id="comm-1",
                invoice_id=invoice.invoice_id,
                channel="EMAIL",
                recipient="debtor@example.com",
                subject="Reminder",
                body_summary="Summary",
                created_at=datetime.now(timezone.utc),
            )
            store.append_communication(record)
            store.append_communication_delivery_event(
                CommunicationDeliveryEvent(
                    event_id="comm-evt-1",
                    communication_id=record.communication_id,
                    invoice_id=invoice.invoice_id,
                    state=CommunicationDeliveryState.CREATED,
                    timestamp=datetime.now(timezone.utc),
                    note="created",
                )
            )
            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE communications SET recipient = 'new@example.com'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM communications")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE communication_delivery_events SET state = 'SENT'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM communication_delivery_events")
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
