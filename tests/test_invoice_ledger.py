from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import Actor
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


class TestInvoiceLedger(unittest.TestCase):
    def test_hash_chain_verification(self) -> None:
        ledger = InvoiceLedger()
        invoice_id = "inv-001"
        now = datetime(2026, 1, 1, tzinfo=timezone.utc)

        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="ISSUED",
            data_payload={"step": 1},
            timestamp=now,
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="FRIENDLY_REMINDER",
            data_payload={"step": 2},
            timestamp=now,
        )

        self.assertTrue(ledger.verify_chain(invoice_id))
        self.assertEqual(len(ledger.events_for_invoice(invoice_id)), 2)

    def test_record_evidence_artifact(self) -> None:
        ledger = InvoiceLedger()
        with TemporaryDirectory() as tmp_dir:
            file_path = Path(tmp_dir) / "proof.txt"
            file_path.write_text("delivery signed", encoding="utf-8")
            artifact = ledger.record_evidence_artifact(
                invoice_id="inv-002",
                file_path=str(file_path),
                user_id="client-123",
            )
        self.assertEqual(artifact.invoice_id, "inv-002")
        self.assertTrue(ledger.verify_chain("inv-002"))


if __name__ == "__main__":
    unittest.main()

