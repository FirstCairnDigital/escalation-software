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

    def test_verify_supports_key_rotation_window(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "manifest-rotation.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            signer = LedgerManifestExporter(store=store, signing_key="legacy-key", key_id="legacy-2026q2")
            verifier = LedgerManifestExporter(
                store=store,
                signing_key="current-key",
                key_id="current-2026q3",
                verification_keys={
                    "legacy-2026q2": "legacy-key",
                    "current-2026q3": "current-key",
                },
            )
            invoice = Invoice(
                invoice_id="inv-man-rotation",
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
                data_payload={"rotation": "legacy"},
            )

            manifest_path = Path(tmp_dir) / "manifest-rotation.json"
            signer.export_invoice_manifest(invoice_id=invoice.invoice_id, output_path=str(manifest_path))
            verification = verifier.verify_invoice_manifest(invoice_id=invoice.invoice_id, manifest_path=str(manifest_path))
            self.assertTrue(verification["overall_valid"])
            self.assertEqual(verification["signature_key_id"], "legacy-2026q2")
            self.assertEqual(verification["verified_with_key_id"], "legacy-2026q2")

    def test_manifest_pdf_paginates_for_long_event_chains(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "manifest-pages.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            exporter = LedgerManifestExporter(store=store, signing_key="unit-test-key", key_id="unit-test")
            invoice = Invoice(
                invoice_id="inv-man-pages",
                currency="GBP",
                principal_amount=Decimal("1200"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            for index in range(90):
                ledger.append_event(
                    invoice_id=invoice.invoice_id,
                    actor=Actor.SYSTEM,
                    event_type=f"EVENT_{index}",
                    data_payload={"index": index},
                )

            pdf_path = Path(tmp_dir) / "manifest.pdf"
            exporter.export_invoice_manifest_pdf(invoice_id=invoice.invoice_id, output_path=str(pdf_path))
            self.assertGreaterEqual(pdf_path.read_bytes().count(b"/Type /Page "), 2)


if __name__ == "__main__":
    unittest.main()
