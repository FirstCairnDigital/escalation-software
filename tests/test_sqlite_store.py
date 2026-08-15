from datetime import date
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import Actor, DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
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


if __name__ == "__main__":
    unittest.main()
