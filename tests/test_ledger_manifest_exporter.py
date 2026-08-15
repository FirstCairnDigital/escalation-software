from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import Actor, DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.ledger_manifest_exporter import LedgerManifestExporter
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestLedgerManifestExporter(unittest.TestCase):
    def test_verify_detects_tampering(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "manifest.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            exporter = LedgerManifestExporter(store=store, signing_key="unit-test-key", key_id="unit-test")
            invoice = Invoice(
                invoice_id="inv-man-1",
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
                data_payload={"foo": "bar"},
            )

            manifest_path = Path(tmp_dir) / "manifest.json"
            exporter.export_invoice_manifest(invoice_id=invoice.invoice_id, output_path=str(manifest_path))
            valid = exporter.verify_invoice_manifest(invoice_id=invoice.invoice_id, manifest_path=str(manifest_path))
            self.assertTrue(valid["overall_valid"])

            tampered = json.loads(manifest_path.read_text(encoding="utf-8"))
            tampered["events_count"] = 99
            manifest_path.write_text(json.dumps(tampered), encoding="utf-8")
            invalid = exporter.verify_invoice_manifest(invoice_id=invoice.invoice_id, manifest_path=str(manifest_path))
            self.assertFalse(invalid["overall_valid"])


if __name__ == "__main__":
    unittest.main()

