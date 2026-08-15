from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from unpaid_invoice_escalator.models import Actor, ArtifactType, DebtorType, EvidenceArtifact, Invoice, InvoiceState, Jurisdiction, LedgerEvent


class SQLiteStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

    @contextmanager
    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    currency TEXT NOT NULL,
                    principal_amount TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    debtor_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_artifacts (
                    document_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL DEFAULT 'OTHER',
                    file_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(evidence_artifacts)").fetchall()
            }
            if "artifact_type" not in columns:
                conn.execute(
                    "ALTER TABLE evidence_artifacts ADD COLUMN artifact_type TEXT NOT NULL DEFAULT 'OTHER'"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_events (
                    event_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data_payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ledger_events_invoice_time
                ON ledger_events(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_invoice
                ON evidence_artifacts(invoice_id)
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoices_no_update
                BEFORE UPDATE ON invoices
                BEGIN
                    SELECT RAISE(ABORT, 'invoices is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoices_no_delete
                BEFORE DELETE ON invoices
                BEGIN
                    SELECT RAISE(ABORT, 'invoices is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_update
                BEFORE UPDATE ON ledger_events
                BEGIN
                    SELECT RAISE(ABORT, 'ledger_events is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_delete
                BEFORE DELETE ON ledger_events
                BEGIN
                    SELECT RAISE(ABORT, 'ledger_events is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_evidence_artifacts_no_update
                BEFORE UPDATE ON evidence_artifacts
                BEGIN
                    SELECT RAISE(ABORT, 'evidence_artifacts is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_evidence_artifacts_no_delete
                BEFORE DELETE ON evidence_artifacts
                BEGIN
                    SELECT RAISE(ABORT, 'evidence_artifacts is append-only');
                END;
                """
            )
            conn.commit()

    def create_invoice(self, invoice: Invoice) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, currency, principal_amount, issue_date, due_date,
                    jurisdiction, debtor_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.invoice_id,
                    invoice.currency,
                    str(invoice.principal_amount),
                    invoice.issue_date.isoformat(),
                    invoice.due_date.isoformat(),
                    invoice.jurisdiction.value,
                    invoice.debtor_type.value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type
                FROM invoices
                WHERE invoice_id = ?
                """,
                (invoice_id,),
            ).fetchone()
        if row is None:
            return None
        return Invoice(
            invoice_id=row["invoice_id"],
            currency=row["currency"],
            principal_amount=Decimal(row["principal_amount"]),
            issue_date=date.fromisoformat(row["issue_date"]),
            due_date=date.fromisoformat(row["due_date"]),
            jurisdiction=Jurisdiction(row["jurisdiction"]),
            debtor_type=DebtorType(row["debtor_type"]),
        )

    def append_ledger_event(self, event: LedgerEvent) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO ledger_events (
                    event_id, invoice_id, timestamp, actor, event_type,
                    data_payload, previous_hash, hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.invoice_id,
                    event.timestamp.isoformat(),
                    event.actor.value,
                    event.event_type,
                    json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str),
                    event.previous_hash,
                    event.hash,
                ),
            )
            conn.commit()

    def events_for_invoice(self, invoice_id: str) -> tuple[LedgerEvent, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, invoice_id, timestamp, actor, event_type, data_payload, previous_hash, hash
                FROM ledger_events
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            LedgerEvent(
                event_id=row["event_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                actor=Actor(row["actor"]),
                event_type=row["event_type"],
                data_payload=json.loads(row["data_payload"]),
                previous_hash=row["previous_hash"],
                hash=row["hash"],
            )
            for row in rows
        )

    def save_evidence_artifact(self, artifact: EvidenceArtifact) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO evidence_artifacts (
                    document_id, invoice_id, artifact_type, file_hash, file_path, upload_timestamp, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.document_id,
                    artifact.invoice_id,
                    artifact.artifact_type.value,
                    artifact.file_hash,
                    artifact.file_path,
                    artifact.upload_timestamp.isoformat(),
                    artifact.user_id,
                ),
            )
            conn.commit()

    def artifacts_for_invoice(self, invoice_id: str) -> tuple[EvidenceArtifact, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT document_id, invoice_id, file_hash, file_path, upload_timestamp, user_id
                     , artifact_type
                FROM evidence_artifacts
                WHERE invoice_id = ?
                ORDER BY upload_timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            EvidenceArtifact(
                document_id=row["document_id"],
                invoice_id=row["invoice_id"],
                artifact_type=ArtifactType(row["artifact_type"]),
                file_hash=row["file_hash"],
                file_path=row["file_path"],
                upload_timestamp=datetime.fromisoformat(row["upload_timestamp"]),
                user_id=row["user_id"],
            )
            for row in rows
        )

    def infer_state(self, invoice_id: str) -> InvoiceState:
        events = self.events_for_invoice(invoice_id)
        for event in reversed(events):
            if event.event_type == "STATE_TRANSITION":
                to_state = event.data_payload.get("to_state")
                if isinstance(to_state, str):
                    return InvoiceState(to_state)
        return InvoiceState.ISSUED

    def infer_state_entered_on(self, invoice_id: str, current_state: InvoiceState) -> date | None:
        events = self.events_for_invoice(invoice_id)
        for event in reversed(events):
            if event.event_type != "STATE_TRANSITION":
                continue
            to_state = event.data_payload.get("to_state")
            if to_state == current_state.value:
                return event.timestamp.date()
        return None

    def verify_chain(self, invoice_id: str) -> bool:
        events = self.events_for_invoice(invoice_id)
        previous = "GENESIS"
        for event in events:
            stable_payload = json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str)
            payload = "|".join(
                [
                    event.event_id,
                    event.invoice_id,
                    event.timestamp.isoformat(),
                    event.actor.value,
                    event.event_type,
                    stable_payload,
                    previous,
                ]
            )
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if event.previous_hash != previous or event.hash != expected_hash:
                return False
            previous = event.hash
        return True
