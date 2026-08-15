from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import uuid4

from unpaid_invoice_escalator.models import (
    Actor,
    CommunicationDeliveryEvent,
    CommunicationDeliveryState,
    CommunicationRecord,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


@dataclass(frozen=True)
class CommunicationDeliverySnapshot:
    communication: CommunicationRecord
    latest_state: CommunicationDeliveryState
    events: tuple[CommunicationDeliveryEvent, ...]


class CommunicationDeliveryTracker:
    _ALLOWED_TRANSITIONS = {
        CommunicationDeliveryState.CREATED: {CommunicationDeliveryState.QUEUED, CommunicationDeliveryState.CANCELLED},
        CommunicationDeliveryState.QUEUED: {
            CommunicationDeliveryState.SENT,
            CommunicationDeliveryState.BOUNCED,
            CommunicationDeliveryState.REJECTED,
            CommunicationDeliveryState.RETURNED,
            CommunicationDeliveryState.CANCELLED,
        },
        CommunicationDeliveryState.SENT: {
            CommunicationDeliveryState.DELIVERED,
            CommunicationDeliveryState.BOUNCED,
            CommunicationDeliveryState.REJECTED,
            CommunicationDeliveryState.RETURNED,
        },
        CommunicationDeliveryState.DELIVERED: {
            CommunicationDeliveryState.OPENED,
            CommunicationDeliveryState.BOUNCED,
            CommunicationDeliveryState.REJECTED,
            CommunicationDeliveryState.RETURNED,
        },
        CommunicationDeliveryState.OPENED: set(),
        CommunicationDeliveryState.BOUNCED: {CommunicationDeliveryState.QUEUED},
        CommunicationDeliveryState.REJECTED: {CommunicationDeliveryState.QUEUED},
        CommunicationDeliveryState.RETURNED: {CommunicationDeliveryState.QUEUED},
        CommunicationDeliveryState.CANCELLED: set(),
    }

    def __init__(self, *, store: SQLiteStore, event_ledger: InvoiceLedger) -> None:
        self._store = store
        self._event_ledger = event_ledger

    def create_communication(
        self,
        *,
        invoice_id: str,
        channel: str,
        recipient: str,
        subject: str,
        body_summary: str,
        automated: bool = True,
    ) -> CommunicationDeliverySnapshot:
        now = datetime.now(timezone.utc)
        communication = CommunicationRecord(
            communication_id=str(uuid4()),
            invoice_id=invoice_id,
            channel=channel,
            recipient=recipient,
            subject=subject,
            body_summary=body_summary,
            automated=automated,
            created_at=now,
        )
        self._store.append_communication(communication)
        created_event = CommunicationDeliveryEvent(
            event_id=str(uuid4()),
            communication_id=communication.communication_id,
            invoice_id=invoice_id,
            state=CommunicationDeliveryState.CREATED,
            timestamp=now,
            note="Communication record created.",
        )
        self._store.append_communication_delivery_event(created_event)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="COMMUNICATION_CREATED",
            timestamp=now,
            data_payload={
                "communication_id": communication.communication_id,
                "channel": communication.channel,
                "recipient": communication.recipient,
                "state": CommunicationDeliveryState.CREATED.value,
            },
        )
        return CommunicationDeliverySnapshot(
            communication=communication,
            latest_state=CommunicationDeliveryState.CREATED,
            events=(created_event,),
        )

    def record_delivery_event(
        self,
        *,
        invoice_id: str,
        communication_id: str,
        next_state: CommunicationDeliveryState,
        note: str = "",
    ) -> CommunicationDeliverySnapshot:
        communication = self._store.communication_for_id(communication_id)
        if communication is None or communication.invoice_id != invoice_id:
            raise ValueError("Communication not found for invoice.")
        events = self._store.communication_delivery_events_for_communication(communication_id)
        if not events:
            raise ValueError("Communication has no existing delivery baseline event.")
        previous_state = events[-1].state
        allowed = self._ALLOWED_TRANSITIONS.get(previous_state, set())
        if next_state not in allowed:
            raise ValueError(
                f"Invalid delivery transition from {previous_state.value} to {next_state.value}."
            )
        now = datetime.now(timezone.utc)
        event = CommunicationDeliveryEvent(
            event_id=str(uuid4()),
            communication_id=communication_id,
            invoice_id=invoice_id,
            state=next_state,
            timestamp=now,
            note=note,
        )
        self._store.append_communication_delivery_event(event)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="COMMUNICATION_DELIVERY_STATE_UPDATED",
            timestamp=now,
            data_payload={
                "communication_id": communication_id,
                "from_state": previous_state.value,
                "to_state": next_state.value,
                "note": note,
            },
        )
        updated_events = (*events, event)
        return CommunicationDeliverySnapshot(
            communication=communication,
            latest_state=next_state,
            events=updated_events,
        )

    def snapshots_for_invoice(self, invoice_id: str) -> tuple[CommunicationDeliverySnapshot, ...]:
        communications = self._store.communications_for_invoice(invoice_id)
        snapshots: list[CommunicationDeliverySnapshot] = []
        for communication in communications:
            events = self._store.communication_delivery_events_for_communication(communication.communication_id)
            if not events:
                continue
            snapshots.append(
                CommunicationDeliverySnapshot(
                    communication=communication,
                    latest_state=events[-1].state,
                    events=events,
                )
            )
        return tuple(snapshots)
