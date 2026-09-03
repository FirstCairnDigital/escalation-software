from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from uuid import uuid4

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.persistence.factory import build_store_and_ledger
from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.services.postgresql_invoice_ledger import PostgreSQLInvoiceLedger


class PostgreSQLAppIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.getenv("POSTGRES_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not cls.database_url:
            raise unittest.SkipTest("PostgreSQL integration tests require a test DATABASE_URL.")

    def test_factory_and_app_use_postgresql_without_creating_sqlite_fallback(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            sqlite_fallback = Path(tmp_dir) / "fallback.db"
            store, ledger = build_store_and_ledger(
                db_path=str(sqlite_fallback),
                database_url=self.database_url,
            )
            self.assertIsInstance(store, PostgreSQLStore)
            self.assertIsInstance(ledger, PostgreSQLInvoiceLedger)
            self.assertFalse(sqlite_fallback.exists())

            app = create_app(
                db_path=str(sqlite_fallback),
                database_url=self.database_url,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)
            self.assertEqual(client.get("/health").status_code, 200)

            ready = client.get("/ready")
            self.assertEqual(ready.status_code, 200)
            ready_body = ready.json()
            self.assertEqual(ready_body["status"], "ready")
            self.assertEqual(ready_body["database_backend"], "postgresql")
            checks = {item["check"]: item for item in ready_body["checks"]}
            self.assertTrue(checks["database-connectivity"]["passed"])
            self.assertTrue(checks["schema-migrations"]["passed"])
            self.assertTrue(checks["append-only-triggers"]["passed"])
            self.assertNotIn("postgresql://", str(ready_body))
            self.assertNotIn("super-secret-postgres-test-password", str(ready_body))
            self.assertFalse(sqlite_fallback.exists())

            invoice_id = f"inv-postgres-app-{uuid4().hex[:8]}"
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": invoice_id,
                    "currency": "GBP",
                    "principal_amount": "100.00",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            get_resp = client.get(f"/invoices/{invoice_id}")
            self.assertEqual(get_resp.status_code, 200)
            self.assertEqual(get_resp.json()["invoice_id"], invoice_id)

    def test_repeated_startup_keeps_postgresql_ready(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            kwargs = {
                "db_path": str(Path(tmp_dir) / "unused.db"),
                "database_url": self.database_url,
                "artifacts_dir": str(Path(tmp_dir) / "artifacts"),
                "bundles_dir": str(Path(tmp_dir) / "bundles"),
            }
            first = TestClient(create_app(**kwargs)).get("/ready")
            second = TestClient(create_app(**kwargs)).get("/ready")
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)

    def test_postgresql_ready_fails_closed_without_exposing_credentials(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_app(
                db_path=str(Path(tmp_dir) / "unused.db"),
                database_url=self.database_url,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)
            with patch(
                "unpaid_invoice_escalator.api.postgresql_connection",
                side_effect=RuntimeError(
                    "postgresql://app:fake-password@db.example.com:5432/app?sslmode=require"
                ),
            ):
                ready = client.get("/ready")
            self.assertEqual(ready.status_code, 503)
            payload = ready.json()
            self.assertEqual(payload["status"], "not_ready")
            self.assertEqual(payload["database_backend"], "postgresql")
            checks = {item["check"]: item for item in payload["checks"]}
            self.assertFalse(checks["database-connectivity"]["passed"])
            self.assertEqual(checks["database-connectivity"]["detail"], "PostgreSQL connectivity failed.")
            self.assertNotIn("fake-password", str(payload))
            self.assertNotIn("postgresql://", str(payload))


if __name__ == "__main__":
    unittest.main()
