#
# First Cairn Digital
# P26003 separate API credentials from actor identities
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory, mkdtemp
import unittest
import json
import sqlite3

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.security import ApiSecurityController
from unpaid_invoice_escalator.services.debtor_verification_portal import DebtorVerificationPortal
from unpaid_invoice_escalator.ui import render_invoice_workspace_html


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
                api_identities={
                    "viewer-key": "ACTOR-VIEWER",
                    "operator-key": "ACTOR-OPERATOR",
                    "admin-key": "ACTOR-ADMIN",
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
            self.assertNotIn("operator-key", create_resp.text)

            get_resp = client.get("/invoices/inv-sec-1", headers={"x-api-key": "viewer-key"})
            self.assertEqual(get_resp.status_code, 200)
            self.assertNotIn("viewer-key", get_resp.text)

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
            rbac_event = next(item for item in metrics_body["recent_audit_events"] if item["event_type"] == "RBAC_FORBIDDEN")
            self.assertEqual(rbac_event["identity"], "ACTOR-VIEWER")
            metrics_text = json.dumps(metrics_body)
            self.assertNotIn("viewer-key", metrics_text)
            self.assertNotIn("operator-key", metrics_text)
            self.assertNotIn("admin-key", metrics_text)

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

    def test_production_request_without_client_mapping_is_rejected(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"mapped-key": "viewer"},
            api_clients={},
            api_identities={"mapped-key": "ACTOR-MAPPED"},
            require_explicit_client_mapping=True,
            rate_limit_per_minute=100,
        )

        decision = security.evaluate_request(
            method="GET",
            path="/invoices/inv-sec-1",
            api_key="mapped-key",
            client_host="127.0.0.1",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status_code, 403)
        self.assertEqual(decision.detail, "Authenticated credential is not mapped to a client.")
        self.assertEqual(decision.client_id, "")
        self.assertEqual(decision.identity, "ACTOR-MAPPED")

    def test_authenticated_request_uses_configured_actor_identity(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"mapped-key": "viewer"},
            api_clients={"mapped-key": "CLIENT-A"},
            api_identities={"mapped-key": "ACTOR-A"},
            rate_limit_per_minute=100,
        )

        decision = security.evaluate_request(
            method="GET",
            path="/invoices/inv-sec-1",
            api_key="mapped-key",
            client_host="127.0.0.1",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.identity, "ACTOR-A")
        self.assertEqual(decision.client_id, "CLIENT-A")

    def test_production_request_without_identity_mapping_is_rejected(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"mapped-key": "viewer"},
            api_clients={"mapped-key": "CLIENT-A"},
            api_identities={},
            require_explicit_identity_mapping=True,
            rate_limit_per_minute=100,
        )

        decision = security.evaluate_request(
            method="GET",
            path="/invoices/inv-sec-1",
            api_key="mapped-key",
            client_host="127.0.0.1",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status_code, 403)
        self.assertEqual(decision.detail, "Authenticated credential is not mapped to an actor identity.")
        self.assertNotEqual(decision.identity, "mapped-key")

        metrics_text = json.dumps(security.metrics_snapshot())
        self.assertNotIn("mapped-key", metrics_text)

    def test_development_fallback_identity_preserves_default_client_without_leaking_key(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"dev-key": "operator"},
            api_clients={},
            api_identities={},
            rate_limit_per_minute=100,
        )

        first = security.evaluate_request(
            method="POST",
            path="/invoices",
            api_key="dev-key",
            client_host="127.0.0.1",
        )
        second = security.evaluate_request(
            method="POST",
            path="/invoices",
            api_key="dev-key",
            client_host="127.0.0.1",
        )

        self.assertTrue(first.allowed)
        self.assertEqual(first.client_id, "DEFAULT_CLIENT")
        self.assertEqual(first.identity, second.identity)
        self.assertNotEqual(first.identity, "dev-key")

    def test_invalid_api_key_is_not_persisted_in_auth_audit(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"known-key": "viewer"},
            api_clients={"known-key": "CLIENT-A"},
            api_identities={"known-key": "ACTOR-A"},
            rate_limit_per_minute=100,
        )

        decision = security.evaluate_request(
            method="GET",
            path="/invoices/inv-sec-1",
            api_key="invalid-secret",
            client_host="198.51.100.10",
        )

        self.assertFalse(decision.allowed)
        self.assertEqual(decision.status_code, 401)
        self.assertNotEqual(decision.identity, "invalid-secret")
        metrics_text = json.dumps(security.metrics_snapshot())
        self.assertNotIn("invalid-secret", metrics_text)
        self.assertIn("198.51.100.10", metrics_text)

    def test_public_request_identity_ignores_supplied_api_key(self) -> None:
        security = ApiSecurityController(
            enabled=True,
            api_keys={"known-key": "viewer"},
            api_clients={"known-key": "CLIENT-A"},
            api_identities={"known-key": "ACTOR-A"},
            rate_limit_per_minute=100,
        )

        decision = security.evaluate_request(
            method="GET",
            path="/verify",
            api_key="known-key",
            client_host="203.0.113.7",
        )

        self.assertTrue(decision.allowed)
        self.assertEqual(decision.role, "public")
        self.assertEqual(decision.identity, "public:203.0.113.7")

    def test_production_explicit_client_mapping_preserves_cross_client_isolation(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-prod-tenant.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                app_env="production",
                auth_enabled=True,
                api_keys={
                    "client-a-key": "operator",
                    "client-b-key": "operator",
                    "admin-key": "admin",
                },
                api_clients={
                    "client-a-key": "CLIENT-A",
                    "client-b-key": "CLIENT-B",
                    "admin-key": "FCD-ADMIN",
                },
                api_identities={
                    "client-a-key": "ACTOR-CLIENT-A",
                    "client-b-key": "ACTOR-CLIENT-B",
                    "admin-key": "ACTOR-ADMIN",
                },
                rate_limit_per_minute=100,
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)

            create_a = client.post(
                "/invoices",
                headers={"x-api-key": "client-a-key"},
                json={
                    "invoice_id": "inv-prod-tenant-a",
                    "currency": "GBP",
                    "principal_amount": "250",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_a.status_code, 200)

            create_b = client.post(
                "/invoices",
                headers={"x-api-key": "client-b-key"},
                json={
                    "invoice_id": "inv-prod-tenant-b",
                    "currency": "GBP",
                    "principal_amount": "400",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_b.status_code, 200)

            self.assertEqual(client.get("/invoices/inv-prod-tenant-a", headers={"x-api-key": "client-a-key"}).status_code, 200)
            self.assertEqual(client.get("/invoices/inv-prod-tenant-b", headers={"x-api-key": "client-b-key"}).status_code, 200)
            self.assertEqual(client.get("/invoices/inv-prod-tenant-b", headers={"x-api-key": "client-a-key"}).status_code, 404)

    def test_production_create_app_rejects_missing_or_stale_client_mappings(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-prod-mapping.db")
            kwargs = {
                "db_path": db_path,
                "artifacts_dir": str(Path(tmp_dir) / "artifacts"),
                "bundles_dir": str(Path(tmp_dir) / "bundles"),
                "app_env": "production",
                "auth_enabled": True,
                "api_keys": {"mapped-key": "admin"},
                "rate_limit_per_minute": 100,
                "manifest_signing_key": "production-signing-key",
                "manifest_key_id": "fcd-kms-key-1",
            }

            with self.assertRaisesRegex(ValueError, "missing explicit client mappings"):
                create_app(api_clients={}, api_identities={"mapped-key": "ACTOR-A"}, **kwargs)

            with self.assertRaisesRegex(ValueError, "do not match configured API credentials"):
                create_app(
                    api_clients={"mapped-key": "CLIENT-A", "stale-key": "CLIENT-B"},
                    api_identities={"mapped-key": "ACTOR-A"},
                    **kwargs,
                )

            with self.assertRaisesRegex(ValueError, "missing explicit actor identities"):
                create_app(api_clients={"mapped-key": "CLIENT-A"}, api_identities={}, **kwargs)

            with self.assertRaisesRegex(ValueError, "identity mapping entry/entries do not match configured API credentials"):
                create_app(
                    api_clients={"mapped-key": "CLIENT-A"},
                    api_identities={"mapped-key": "ACTOR-A", "stale-key": "ACTOR-B"},
                    **kwargs,
                )

    def test_public_portal_abuse_protection_scopes_by_case_and_action(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "portal-rate-limit.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={"operator-key": "operator"},
                rate_limit_per_minute=2,
                rate_limit_alert_threshold=1,
            )
            client = TestClient(app)
            store = SQLiteStore(db_path)
            portal = DebtorVerificationPortal(store=store)

            for invoice_id, ref in (("inv-public-1", "INV-PUBLIC-1"), ("inv-public-2", "INV-PUBLIC-2")):
                create_resp = client.post(
                    "/invoices",
                    headers={"x-api-key": "operator-key"},
                    json={
                        "invoice_id": invoice_id,
                        "currency": "GBP",
                        "principal_amount": "200",
                        "issue_date": "2026-01-01",
                        "due_date": "2026-02-01",
                        "jurisdiction": "ENGLAND_WALES",
                        "debtor_type": "LIMITED",
                    },
                )
                self.assertEqual(create_resp.status_code, 200)

            case_one = portal.register_case(invoice_id="inv-public-1", creditor_name="Acme Ltd", invoice_reference="INV-PUBLIC-1")
            case_two = portal.register_case(invoice_id="inv-public-2", creditor_name="Beta Ltd", invoice_reference="INV-PUBLIC-2")

            first_invalid = client.get(f"/verify?case={case_one.case_id}&code=BADCODE")
            second_invalid = client.get(f"/verify?case={case_one.case_id}&code=BADCODE")
            third_invalid = client.get(f"/verify?case={case_one.case_id}&code=BADCODE")
            self.assertEqual(first_invalid.status_code, 404)
            self.assertEqual(second_invalid.status_code, 404)
            self.assertEqual(third_invalid.status_code, 429)

            other_case_valid = client.get(f"/verify?case={case_two.case_id}&code={case_two.verification_code}")
            self.assertEqual(other_case_valid.status_code, 200)

            question_payload = {
                "case": case_one.case_id,
                "code": case_one.verification_code,
                "debtor_identifier": "debtor-public-1",
                "question": "Please clarify the invoice terms.",
            }
            first_action = client.post("/portal/actions/questions", json=question_payload)
            second_action = client.post("/portal/actions/questions", json=question_payload)
            third_action = client.post("/portal/actions/questions", json=question_payload)
            self.assertEqual(first_action.status_code, 200)
            self.assertEqual(second_action.status_code, 200)
            self.assertEqual(third_action.status_code, 429)

            portal_page = client.get(f"/portal?case={case_two.case_id}&code={case_two.verification_code}")
            self.assertEqual(portal_page.status_code, 200)

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
                api_clients={"admin-key": "FCD-ADMIN"},
                api_identities={"admin-key": "ACTOR-ADMIN"},
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

            for manifest_filename in (
                "..\\evil.json",
                "../evil.json",
                "nested\\path.json",
                "nested/path.json",
                "C:\\evil.json",
                "/tmp/evil.json",
            ):
                manifest_resp = client.post(
                    "/invoices/inv-sec-path/ledger-manifests",
                    headers={"x-api-key": "operator-key"},
                    json={"output_filename": manifest_filename},
                )
                self.assertEqual(manifest_resp.status_code, 400)
                self.assertIn("simple filename", manifest_resp.json()["detail"])

            for bundle_filename in (
                "..\\evil.pdf",
                "../evil.pdf",
                "nested\\path.pdf",
                "nested/path.pdf",
                "C:\\evil.pdf",
                "/tmp/evil.pdf",
            ):
                bundle_resp = client.post(
                    "/invoices/inv-sec-path/evidence-bundles",
                    headers={"x-api-key": "operator-key"},
                    json={
                        "communications": ["Reminder"],
                        "formal_notices": ["Letter"],
                        "output_filename": bundle_filename,
                    },
                )
                self.assertEqual(bundle_resp.status_code, 400)
                self.assertIn("simple filename", bundle_resp.json()["detail"])

            valid_manifest_resp = client.post(
                "/invoices/inv-sec-path/ledger-manifests",
                headers={"x-api-key": "operator-key"},
                json={"output_filename": "ledger_manifest.json"},
            )
            self.assertEqual(valid_manifest_resp.status_code, 200)

    def test_bank_detail_dual_control_requires_distinct_authenticated_identities(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "bank-auth.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={
                    "requester-key": "operator",
                    "approver-key": "admin",
                    "viewer-key": "viewer",
                },
                api_clients={
                    "requester-key": "CLIENT-A",
                    "approver-key": "CLIENT-A",
                    "viewer-key": "CLIENT-A",
                },
                api_identities={
                    "requester-key": "ACTOR-REQUESTER",
                    "approver-key": "ACTOR-APPROVER",
                    "viewer-key": "ACTOR-VIEWER",
                },
                rate_limit_per_minute=100,
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "requester-key"},
                json={
                    "invoice_id": "inv-bank-auth",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            viewer_blocked_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "viewer-key"},
                json={
                    "updated_by": "viewer-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approval_reference": "BANK-REF-1",
                },
            )
            self.assertEqual(viewer_blocked_resp.status_code, 403)

            mfa_only_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "requester-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "mfa_reauthenticated": True,
                },
            )
            self.assertEqual(mfa_only_resp.status_code, 404)

            supplied_approver_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "requester-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approved_by": "ADMIN-SUPPLIED",
                    "dual_control_approval_reference": "BANK-REF-1",
                },
            )
            self.assertEqual(supplied_approver_resp.status_code, 404)

            approval_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details/approvals",
                headers={"x-api-key": "approver-key"},
                json={
                    "approval_reference": "BANK-REF-1",
                    "approval_method": "SERVER_SIDE_ADMIN_APPROVAL",
                    "notes": "Approver verified the change off-request.",
                },
            )
            self.assertEqual(approval_resp.status_code, 200)

            self_approval_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "approver-key"},
                json={
                    "updated_by": "approver-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approval_reference": "BANK-REF-1",
                },
            )
            self.assertEqual(self_approval_resp.status_code, 403)

            spoofed_name_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "requester-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approved_by": "spoofed-name",
                    "dual_control_approval_reference": "BANK-REF-1",
                },
            )
            self.assertEqual(spoofed_name_resp.status_code, 403)

            valid_resp = client.post(
                "/invoices/inv-bank-auth/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "requester-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approval_reference": "BANK-REF-1",
                },
            )
            self.assertEqual(valid_resp.status_code, 200)
            self.assertEqual(valid_resp.json()["verification_method"], "ACCOUNT_HOLDER_NAME_CONSISTENCY_CHECK")
            self.assertEqual(valid_resp.json()["cop_state"], "COP_EXACT_MATCH")
            self.assertNotIn("requester-key", valid_resp.text)
            self.assertNotIn("approver-key", valid_resp.text)

            ledger_resp = client.get("/invoices/inv-bank-auth/compliance-ledger", headers={"x-api-key": "viewer-key"})
            self.assertEqual(ledger_resp.status_code, 200)
            events = ledger_resp.json()["entries"]
            approval_event = next(item for item in events if item["event_type"] == "BANK_DETAIL_DUAL_CONTROL_APPROVED")
            update_event = next(item for item in events if item["event_type"] == "BANK_DETAILS_UPDATED_PENDING_COP")
            self.assertEqual(approval_event["details"]["approver_identity"], "ACTOR-APPROVER")
            self.assertEqual(update_event["details"]["requester_identity"], "ACTOR-REQUESTER")
            self.assertEqual(update_event["details"]["approver_identity"], "ACTOR-APPROVER")
            self.assertEqual(update_event["details"]["approval_reference"], "BANK-REF-1")

            cop_text = json.dumps(valid_resp.json())
            self.assertNotIn("CONFIRMATION_OF_PAYEE", cop_text)
            self.assertNotIn("requester-key", json.dumps(events))
            self.assertNotIn("approver-key", json.dumps(events))

    def test_bank_detail_dual_control_rejects_two_credentials_for_same_actor(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "bank-auth-same-actor.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={
                    "requester-key": "operator",
                    "approver-key": "admin",
                },
                api_clients={
                    "requester-key": "CLIENT-A",
                    "approver-key": "CLIENT-A",
                },
                api_identities={
                    "requester-key": "ACTOR-SHARED",
                    "approver-key": "ACTOR-SHARED",
                },
                rate_limit_per_minute=100,
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "requester-key"},
                json={
                    "invoice_id": "inv-bank-same-actor",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            approval_resp = client.post(
                "/invoices/inv-bank-same-actor/settlement-bank-details/approvals",
                headers={"x-api-key": "approver-key"},
                json={
                    "approval_reference": "BANK-SHARED-1",
                    "approval_method": "SERVER_SIDE_ADMIN_APPROVAL",
                    "notes": "Approval recorded under the same actor identity.",
                },
            )
            self.assertEqual(approval_resp.status_code, 200)

            update_resp = client.post(
                "/invoices/inv-bank-same-actor/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "requester-key",
                    "account_holder_name": "Client A Trading Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "Client A Trading Ltd",
                    "dual_control_approval_reference": "BANK-SHARED-1",
                },
            )
            self.assertEqual(update_resp.status_code, 403)
            self.assertIn("distinct authenticated identities", update_resp.json()["detail"])

    def test_tenant_isolation_blocks_cross_client_access(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "tenant.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=True,
                api_keys={
                    "client-a-key": "operator",
                    "client-b-key": "operator",
                    "admin-key": "admin",
                },
                api_clients={
                    "client-a-key": "CLIENT-A",
                    "client-b-key": "CLIENT-B",
                    "admin-key": "FCD-ADMIN",
                },
                rate_limit_per_minute=100,
                manifest_signing_key="production-signing-key",
                manifest_key_id="fcd-kms-key-1",
            )
            client = TestClient(app)

            create_a = client.post(
                "/invoices",
                headers={"x-api-key": "client-a-key"},
                json={
                    "invoice_id": "inv-tenant-a",
                    "currency": "GBP",
                    "principal_amount": "250",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_a.status_code, 200)
            create_b = client.post(
                "/invoices",
                headers={"x-api-key": "client-b-key"},
                json={
                    "invoice_id": "inv-tenant-b",
                    "currency": "GBP",
                    "principal_amount": "400",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_b.status_code, 200)

            self.assertEqual(client.get("/invoices/inv-tenant-a", headers={"x-api-key": "client-a-key"}).status_code, 200)
            self.assertEqual(client.get("/invoices/inv-tenant-b", headers={"x-api-key": "client-b-key"}).status_code, 200)
            self.assertEqual(client.get("/invoices/inv-tenant-b", headers={"x-api-key": "client-a-key"}).status_code, 404)
            self.assertEqual(
                client.post(
                    "/invoices/inv-tenant-b/communications",
                    headers={"x-api-key": "client-a-key"},
                    json={
                        "channel": "EMAIL",
                        "recipient": "b@example.com",
                        "subject": "Cross-tenant attempt",
                        "body_summary": "Should not be visible",
                    },
                ).status_code,
                404,
            )
            self.assertEqual(
                client.get(
                    "/invoices/inv-tenant-b/evidence-bundle?output_filename=tenant.pdf",
                    headers={"x-api-key": "client-a-key"},
                ).status_code,
                404,
            )
            self.assertEqual(client.get("/invoices/inv-tenant-b/debtor-ledger", headers={"x-api-key": "client-a-key"}).status_code, 404)
            self.assertEqual(
                client.post(
                    "/invoices/inv-tenant-b/settlement-bank-details",
                    headers={"x-api-key": "client-a-key"},
                    json={
                        "updated_by": "client-a-key",
                        "account_holder_name": "Client B Trading Ltd",
                        "sort_code": "12-34-56",
                        "account_number": "12345678",
                        "expected_payee_name": "Client B Trading Ltd",
                        "dual_control_approval_reference": "BANK-CROSS-TENANT",
                    },
                ).status_code,
                404,
            )
            self.assertEqual(
                client.post(
                    "/invoices/inv-tenant-b/resolution/payment-plans",
                    headers={"x-api-key": "client-a-key"},
                    json={
                        "proposed_by": "USER-A",
                        "installment_amount_gbp": "50",
                        "installment_count": 4,
                        "first_due_date": "2026-02-15",
                        "frequency_days": 30,
                        "notes": "Cross tenant attempt",
                    },
                ).status_code,
                404,
            )
            self.assertEqual(
                client.post(
                    "/invoices/inv-tenant-b/resolution/settlement-offers",
                    headers={"x-api-key": "client-a-key"},
                    json={
                        "offered_by": "USER-A",
                        "offered_amount_gbp": "300",
                        "expiry_date": "2026-02-15",
                        "notes": "Cross tenant attempt",
                    },
                ).status_code,
                404,
            )

            client_fee_resp = client.post(
                "/invoices/inv-tenant-a/client-fee-ledger/actions",
                headers={"x-api-key": "client-a-key"},
                json={
                    "case_id": "CASE-A",
                    "client_id": "CLIENT-B",
                    "action_selected": "MONTHLY_SAAS_TIER",
                    "accepted_by_user": "USER-A",
                },
            )
            self.assertEqual(client_fee_resp.status_code, 200)
            ledger_resp = client.get("/invoices/inv-tenant-a/client-fee-ledger", headers={"x-api-key": "client-a-key"})
            self.assertEqual(ledger_resp.status_code, 200)
            self.assertEqual(ledger_resp.json()["entries"][0]["client_id"], "CLIENT-A")

            admin_invoice_a = client.get("/invoices/inv-tenant-a", headers={"x-api-key": "admin-key"})
            admin_invoice_b = client.get("/invoices/inv-tenant-b", headers={"x-api-key": "admin-key"})
            self.assertEqual(admin_invoice_a.status_code, 200)
            self.assertEqual(admin_invoice_b.status_code, 200)
            admin_list = client.get("/dashboard", headers={"x-api-key": "admin-key"})
            self.assertEqual(admin_list.status_code, 200)
            self.assertEqual(admin_list.json()["metrics"]["active_cases"], 2)

    def test_existing_invoice_rows_are_migrated_with_default_client(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "legacy.db")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE invoices (
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
                    CREATE TABLE debtor_ledger_entries (
                        entry_id TEXT PRIMARY KEY,
                        invoice_id TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        entry_type TEXT NOT NULL,
                        amount_gbp TEXT NOT NULL,
                        description TEXT NOT NULL,
                        recovery_cost_category TEXT,
                        linked_client_fee_entry_id TEXT
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO invoices (
                        invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    ("legacy-invoice", "GBP", "100.00", "2026-01-01", "2026-01-31", "ENGLAND_WALES", "LIMITED", "2026-01-01T00:00:00+00:00"),
                )
                conn.execute(
                    """
                    INSERT INTO debtor_ledger_entries (
                        entry_id, invoice_id, timestamp, entry_type, amount_gbp, description, recovery_cost_category, linked_client_fee_entry_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        "legacy-invoice-principal",
                        "legacy-invoice",
                        "2026-01-01T00:00:00+00:00",
                        "ORIGINAL_PRINCIPAL",
                        "100.00",
                        "Legacy principal",
                        None,
                        None,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                auth_enabled=False,
            )
            client = TestClient(app)
            resp = client.get("/invoices/legacy-invoice")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.json()["invoice_id"], "legacy-invoice")

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
                api_identities={"viewer-key": "ACTOR-VIEWER", "admin-key": "ACTOR-ADMIN"},
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
                self.assertEqual(validation_body["api_identity_mapping_count"], 2)
                self.assertIn("database-connectivity", {entry["check"] for entry in validation_body["checks"]})
                self.assertIn("append-only-triggers", {entry["check"] for entry in validation_body["checks"]})
                self.assertGreaterEqual(validation_body["summary"]["total_checks"], 1)
                self.assertIn("generated_at_utc", validation_body)
                self.assertNotIn("viewer-key", json.dumps(validation_body))
                self.assertNotIn("admin-key", json.dumps(validation_body))

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
                self.assertEqual(len(runbook_body["steps"]), 5)
                self.assertTrue(any("retention" in json.dumps(step).lower() for step in runbook_body["steps"]))
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
                api_identities={"viewer-key": "ACTOR-VIEWER", "admin-key": "ACTOR-ADMIN"},
                manifest_signing_key="non-default-key",
                manifest_key_id="fcd-kms-key-ready",
            )
            with TestClient(app) as client:
                verify_resp = client.get("/verify?case=FCD-R-2026-000001&code=ABCDEFGH", headers={"x-api-key": "viewer-key"})
                self.assertEqual(verify_resp.status_code, 404)
                portal_resp = client.get("/portal?case=FCD-R-2026-000001&code=ABCDEFGH", headers={"x-api-key": "viewer-key"})
                self.assertEqual(portal_resp.status_code, 404)
                payment_link_resp = client.get("/portal/payment-link?case=FCD-R-2026-000001&code=ABCDEFGH", headers={"x-api-key": "viewer-key"})
                self.assertEqual(payment_link_resp.status_code, 404)

    def test_invoice_workspace_escapes_hostile_invoice_id(self) -> None:
        malicious_invoice_id = 'inv-"><script>alert(1)</script>'
        html = render_invoice_workspace_html(malicious_invoice_id)
        self.assertNotIn('</script><script>alert(1)</script>', html)
        escaped_id = json.dumps(malicious_invoice_id).replace("</", "<\\/")
        self.assertIn(f'const workspaceInvoiceId = {escaped_id};', html)

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
