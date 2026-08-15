from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import CommunicationDeliveryState, DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.communication_delivery_tracker import CommunicationDeliveryTracker
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestCommunicationDeliveryTracker(unittest.TestCase):
    def test_valid_lifecycle_and_failure_requeue(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "tracker.db"))
            ledger = SQLiteInvoiceLedger(store)
            tracker = CommunicationDeliveryTracker(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-comm-1",
                currency="GBP",
                principal_amount=Decimal("200"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            snapshot = tracker.create_communication(
                invoice_id=invoice.invoice_id,
                channel="EMAIL",
                recipient="debtor@example.com",
                subject="Reminder",
                body_summary="Summary",
            )
            self.assertEqual(snapshot.latest_state, CommunicationDeliveryState.CREATED)
            snapshot = tracker.record_delivery_event(
                invoice_id=invoice.invoice_id,
                communication_id=snapshot.communication.communication_id,
                next_state=CommunicationDeliveryState.QUEUED,
                note="queued",
            )
            snapshot = tracker.record_delivery_event(
                invoice_id=invoice.invoice_id,
                communication_id=snapshot.communication.communication_id,
                next_state=CommunicationDeliveryState.SENT,
                note="sent",
            )
            snapshot = tracker.record_delivery_event(
                invoice_id=invoice.invoice_id,
                communication_id=snapshot.communication.communication_id,
                next_state=CommunicationDeliveryState.BOUNCED,
                note="bounced",
            )
            self.assertEqual(snapshot.latest_state, CommunicationDeliveryState.BOUNCED)
            snapshot = tracker.record_delivery_event(
                invoice_id=invoice.invoice_id,
                communication_id=snapshot.communication.communication_id,
                next_state=CommunicationDeliveryState.QUEUED,
                note="requeued",
            )
            self.assertEqual(snapshot.latest_state, CommunicationDeliveryState.QUEUED)

    def test_invalid_transition_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            store = SQLiteStore(str(Path(tmp_dir) / "tracker-invalid.db"))
            ledger = SQLiteInvoiceLedger(store)
            tracker = CommunicationDeliveryTracker(store=store, event_ledger=ledger)
            invoice = Invoice(
                invoice_id="inv-comm-2",
                currency="GBP",
                principal_amount=Decimal("200"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            snapshot = tracker.create_communication(
                invoice_id=invoice.invoice_id,
                channel="EMAIL",
                recipient="debtor@example.com",
                subject="Reminder",
                body_summary="Summary",
            )
            with self.assertRaises(ValueError):
                tracker.record_delivery_event(
                    invoice_id=invoice.invoice_id,
                    communication_id=snapshot.communication.communication_id,
                    next_state=CommunicationDeliveryState.SENT,
                    note="invalid",
                )


if __name__ == "__main__":
    unittest.main()
