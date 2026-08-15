from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from unpaid_invoice_escalator.models import Actor, ArtifactType, EvidenceArtifact, LedgerEvent


class InvoiceLedger:
    """Append-only in-memory ledger with hash chaining per invoice."""

    def __init__(self) -> None:
        self._events_by_invoice: dict[str, list[LedgerEvent]] = {}

    @staticmethod
    def _stable_payload(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)

    @classmethod
    def _hash_event(
        cls,
        *,
        event_id: str,
        invoice_id: str,
        timestamp: datetime,
        actor: Actor,
        event_type: str,
        data_payload: dict[str, Any],
        previous_hash: str,
    ) -> str:
        payload = "|".join(
            [
                event_id,
                invoice_id,
                timestamp.isoformat(),
                actor.value,
                event_type,
                cls._stable_payload(data_payload),
                previous_hash,
            ]
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def append_event(
        self,
        *,
        invoice_id: str,
        actor: Actor,
        event_type: str,
        data_payload: dict[str, Any] | None = None,
        timestamp: datetime | None = None,
    ) -> LedgerEvent:
        now = timestamp or datetime.now(timezone.utc)
        payload = data_payload or {}
        event_id = str(uuid4())

        entries = self._events_by_invoice.setdefault(invoice_id, [])
        previous_hash = entries[-1].hash if entries else "GENESIS"
        hash_value = self._hash_event(
            event_id=event_id,
            invoice_id=invoice_id,
            timestamp=now,
            actor=actor,
            event_type=event_type,
            data_payload=payload,
            previous_hash=previous_hash,
        )

        event = LedgerEvent(
            event_id=event_id,
            invoice_id=invoice_id,
            timestamp=now,
            actor=actor,
            event_type=event_type,
            data_payload=payload,
            previous_hash=previous_hash,
            hash=hash_value,
        )
        entries.append(event)
        return event

    def record_evidence_artifact(
        self,
        *,
        invoice_id: str,
        file_path: str,
        user_id: str,
        artifact_type: ArtifactType = ArtifactType.OTHER,
        upload_timestamp: datetime | None = None,
    ) -> EvidenceArtifact:
        path = Path(file_path)
        file_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        now = upload_timestamp or datetime.now(timezone.utc)
        artifact = EvidenceArtifact(
            document_id=str(uuid4()),
            invoice_id=invoice_id,
            artifact_type=artifact_type,
            file_hash=file_hash,
            file_path=str(path),
            upload_timestamp=now,
            user_id=user_id,
        )
        self.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="EVIDENCE_ARTIFACT_UPLOADED",
            data_payload={
                "document_id": artifact.document_id,
                "artifact_type": artifact.artifact_type.value,
                "file_hash": artifact.file_hash,
                "file_path": artifact.file_path,
                "user_id": artifact.user_id,
            },
            timestamp=now,
        )
        return artifact

    def events_for_invoice(self, invoice_id: str) -> tuple[LedgerEvent, ...]:
        return tuple(self._events_by_invoice.get(invoice_id, []))

    def verify_chain(self, invoice_id: str) -> bool:
        events = self._events_by_invoice.get(invoice_id, [])
        if not events:
            return True

        previous = "GENESIS"
        for event in events:
            expected_hash = self._hash_event(
                event_id=event.event_id,
                invoice_id=event.invoice_id,
                timestamp=event.timestamp,
                actor=event.actor,
                event_type=event.event_type,
                data_payload=event.data_payload,
                previous_hash=previous,
            )
            if event.previous_hash != previous or event.hash != expected_hash:
                return False
            previous = event.hash
        return True
