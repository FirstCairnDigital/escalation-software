from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.persistence.database_config import resolve_database_config
from unpaid_invoice_escalator.persistence.factory import build_store_and_ledger
from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.production_config import validate_production_config
from unpaid_invoice_escalator.services.postgresql_invoice_ledger import PostgreSQLInvoiceLedger
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


FAKE_POSTGRES_URL = "postgresql://app:fake-password@db.example.com:5432/fcd?sslmode=require"
FAKE_POSTGRES_URL_DISABLE = "postgresql://app:fake-password@db.example.com:5432/fcd?sslmode=disable"
FAKE_POSTGRES_URL_VERIFY_CA = "postgresql://app:fake-password@db.example.com:5432/fcd?sslmode=verify-ca"
FAKE_POSTGRES_URL_VERIFY_FULL = "postgresql://app:fake-password@db.example.com:5432/fcd?sslmode=verify-full"


def _production_env(database_url: str | None = None) -> dict[str, str]:
    env = {
        "FCD_APP_ENV": "production",
        "FCD_MANIFEST_SIGNING_KEY": "prod-signing-key",
        "FCD_MANIFEST_KEY_ID": "prod-key-id",
        "FCD_API_KEYS": "admin-key:admin",
        "FCD_API_CLIENTS": "admin-key:FCD-ADMIN",
        "FCD_API_IDENTITIES": "admin-key:ADMIN-ACTOR",
        "FCD_RATE_LIMIT_PER_MINUTE": "120",
        "FCD_AUTH_FAILURE_ALERT_THRESHOLD": "10",
        "FCD_RATE_LIMIT_ALERT_THRESHOLD": "10",
        "FCD_SERVER_ERROR_ALERT_THRESHOLD": "5",
        "FCD_MAX_UPLOAD_BYTES": "5242880",
        "FCD_ALLOWED_UPLOAD_CONTENT_TYPES": "application/pdf,text/plain",
        "FCD_ALLOWED_UPLOAD_EXTENSIONS": ".pdf,.txt",
        "FCD_QUARANTINE_DIR": "data/quarantine",
        "FCD_DATA_RETENTION_DAYS": "2190",
        "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 0 * * *",
    }
    if database_url is not None:
        env["DATABASE_URL"] = database_url
    return env


