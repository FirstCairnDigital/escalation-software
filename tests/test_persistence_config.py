from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.persistence.database_config import resolve_database_config
from unpaid_invoice_escalator.persistence.factory import PostgreSQLPersistenceNotImplementedError, build_store_and_ledger
from unpaid_invoice_escalator.production_config import validate_production_config


class PersistenceConfigurationTests(unittest.TestCase):
    def test_development_db_path_stays_sqlite(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "dev.db")
            app = create_app(db_path=db_path)
            client = TestClient(app)
            resp = client.get("/health")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "ok")

    def test_sqlite_url_resolves_to_sqlite(self) -> None:
        cfg = resolve_database_config({}, db_path="data/escalator.db", database_url="sqlite:///tmp/test.db")
        self.assertEqual(cfg.backend, "sqlite")
        self.assertEqual(cfg.sqlite_path, "/tmp/test.db")

    def test_postgresql_url_resolves_to_postgresql(self) -> None:
        cfg = resolve_database_config(
            {},
            database_url="postgresql://app:super-secret-database-password@db.example.com:5432/fcd?sslmode=require",
        )
        self.assertEqual(cfg.backend, "postgresql")
        self.assertTrue(cfg.tls_required)
        self.assertTrue(cfg.tls_enabled)

    def test_explicit_database_url_precedence_over_db_path(self) -> None:
        with self.assertRaises(PostgreSQLPersistenceNotImplementedError):
            create_app(
                db_path="data/fallback.db",
                database_url="postgresql://app:super-secret-database-password@db.example.com:5432/fcd?sslmode=require",
            )

    def test_unsupported_database_scheme_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_database_config({}, database_url="ftp://example.com/data.db")

    def test_postgresql_configuration_never_silently_creates_sqlite(self) -> None:
        with self.assertRaises(PostgreSQLPersistenceNotImplementedError):
            build_store_and_ledger(
                env={"DATABASE_URL": "postgresql://app:secret@db.example.com:5432/fcd?sslmode=require"},
                db_path="data/fallback.db",
            )

    def test_database_url_is_redacted_from_validation_output(self) -> None:
        report = validate_production_config(
            {
                "FCD_APP_ENV": "production",
                "FCD_MANIFEST_SIGNING_KEY": "prod-signing-key",
                "FCD_MANIFEST_KEY_ID": "prod-key-id",
                "FCD_API_KEYS": "admin-key:admin",
                "FCD_API_CLIENTS": "admin-key:FCD-ADMIN",
                "FCD_API_IDENTITIES": "admin-key:ADMIN-ACTOR",
                "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 0 * * *",
                "DATABASE_URL": "postgresql://app:super-secret-database-password@db.example.com:5432/fcd?sslmode=require",
            }
        )
        payload = str(report)
        self.assertNotIn("super-secret-database-password", payload)
        self.assertNotIn("postgresql://app:super-secret-database-password", payload)
        self.assertNotIn("database_url", payload)
        self.assertEqual(report["database_backend"], "postgresql")
        self.assertTrue(report["database_configured"])
        self.assertTrue(report["database_tls_required"])
        self.assertTrue(report["database_tls_enabled"])

    def test_postgresql_tls_modes_are_classified(self) -> None:
        require_cfg = resolve_database_config({}, database_url="postgresql://app:secret@db.example.com:5432/fcd?sslmode=require")
        verify_ca_cfg = resolve_database_config({}, database_url="postgresql://app:secret@db.example.com:5432/fcd?sslmode=verify-ca")
        verify_full_cfg = resolve_database_config({}, database_url="postgresql://app:secret@db.example.com:5432/fcd?sslmode=verify-full")
        plain_cfg = resolve_database_config({}, database_url="postgresql://app:secret@db.example.com:5432/fcd?sslmode=disable")

        self.assertTrue(require_cfg.tls_required)
        self.assertTrue(verify_ca_cfg.tls_required)
        self.assertTrue(verify_full_cfg.tls_required)
        self.assertFalse(plain_cfg.tls_required)
        self.assertFalse(plain_cfg.tls_enabled)


if __name__ == "__main__":
    unittest.main()
