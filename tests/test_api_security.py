from pathlib import Path
import shutil
from tempfile import TemporaryDirectory, mkdtemp
import unittest

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app


class TestApiSecurity(unittest.TestCase):
    def test_auth_rbac_and_metrics(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={
                    "viewer-key": "viewer",
                    "operator-key": "operator",
                    "admin-key": "admin",
                },
                rate_limit_per_minute=100,
                auth_failure_alert_threshold=1,
            )
            client = TestClient(app)

            missing_key_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-sec-1",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-02",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(missing_key_resp.status_code, 401)
            self.assertIn("x-request-id", missing_key_resp.headers)
            self.assertEqual(missing_key_resp.headers.get("x-content-type-options"), "nosniff")
            self.assertEqual(missing_key_resp.headers.get("x-frame-options"), "DENY")

            viewer_forbidden_resp = client.post(
                "/invoices",
                headers={"x-api-key": "viewer-key"},
                json={
                    "invoice_id": "inv-sec-1",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-02",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(viewer_forbidden_resp.status_code, 403)

            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "operator-key"},
                json={
                    "invoice_id": "inv-sec-1",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-02",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            get_resp = client.get("/invoices/inv-sec-1", headers={"x-api-key": "viewer-key"})
            self.assertEqual(get_resp.status_code, 200)

            operator_metrics_forbidden = client.get("/metrics", headers={"x-api-key": "operator-key"})
            self.assertEqual(operator_metrics_forbidden.status_code, 403)

            admin_metrics = client.get("/metrics", headers={"x-api-key": "admin-key"})
            self.assertEqual(admin_metrics.status_code, 200)
            self.assertIn("x-request-id", admin_metrics.headers)
            metrics_body = admin_metrics.json()
            self.assertTrue(metrics_body["security_enabled"])
            self.assertIn("401", metrics_body["status_counts"])
            self.assertIn("auth_failures_total", metrics_body["active_alerts"])
            self.assertEqual(metrics_body["alert_policy"]["auth_failure_alert_threshold"], 1)
            self.assertGreaterEqual(len(metrics_body["recent_audit_events"]), 2)
            self.assertEqual(metrics_body["recent_audit_events"][0]["event_type"], "AUTH_FAILURE")

    def test_rate_limiting(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={
                    "viewer-key": "viewer",
                    "operator-key": "operator",
                    "admin-key": "admin",
                },
                rate_limit_per_minute=2,
                rate_limit_alert_threshold=1,
            )
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "operator-key"},
                json={
                    "invoice_id": "inv-sec-rate",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-02",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            first = client.get("/invoices/inv-sec-rate", headers={"x-api-key": "viewer-key"})
            second = client.get("/invoices/inv-sec-rate", headers={"x-api-key": "viewer-key"})
            third = client.get("/invoices/inv-sec-rate", headers={"x-api-key": "viewer-key"})
            self.assertEqual(first.status_code, 200)
            self.assertEqual(second.status_code, 200)
            self.assertEqual(third.status_code, 429)
            admin_metrics = client.get("/metrics", headers={"x-api-key": "admin-key"})
            self.assertEqual(admin_metrics.status_code, 200)
            self.assertIn("rate_limited_total", admin_metrics.json()["active_alerts"])

    def test_production_requires_strong_signing_key(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api.db")
            with self.assertRaises(ValueError):
                create_app(
                    db_path=db_path,
                    artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                    bundles_dir=str(Path(tmp_dir) / "bundles"),
                    app_env="production",
                    auth_enabled=True,
                    api_keys={"admin-key": "admin"},
                )

            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                app_env="production",
                auth_enabled=True,
                api_keys={"admin-key": "admin"},
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)
            metrics_resp = client.get("/metrics", headers={"x-api-key": "admin-key"})
            self.assertEqual(metrics_resp.status_code, 200)

    def test_export_filename_traversal_is_rejected(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={"operator-key": "operator", "admin-key": "admin"},
                rate_limit_per_minute=100,
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "operator-key"},
                json={
                    "invoice_id": "inv-sec-path",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-02",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            manifest_resp = client.post(
                "/invoices/inv-sec-path/ledger-manifests",
                headers={"x-api-key": "operator-key"},
                json={"output_filename": "..\\evil.json"},
            )
            self.assertEqual(manifest_resp.status_code, 400)
            self.assertIn("simple filename", manifest_resp.json()["detail"])

            absolute_manifest_resp = client.post(
                "/invoices/inv-sec-path/ledger-manifests",
                headers={"x-api-key": "operator-key"},
                json={"output_filename": "C:\\evil.json"},
            )
            self.assertEqual(absolute_manifest_resp.status_code, 400)

            bundle_resp = client.post(
                "/invoices/inv-sec-path/evidence-bundles",
                headers={"x-api-key": "operator-key"},
                json={
                    "communications": ["Reminder"],
                    "formal_notices": ["Letter"],
                    "output_filename": "..\\evil.pdf",
                },
            )
            self.assertEqual(bundle_resp.status_code, 400)

            absolute_bundle_resp = client.post(
                "/invoices/inv-sec-path/evidence-bundles",
                headers={"x-api-key": "operator-key"},
                json={
                    "communications": ["Reminder"],
                    "formal_notices": ["Letter"],
                    "output_filename": "C:\\evil.pdf",
                },
            )
            self.assertEqual(absolute_bundle_resp.status_code, 400)

    def test_readiness_and_startup_validation_endpoint(self) -> None:
        tmp_dir = mkdtemp()
        try:
            db_path = str(Path(tmp_dir) / "api-ready.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={"viewer-key": "viewer", "admin-key": "admin"},
                max_upload_bytes=64,
                manifest_signing_key="non-default-key",
                manifest_key_id="fcd-kms-key-ready",
            )
            with TestClient(app) as client:
                ready_resp = client.get("/ready")
                self.assertEqual(ready_resp.status_code, 200)
                self.assertEqual(ready_resp.json()["status"], "ready")

                forbidden_resp = client.get("/deployment/startup-config-validation", headers={"x-api-key": "viewer-key"})
                self.assertEqual(forbidden_resp.status_code, 403)

                validation_resp = client.get("/deployment/startup-config-validation", headers={"x-api-key": "admin-key"})
                self.assertEqual(validation_resp.status_code, 200)
                validation_body = validation_resp.json()
                self.assertTrue(validation_body["ready"])
                self.assertEqual(validation_body["manifest_key_id"], "fcd-kms-key-ready")
                self.assertIn("database-connectivity", {entry["check"] for entry in validation_body["checks"]})
                self.assertIn("append-only-triggers", {entry["check"] for entry in validation_body["checks"]})
                self.assertGreaterEqual(validation_body["summary"]["total_checks"], 1)
                self.assertIn("generated_at_utc", validation_body)

                report_resp = client.get(
                    "/deployment/startup-config-validation/report", headers={"x-api-key": "admin-key"}
                )
                self.assertEqual(report_resp.status_code, 200)
                report_body = report_resp.json()
                self.assertIn("runbook", report_body)
                self.assertIn("steps", report_body["runbook"])

                runbook_forbidden = client.get("/deployment/runbook", headers={"x-api-key": "viewer-key"})
                self.assertEqual(runbook_forbidden.status_code, 403)
                runbook_resp = client.get("/deployment/runbook", headers={"x-api-key": "admin-key"})
                self.assertEqual(runbook_resp.status_code, 200)
                runbook_body = runbook_resp.json()
                self.assertTrue(runbook_body["ready"])
                self.assertEqual(len(runbook_body["steps"]), 4)
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)

    def test_verify_endpoint_is_public(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-verify-public.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={"viewer-key": "viewer", "admin-key": "admin"},
                manifest_signing_key="non-default-key",
                manifest_key_id="fcd-kms-key-ready",
            )
            with TestClient(app) as client:
                verify_resp = client.get("/verify?case=FCD-R-2026-000001&code=ABCDEFGH")
                self.assertEqual(verify_resp.status_code, 404)
                portal_resp = client.get("/portal?case=FCD-R-2026-000001&code=ABCDEFGH")
                self.assertEqual(portal_resp.status_code, 404)

    def test_readiness_fails_with_invalid_upload_limit(self) -> None:
        tmp_dir = mkdtemp()
        try:
            db_path = str(Path(tmp_dir) / "api-not-ready.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=False,
                app_env="development",
                max_upload_bytes=0,
                allowed_upload_content_types=(),
                allowed_upload_extensions=(),
            )
            with TestClient(app) as client:
                ready_resp = client.get("/ready")
                self.assertEqual(ready_resp.status_code, 503)
                body = ready_resp.json()
                self.assertEqual(body["status"], "not_ready")
                self.assertFalse(body["ready"])
                self.assertIn("allowed-upload-content-types", {entry["check"] for entry in body["errors"]})
                self.assertIn("allowed-upload-extensions", {entry["check"] for entry in body["errors"]})
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