class PersistenceConfigurationTests(unittest.TestCase):
    def test_create_app_sqlite_uses_factory_path_and_starts(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "dev.db")
            app = create_app(db_path=db_path)
            client = TestClient(app)
            resp = client.get("/health")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "ok")

    def test_development_db_path_stays_sqlite(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "dev.db")
            app = create_app(db_path=db_path)
            client = TestClient(app)
            resp = client.get("/health")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["status"], "ok")

    def test_sqlite_factory_returns_sqlite_implementations(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "sqlite.db")
            store, ledger = build_store_and_ledger(db_path=db_path)
            self.assertIsInstance(store, SQLiteStore)
            self.assertIsInstance(ledger, SQLiteInvoiceLedger)

    def test_postgresql_factory_returns_postgresql_implementations_and_runs_migrations(self) -> None:
        with patch.object(PostgreSQLStore, "run_migrations", return_value=["0001_initial"]) as run_migrations:
            store, ledger = build_store_and_ledger(database_url=FAKE_POSTGRES_URL, db_path="data/fallback.db")
        self.assertIsInstance(store, PostgreSQLStore)
        self.assertIsInstance(ledger, PostgreSQLInvoiceLedger)
        run_migrations.assert_called_once_with()

    def test_postgresql_migration_failures_do_not_fall_back_to_sqlite(self) -> None:
        with patch.object(PostgreSQLStore, "run_migrations", side_effect=RuntimeError("migration failed")):
            with self.assertRaisesRegex(RuntimeError, "migration failed"):
                build_store_and_ledger(database_url=FAKE_POSTGRES_URL, db_path="data/fallback.db")

    def test_explicit_postgresql_takes_precedence_over_db_path_without_creating_sqlite_file(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = Path(tmp_dir) / "fallback.db"
            with patch.object(PostgreSQLStore, "run_migrations", return_value=["0001_initial"]):
                store, ledger = build_store_and_ledger(database_url=FAKE_POSTGRES_URL, db_path=str(db_path))
            self.assertIsInstance(store, PostgreSQLStore)
            self.assertIsInstance(ledger, PostgreSQLInvoiceLedger)
            self.assertFalse(db_path.exists())

    def test_sqlite_url_resolves_to_sqlite(self) -> None:
        cfg = resolve_database_config({}, db_path="data/escalator.db", database_url="sqlite:///tmp/test.db")
        self.assertEqual(cfg.backend, "sqlite")
        self.assertEqual(cfg.sqlite_path, "/tmp/test.db")
        self.assertTrue(cfg.configured)

    def test_postgresql_url_resolves_to_postgresql(self) -> None:
        cfg = resolve_database_config({}, database_url=FAKE_POSTGRES_URL)
        self.assertEqual(cfg.backend, "postgresql")
        self.assertTrue(cfg.tls_required)
        self.assertTrue(cfg.tls_enabled)
        self.assertTrue(cfg.configured)

    def test_db_path_fallback_is_not_treated_as_explicit_database_configuration(self) -> None:
        cfg = resolve_database_config({}, db_path="data/escalator.db")
        self.assertEqual(cfg.backend, "sqlite")
        self.assertFalse(cfg.configured)
        self.assertEqual(cfg.source, "db_path")

    def test_unsupported_database_scheme_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            resolve_database_config({}, database_url="ftp://example.com/data.db")

    def test_create_app_rejects_production_sqlite(self) -> None:
        with self.assertRaisesRegex(ValueError, "Production requires an explicit DATABASE_URL|Production requires PostgreSQL"):
            create_app(
                app_env="production",
                auth_enabled=True,
                db_path="data/fallback.db",
                manifest_signing_key="prod-signing-key",
                manifest_key_id="prod-key-id",
                api_keys={"admin-key": "admin"},
                api_clients={"admin-key": "FCD-ADMIN"},
                api_identities={"admin-key": "ADMIN-ACTOR"},
            )

    def test_create_app_rejects_production_postgresql_without_tls(self) -> None:
        with self.assertRaisesRegex(ValueError, "sslmode=require, sslmode=verify-ca, or sslmode=verify-full"):
            create_app(
                app_env="production",
                auth_enabled=True,
                db_path="data/fallback.db",
                database_url=FAKE_POSTGRES_URL_DISABLE,
                manifest_signing_key="prod-signing-key",
                manifest_key_id="prod-key-id",
                api_keys={"admin-key": "admin"},
                api_clients={"admin-key": "FCD-ADMIN"},
                api_identities={"admin-key": "ADMIN-ACTOR"},
            )

    def test_database_url_is_redacted_from_validation_output(self) -> None:
        report = validate_production_config(_production_env(FAKE_POSTGRES_URL))
        payload = str(report)
        self.assertNotIn("fake-password", payload)
        self.assertNotIn("postgresql://app:fake-password", payload)
        self.assertEqual(report["database_backend"], "postgresql")
        self.assertTrue(report["database_configured"])
        self.assertEqual(report["database_source"], "configured_database_url")
        self.assertTrue(report["database_tls_required"])
        self.assertTrue(report["database_tls_enabled"])

    def test_validate_production_config_rejects_sqlite(self) -> None:
        report = validate_production_config(_production_env("sqlite:///tmp/fcd.db"))
        self.assertFalse(report["valid"])
        self.assertIn("Production requires PostgreSQL; SQLite is not permitted.", "\n".join(report["errors"]))

    def test_validate_production_config_rejects_missing_database_url(self) -> None:
        report = validate_production_config(_production_env())
        self.assertFalse(report["valid"])
        self.assertIn("Production requires an explicit DATABASE_URL; db_path fallback is not permitted.", "\n".join(report["errors"]))

    def test_validate_production_config_rejects_postgresql_without_tls(self) -> None:
        report = validate_production_config(_production_env(FAKE_POSTGRES_URL_DISABLE))
        self.assertFalse(report["valid"])
        self.assertIn(
            "Production PostgreSQL DATABASE_URL must use sslmode=require, sslmode=verify-ca, or sslmode=verify-full.",
            "\n".join(report["errors"]),
        )

    def test_validate_production_config_accepts_supported_postgresql_tls_modes(self) -> None:
        for database_url in (FAKE_POSTGRES_URL, FAKE_POSTGRES_URL_VERIFY_CA, FAKE_POSTGRES_URL_VERIFY_FULL):
            with self.subTest(database_url=database_url):
                report = validate_production_config(_production_env(database_url))
                self.assertTrue(report["valid"])
                self.assertEqual(report["database_backend"], "postgresql")
                self.assertTrue(report["database_configured"])
                self.assertTrue(report["database_tls_required"])
                self.assertTrue(report["database_tls_enabled"])

    def test_validate_production_config_rejects_unsupported_database_scheme_without_exposing_credentials(self) -> None:
        report = validate_production_config(_production_env("mysql://app:fake-password@db.example.com/fcd"))
        self.assertFalse(report["valid"])
        self.assertIn("Unsupported database scheme in DATABASE_URL: mysql", "\n".join(report["errors"]))
        self.assertNotIn("fake-password", str(report))

    def test_postgresql_tls_modes_are_classified(self) -> None:
        require_cfg = resolve_database_config({}, database_url=FAKE_POSTGRES_URL)
        verify_ca_cfg = resolve_database_config({}, database_url=FAKE_POSTGRES_URL_VERIFY_CA)
        verify_full_cfg = resolve_database_config({}, database_url=FAKE_POSTGRES_URL_VERIFY_FULL)
        plain_cfg = resolve_database_config({}, database_url=FAKE_POSTGRES_URL_DISABLE)

        self.assertTrue(require_cfg.tls_required)
        self.assertTrue(verify_ca_cfg.tls_required)
        self.assertTrue(verify_full_cfg.tls_required)
        self.assertFalse(plain_cfg.tls_required)
        self.assertFalse(plain_cfg.tls_enabled)


if __name__ == "__main__":
    unittest.main()
