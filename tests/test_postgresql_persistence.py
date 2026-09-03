from __future__ import annotations

import os
import threading
import unittest
from datetime import datetime, timezone
from decimal import Decimal
from importlib.resources import files
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from unpaid_invoice_escalator.models import Actor, Jurisdiction, DebtorType
from unpaid_invoice_escalator.persistence.migrations.postgresql.postgresql_migrations import (
    MigrationChecksumMismatchError,
    PostgreSQLMigrationRunner,
)
from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.services.postgresql_invoice_ledger import PostgreSQLInvoiceLedger


def test_postgresql_migration_sql_is_packaged() -> None:
    migration_file = files("unpaid_invoice_escalator.persistence.migrations.postgresql").joinpath("0001_initial.sql")
    assert migration_file.is_file()
    assert migration_file.read_text(encoding="utf-8")


class PostgreSQLPersistenceIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.getenv("POSTGRES_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not cls.database_url:
            raise unittest.SkipTest("PostgreSQL integration tests require a test DATABASE_URL.")

    def setUp(self) -> None:
        self.store = PostgreSQLStore(self.database_url)
        self.store.run_migrations()
        self.ledger = PostgreSQLInvoiceLedger(self.database_url)

    def _create_invoice_row(self, invoice_id: str) -> None:
        with self.store.connection() as conn:
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, currency, principal_amount, issue_date, due_date,
                    jurisdiction, debtor_type, client_id, created_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    invoice_id,
                    "GBP",
                    Decimal("1250.00"),
                    datetime.now(timezone.utc).date(),
                    datetime.now(timezone.utc).date(),
                    Jurisdiction.ENGLAND_WALES.value,
                    DebtorType.LIMITED.value,
                    "CLIENT-01",
                    datetime.now(timezone.utc),
                ),
            )

    def test_connection_and_migrations_apply(self) -> None:
        with self.store.connection() as conn:
            self.assertIsNotNone(conn)
            tables = conn.execute(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' ORDER BY table_name"
            ).fetchall()
            self.assertIn("invoices", {row["table_name"] for row in tables})
            self.assertIn("ledger_events", {row["table_name"] for row in tables})
            self.assertIn("schema_migrations", {row["table_name"] for row in tables})

    def test_running_migrations_twice_is_safe(self) -> None:
        applied_again = self.store.run_migrations()
        self.assertEqual(applied_again, [])

    def test_migration_checksum_mismatch_is_detected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            migration_file = Path(tmp_dir) / "0001_test.sql"
            migration_file.write_text("CREATE TABLE IF NOT EXISTS temp_mutation (id TEXT PRIMARY KEY);", encoding="utf-8")
            runner = PostgreSQLMigrationRunner(self.database_url, migration_dir=tmp_dir)
            runner.apply()
            migration_file.write_text(
                "CREATE TABLE IF NOT EXISTS temp_mutation (id TEXT PRIMARY KEY, extra TEXT);",
                encoding="utf-8",
            )
            with self.assertRaises(MigrationChecksumMismatchError):
                runner.apply()

    def test_append_only_protection_rejects_update_and_delete(self) -> None:
        invoice_id = f"INV-{uuid4().hex[:12]}"
        self._create_invoice_row(invoice_id)
        with self.store.connection() as conn:
            conn.execute(
                "INSERT INTO ledger_events (event_id, invoice_id, timestamp, actor, event_type, data_payload, previous_hash, hash) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    f"evt-protect-{uuid4().hex}",
                    invoice_id,
                    datetime.now(timezone.utc),
                    Actor.SYSTEM.value,
                    "TEST_EVENT",
                    "{}",
                    "GENESIS",
                    "abc123",
                ),
            )
        with self.store.connection() as conn:
            with self.assertRaises(Exception):
                conn.execute("UPDATE ledger_events SET event_type = 'UPDATED' WHERE invoice_id = %s", (invoice_id,))
        with self.store.connection() as conn:
            with self.assertRaises(Exception):
                conn.execute("DELETE FROM ledger_events WHERE invoice_id = %s", (invoice_id,))

    def test_ledger_chain_and_verification(self) -> None:
        invoice_id = f"INV-{uuid4().hex[:12]}"
        self._create_invoice_row(invoice_id)
        first = self.ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="INITIAL_EVENT",
            data_payload={"step": 1},
        )
        second = self.ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="SECOND_EVENT",
            data_payload={"step": 2},
        )
        self.assertEqual(first.previous_hash, "GENESIS")
        self.assertEqual(second.previous_hash, first.hash)
        self.assertTrue(self.ledger.verify_chain(invoice_id))

    def test_concurrent_appends_to_same_invoice_remain_one_chain(self) -> None:
        invoice_id = f"INV-{uuid4().hex[:12]}"
        self._create_invoice_row(invoice_id)
        barrier = threading.Barrier(8)
        results: list[str] = []
        lock = threading.Lock()

        def append_worker() -> None:
            barrier.wait()
            ledger = PostgreSQLInvoiceLedger(self.database_url)
            event = ledger.append_event(
                invoice_id=invoice_id,
                actor=Actor.SYSTEM,
                event_type="THREAD_EVENT",
                data_payload={"worker": uuid4().hex},
            )
            with lock:
                results.append(event.hash)

        threads = [threading.Thread(target=append_worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(results), 8)
        with self.store.connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM ledger_events WHERE invoice_id = %s", (invoice_id,)).fetchone()["count"]
        self.assertEqual(count, 8)
        self.assertTrue(self.ledger.verify_chain(invoice_id))

    def test_concurrent_first_append_to_empty_invoice_stays_one_chain(self) -> None:
        invoice_id = f"INV-{uuid4().hex[:12]}"
        self._create_invoice_row(invoice_id)
        barrier = threading.Barrier(6)
        hashes: list[str] = []
        lock = threading.Lock()

        def append_worker() -> None:
            barrier.wait()
            ledger = PostgreSQLInvoiceLedger(self.database_url)
            event = ledger.append_event(
                invoice_id=invoice_id,
                actor=Actor.CLIENT,
                event_type="EMPTY_CHAIN_EVENT",
                data_payload={"worker": uuid4().hex},
            )
            with lock:
                hashes.append(event.hash)

        threads = [threading.Thread(target=append_worker) for _ in range(6)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(len(hashes), 6)
        self.assertTrue(self.ledger.verify_chain(invoice_id))

    def test_rollback_leaves_no_half_written_event(self) -> None:
        invoice_id = f"INV-{uuid4().hex[:12]}"
        self._create_invoice_row(invoice_id)
        from unittest import mock

        with mock.patch("unpaid_invoice_escalator.services.postgresql_invoice_ledger.InvoiceLedger._hash_event", side_effect=RuntimeError("simulated failure")):
            with self.assertRaises(RuntimeError):
                self.ledger.append_event(
                    invoice_id=invoice_id,
                    actor=Actor.SYSTEM,
                    event_type="ROLLBACK_EVENT",
                    data_payload={"should_fail": True},
                )
        with self.store.connection() as conn:
            count = conn.execute("SELECT COUNT(*) AS count FROM ledger_events WHERE invoice_id = %s", (invoice_id,)).fetchone()["count"]
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
