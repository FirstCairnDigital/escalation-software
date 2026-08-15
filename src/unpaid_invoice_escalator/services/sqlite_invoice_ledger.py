from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from unpaid_invoice_escalator.models import Actor, ArtifactType, EvidenceArtifact, LedgerEvent
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


class SQLiteInvoiceLedger:
    """Append-only SQLite-backed ledger with per-invoice hash chaining."""

    def __init__(self, store: SQLiteStore) -> None:
        self._store = store

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
        previous_events = self._store.events_for_invoice(invoice_id)
        previous_hash = previous_events[-1].hash if previous_events else "GENESIS"
        event_id = str(uuid4())
        hash_value = InvoiceLedger._hash_event(
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
        self._store.append_ledger_event(event)
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
        now = upload_timestamp or datetime.now(timezone.utc)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        artifact = EvidenceArtifact(
            document_id=str(uuid4()),
            invoice_id=invoice_id,
            artifact_type=artifact_type,
            file_hash=digest,
            file_path=str(path),
            upload_timestamp=now,
            user_id=user_id,
        )
        self._store.save_evidence_artifact(artifact)
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
        return self._store.events_for_invoice(invoice_id)

    def verify_chain(self, invoice_id: str) -> bool:
        return self._store.verify_chain(invoice_id)
