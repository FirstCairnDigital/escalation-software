from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from unpaid_invoice_escalator.models import Actor, LedgerEvent
from unpaid_invoice_escalator.persistence.postgresql_connection import postgresql_connection
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


class PostgreSQLInvoiceLedger:
    """Append-only PostgreSQL-backed invoice ledger with per-invoice advisory locking."""

    def __init__(self, database_url: str) -> None:
        self.database_url = database_url

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
        with postgresql_connection(self.database_url) as conn:
            try:
                with conn.transaction():
                    conn.execute(
                        "SELECT pg_advisory_xact_lock(hashtext('invoice:' || %s))",
                        (invoice_id,),
                    )
                    previous_row = conn.execute(
                        "SELECT hash FROM ledger_events WHERE invoice_id = %s ORDER BY event_seq DESC LIMIT 1",
                        (invoice_id,),
                    ).fetchone()
                    previous_hash = previous_row["hash"] if previous_row else "GENESIS"
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
                    conn.execute(
                        """
                        INSERT INTO ledger_events (
                            event_id, invoice_id, timestamp, actor, event_type,
                            data_payload, previous_hash, hash
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                        """,
                        (
                            event.event_id,
                            event.invoice_id,
                            event.timestamp,
                            event.actor.value,
                            event.event_type,
                            json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str),
                            event.previous_hash,
                            event.hash,
                        ),
                    )
                    return event
            except Exception:
                conn.rollback()
                raise

    def verify_chain(self, invoice_id: str) -> bool:
        with postgresql_connection(self.database_url) as conn:
            rows = conn.execute(
                "SELECT event_id, invoice_id, timestamp, actor, event_type, data_payload, previous_hash, hash FROM ledger_events WHERE invoice_id = %s ORDER BY event_seq ASC",
                (invoice_id,),
            ).fetchall()
            if not rows:
                return True
            previous = "GENESIS"
            for row in rows:
                expected_hash = InvoiceLedger._hash_event(
                    event_id=row["event_id"],
                    invoice_id=row["invoice_id"],
                    timestamp=row["timestamp"],
                    actor=Actor(row["actor"]),
                    event_type=row["event_type"],
                    data_payload=row["data_payload"],
                    previous_hash=previous,
                )
                if row["previous_hash"] != previous or row["hash"] != expected_hash:
                    return False
                previous = row["hash"]
            return True


__all__ = ["PostgreSQLInvoiceLedger"]
