#
# First Cairn Digital
# P26003 bounded hostile upload handling
import asyncio
from datetime import date, timedelta
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
from urllib.parse import quote

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import UPLOAD_READ_CHUNK_BYTES, _read_upload_content_bounded, create_app
from unpaid_invoice_escalator.production_config import validate_production_config


class TestApi(unittest.TestCase):
    def test_invoice_flow(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            home_resp = client.get("/")
            self.assertEqual(home_resp.status_code, 200)
            self.assertIn("Engine Dashboard", home_resp.text)
            dashboard_page = client.get("/ui/dashboard")
            self.assertEqual(dashboard_page.status_code, 200)
            cases_page = client.get("/ui/cases")
            self.assertEqual(cases_page.status_code, 200)
            self.assertIn("Five-ledger snapshot", cases_page.text)
            self.assertIn("Latest case activity", cases_page.text)
            self.assertEqual(client.get("/ui/debtors").status_code, 200)
            self.assertEqual(client.get("/ui/creditors").status_code, 200)
            self.assertEqual(client.get("/ui/disputes").status_code, 200)
            operations_page = client.get("/ui/operations")
            self.assertEqual(operations_page.status_code, 200)
            self.assertIn("Recent communication activity", operations_page.text)
            self.assertIn("Payment plan actions", operations_page.text)
            self.assertIn("Settlement actions", operations_page.text)
            self.assertIn("Reported payment review", operations_page.text)
            self.assertIn("Report installment payment for verification", operations_page.text)
            compliance_page = client.get("/ui/compliance")
            self.assertEqual(compliance_page.status_code, 200)
            self.assertIn("Humane pause controls", compliance_page.text)
            self.assertIn("Company status review", compliance_page.text)
            self.assertIn("Restricted note controls", compliance_page.text)
            self.assertIn("function renderGovernanceSummary", compliance_page.text)
            self.assertIn("Client handoff readiness", compliance_page.text)
            reports_page = client.get("/ui/reports")
            self.assertEqual(reports_page.status_code, 200)
            self.assertIn("Environment checks", reports_page.text)
            self.assertIn("Policy controls", reports_page.text)
            self.assertIn("Retention queue", reports_page.text)
            self.assertIn("Retention schedule", reports_page.text)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-1",
                    "currency": "GBP",
                    "principal_amount": "2800",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "NORTHERN_IRELAND",
                    "debtor_type": "SOLE_TRADER",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            dashboard_resp = client.get("/dashboard")
            self.assertEqual(dashboard_resp.status_code, 200)
            self.assertEqual(dashboard_resp.json()["metrics"]["active_cases"], 1)
            self.assertEqual(dashboard_resp.json()["cases"][0]["invoice_id"], "inv-api-1")
            invoice_resp = client.get("/invoices/inv-api-1")
            self.assertEqual(invoice_resp.status_code, 200)
            self.assertEqual(invoice_resp.json()["outstanding_balance_gbp"], "2800.00")
            case_health_resp = client.post(
                "/invoices/inv-api-1/case-health-check",
                json={
                    "user_id": "USER-102",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(case_health_resp.status_code, 200)
            self.assertEqual(case_health_resp.json()["case_confidence"], "READY")

            verification_register_resp = client.post(
                "/invoices/inv-api-1/debtor-verification/register",
                json={"creditor_name": "First Cairn Digital Client Ltd", "invoice_reference": "INV-001"},
            )
            self.assertEqual(verification_register_resp.status_code, 200)
            verification_body = verification_register_resp.json()
            verify_resp = client.get(
                f"/verify?case={verification_body['case_id']}&code={verification_body['verification_code']}"
            )
            self.assertEqual(verify_resp.status_code, 200)
            self.assertTrue(verify_resp.json()["valid"])
            portal_resp = client.get(
                f"/portal?case={verification_body['case_id']}&code={verification_body['verification_code']}"
            )
            self.assertEqual(portal_resp.status_code, 200)
            self.assertIn("resolution_options", portal_resp.json())
            self.assertIn("Data Processor", portal_resp.json()["source_of_data_notice"])
            self.assertFalse(portal_resp.json()["settlement_destination_available"])

            unauthorized_bank_update = client.post(
                "/invoices/inv-api-1/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "First Cairn Digital Client Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "mfa_reauthenticated": False,
                },
            )
            self.assertEqual(unauthorized_bank_update.status_code, 404)

            approval_resp = client.post(
                "/invoices/inv-api-1/settlement-bank-details/approvals",
                headers={"x-api-key": "approver-key"},
                json={
                    "approval_reference": "APPROVAL-REF-1",
                    "approval_method": "AUTHENTICATED_ADMIN_APPROVAL",
                    "notes": "Verified by admin prior to bank update.",
                },
            )
            self.assertEqual(approval_resp.status_code, 200)

            authorized_bank_update = client.post(
                "/invoices/inv-api-1/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "First Cairn Digital Client Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "dual_control_approval_reference": "APPROVAL-REF-1",
                },
            )
            self.assertEqual(authorized_bank_update.status_code, 200)
            self.assertEqual(authorized_bank_update.json()["cop_state"], "COP_EXACT_MATCH")
            self.assertEqual(
                authorized_bank_update.json()["verification_method"],
                "ACCOUNT_HOLDER_NAME_CONSISTENCY_CHECK",
            )

            bank_details_resp = client.get("/invoices/inv-api-1/settlement-bank-details")
            self.assertEqual(bank_details_resp.status_code, 200)
            self.assertGreaterEqual(bank_details_resp.json()["count"], 2)

            portal_with_verified_bank = client.get(
                f"/portal?case={verification_body['case_id']}&code={verification_body['verification_code']}"
            )
            self.assertEqual(portal_with_verified_bank.status_code, 200)
            self.assertTrue(portal_with_verified_bank.json()["settlement_destination_available"])

            failed_bank_update = client.post(
                "/invoices/inv-api-1/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "Unexpected Name",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "dual_control_approval_reference": "APPROVAL-REF-1",
                    "dual_control_approved_by": "WRONG-APPROVER",
                    "mfa_reauthenticated": True,
                },
            )
            self.assertEqual(failed_bank_update.status_code, 403)

            portal_with_failed_bank = client.get(
                f"/portal?case={verification_body['case_id']}&code={verification_body['verification_code']}"
            )
            self.assertEqual(portal_with_failed_bank.status_code, 200)
            self.assertTrue(portal_with_failed_bank.json()["settlement_destination_available"])

            comm_create_resp = client.post(
                "/invoices/inv-api-1/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "accounts@example.com",
                    "subject": "Invoice reminder",
                    "body_summary": "Friendly reminder for outstanding invoice.",
                },
            )
            self.assertEqual(comm_create_resp.status_code, 200)
            communication_id = comm_create_resp.json()["communication_id"]
            self.assertEqual(comm_create_resp.json()["delivery_state"], "CREATED")
            for state in ("QUEUED", "SENT", "DELIVERED", "OPENED"):
                comm_state_resp = client.post(
                    f"/invoices/inv-api-1/communications/{communication_id}/delivery-events",
                    json={"state": state, "note": f"{state} update"},
                )
                self.assertEqual(comm_state_resp.status_code, 200)
            comm_list_resp = client.get("/invoices/inv-api-1/communications")
            self.assertEqual(comm_list_resp.status_code, 200)
            self.assertEqual(comm_list_resp.json()["communications"][0]["latest_state"], "OPENED")

            legal_gate_resp = client.post(
                "/invoices/inv-api-1/legal-safety-gate/confirm",
                json={
                    "user_id": "USER-102",
                    "amount_claimed_gbp": "2800",
                    "payments_recorded_gbp": "0",
                    "authorised_to_act": True,
                    "info_accurate": True,
                    "invoice_unpaid": True,
                    "payments_recorded_complete": True,
                    "genuine_supporting_docs": True,
                    "no_unresolved_dispute": True,
                    "commercial_not_excluded": True,
                },
            )
            self.assertEqual(legal_gate_resp.status_code, 200)
            self.assertTrue(legal_gate_resp.json()["accepted"])

            discrepancy_resp = client.post(
                "/invoices/inv-api-1/discrepancy-check",
                json={
                    "claim_amount": "2800",
                    "evidence_document_amount": "2800",
                    "principal": "2800",
                    "payments_recorded": "0",
                    "outstanding_entered": "2800",
                },
            )
            self.assertEqual(discrepancy_resp.status_code, 200)
            self.assertEqual(discrepancy_resp.json()["status"], "VALIDATED")

            compliance_resp = client.get("/invoices/inv-api-1/compliance-ledger")
            self.assertEqual(compliance_resp.status_code, 200)
            self.assertGreaterEqual(compliance_resp.json()["count"], 2)

            five_ledger_resp = client.get("/invoices/inv-api-1/five-ledger-summary")
            self.assertEqual(five_ledger_resp.status_code, 200)
            self.assertEqual(five_ledger_resp.json()["outstanding_balance_gbp"], "2800.00")
            self.assertGreaterEqual(five_ledger_resp.json()["compliance_ledger_events_count"], 4)

            fee_action_resp = client.post(
                "/invoices/inv-api-1/client-fee-ledger/actions",
                json={
                    "case_id": "FCD-R-2026-000184",
                    "client_id": "CLI-8841",
                    "action_selected": "FORMAL_ESCALATION",
                    "accepted_by_user": "John Smith (USER-102)",
                },
            )
            self.assertEqual(fee_action_resp.status_code, 200)
            self.assertEqual(fee_action_resp.json()["fee_amount_gbp"], "9.95")

            court_quote_resp = client.post(
                "/invoices/inv-api-1/court-fee-quotes",
                json={"claim_value_gbp": "2800"},
            )
            self.assertEqual(court_quote_resp.status_code, 200)
            self.assertEqual(court_quote_resp.json()["official_court_fee_gbp"], "163")
            viability_resp = client.post(
                "/invoices/inv-api-1/viability-proportionality-assessments",
                json={
                    "on_date": "2026-02-01",
                    "projected_action": "PRE_ACTION_PACK",
                    "estimated_time_cost_gbp": "30",
                    "company_status": "ACTIVE",
                },
            )
            self.assertEqual(viability_resp.status_code, 200)
            self.assertIn("projected_total_cost_gbp", viability_resp.json())

            cost_assess_resp = client.post(
                "/invoices/inv-api-1/recovery-cost-assessments",
                json={
                    "recovery_cost_gbp": "39.95",
                    "has_contractual_recovery_clause": False,
                    "is_official_court_fee": False,
                    "statutory_reasonable_recovery_allowed": True,
                },
            )
            self.assertEqual(cost_assess_resp.status_code, 200)
            self.assertEqual(
                cost_assess_resp.json()["category"],
                "STATUTORY_REASONABLE_RECOVERY_COST",
            )

            debtor_entry_resp = client.post(
                "/invoices/inv-api-1/debtor-ledger/entries",
                json={
                    "entry_type": "STATUTORY_INTEREST",
                    "amount_gbp": "12.50",
                    "description": "Accrued interest",
                },
            )
            self.assertEqual(debtor_entry_resp.status_code, 200)

            debtor_ledger_resp = client.get("/invoices/inv-api-1/debtor-ledger")
            self.assertEqual(debtor_ledger_resp.status_code, 200)
            self.assertEqual(debtor_ledger_resp.json()["balance_gbp"], "2812.50")
            client_ledger_resp = client.get("/invoices/inv-api-1/client-fee-ledger")
            self.assertEqual(client_ledger_resp.status_code, 200)
            self.assertEqual(client_ledger_resp.json()["balance_gbp"], "11.94")
            updated_invoice_resp = client.get("/invoices/inv-api-1")
            self.assertEqual(updated_invoice_resp.status_code, 200)
            self.assertEqual(updated_invoice_resp.json()["outstanding_balance_gbp"], "2812.50")

            hygiene_resp = client.post(
                "/invoices/inv-api-1/pre-overdue-hygiene",
                json={
                    "creditor_legal_entity_name": "First Cairn Digital Ltd",
                    "creditor_companies_house_number": "SC123456",
                    "creditor_vat_number": "GB123456789",
                    "creditor_trading_address": "1 Example Street, Glasgow",
                    "debtor_legal_entity_name": "Example Buyer Ltd",
                    "debtor_companies_house_number": "NI654321",
                    "debtor_vat_number": "GB987654321",
                    "debtor_trading_address": "2 Sample Road, Belfast",
                    "po_required": True,
                    "po_reference": None,
                    "payment_terms_days": 30,
                    "contractual_interest_clause_present": True,
                    "contractual_recovery_clause_present": False,
                    "proof_of_delivery_required": True,
                    "suggested_clause_text": "Draft clause",
                    "notes": "Initial setup review",
                },
            )
            self.assertEqual(hygiene_resp.status_code, 200)
            hygiene_body = hygiene_resp.json()
            self.assertFalse(hygiene_body["checklist_complete"])
            self.assertIn("Contractual recovery charges clause", hygiene_body["missing_items"])
            self.assertEqual(hygiene_body["warning_tier"], "NONE")
            self.assertEqual(hygiene_body["format_warnings"], [])
            self.assertEqual(hygiene_body["disclaimer"], "Requires Client Independent Legal Review")

            hygiene_warn_resp = client.post(
                "/invoices/inv-api-1/pre-overdue-hygiene",
                json={
                    "creditor_legal_entity_name": "First Cairn Digital Ltd",
                    "creditor_companies_house_number": "BAD-123",
                    "creditor_vat_number": "XX999",
                    "creditor_trading_address": "1 Example Street, Glasgow",
                    "debtor_legal_entity_name": "Example Buyer Ltd",
                    "debtor_companies_house_number": "BAD-456",
                    "debtor_vat_number": "YY999",
                    "debtor_trading_address": "2 Sample Road, Belfast",
                    "po_required": False,
                    "po_reference": None,
                    "payment_terms_days": 30,
                    "contractual_interest_clause_present": True,
                    "contractual_recovery_clause_present": True,
                    "proof_of_delivery_required": True,
                    "suggested_clause_text": None,
                    "notes": "format checks",
                },
            )
            self.assertEqual(hygiene_warn_resp.status_code, 200)
            hygiene_warn_body = hygiene_warn_resp.json()
            self.assertEqual(hygiene_warn_body["warning_tier"], "HIGH")
            self.assertEqual(len(hygiene_warn_body["format_warnings"]), 4)

            hygiene_list_resp = client.get("/invoices/inv-api-1/pre-overdue-hygiene")
            self.assertEqual(hygiene_list_resp.status_code, 200)
            hygiene_list_body = hygiene_list_resp.json()
            self.assertEqual(hygiene_list_body["count"], 2)
            self.assertEqual(hygiene_list_body["records"][1]["warning_tier"], "HIGH")

            workspace_resp = client.get("/ui/invoices/inv-api-1")
            self.assertEqual(workspace_resp.status_code, 200)
            self.assertIn("Invoice Workspace", workspace_resp.text)
            self.assertIn("Outstanding Balance", workspace_resp.text)
            self.assertIn("Resolution artifacts", workspace_resp.text)
            self.assertIn("Ledger manifest controls", workspace_resp.text)
            self.assertIn("Settlement acceptance", workspace_resp.text)
            self.assertIn("Settlement progress", workspace_resp.text)
            self.assertIn("Reported payment review", workspace_resp.text)
            self.assertIn("Governance snapshot", workspace_resp.text)
            self.assertIn("Client handoff readiness", workspace_resp.text)
            self.assertIn("Portal activity", workspace_resp.text)
            self.assertIn("Company status", workspace_resp.text)
            self.assertIn("Restricted notes", workspace_resp.text)
            self.assertIn("Retention review", workspace_resp.text)
            rule_resp = client.get("/rule-packs/NORTHERN_IRELAND/active?on_date=2026-02-01")
            self.assertEqual(rule_resp.status_code, 200)
            self.assertEqual(rule_resp.json()["rule_id"], "ni-commercial-invoice-recovery")

            escalate_resp = client.post(
                "/invoices/inv-api-1/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(escalate_resp.status_code, 200)
            self.assertEqual(escalate_resp.json()["next_state"], "PRE_ACTION_PROTOCOL")
            self.assertIn("viability_assessment", escalate_resp.json())
            self.assertEqual(escalate_resp.json()["communication_preview"]["level"], 5)
            self.assertIn("message", escalate_resp.json()["communication_preview"])

            preview_resp = client.get(
                "/invoices/inv-api-1/communication-preview?state=OVERDUE_CHASER&on_date=2026-02-01"
            )
            self.assertEqual(preview_resp.status_code, 200)
            self.assertEqual(preview_resp.json()["level"], 2)

            upload_resp = client.post(
                "/invoices/inv-api-1/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"contract terms", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 200)
            self.assertEqual(upload_resp.json()["artifact_type"], "CONTRACT")

            upload_resp = client.post(
                "/invoices/inv-api-1/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "PROOF_OF_DELIVERY"},
                files={"file": ("proof.txt", b"proof of delivery", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 200)

            artifacts_resp = client.get("/invoices/inv-api-1/evidence-artifacts?artifact_type=CONTRACT&limit=1&offset=0")
            self.assertEqual(artifacts_resp.status_code, 200)
            artifacts_body = artifacts_resp.json()
            self.assertEqual(artifacts_body["count"], 1)
            self.assertEqual(artifacts_body["total_count"], 1)
            self.assertEqual(artifacts_body["artifacts"][0]["artifact_type"], "CONTRACT")

            events_resp = client.get(
                "/invoices/inv-api-1/ledger-events?event_type=EVIDENCE_ARTIFACT_UPLOADED&limit=1&offset=0"
            )
            self.assertEqual(events_resp.status_code, 200)
            events_body = events_resp.json()
            self.assertTrue(events_body["chain_valid"])
            self.assertEqual(events_body["count"], 1)
            self.assertGreaterEqual(events_body["total_count"], 2)

            bundle_resp = client.post(
                "/invoices/inv-api-1/evidence-bundles",
                json={"communications": ["Reminder sent"], "formal_notices": ["Letter of Claim"]},
            )
            self.assertEqual(bundle_resp.status_code, 200)
            bundle_path = Path(bundle_resp.json()["bundle_path"])
            self.assertTrue(bundle_path.exists())

            manifest_resp = client.post(
                "/invoices/inv-api-1/ledger-manifests",
                json={"output_filename": "manifest.json"},
            )
            self.assertEqual(manifest_resp.status_code, 200)
            body = manifest_resp.json()
            self.assertEqual(body["manifest_format"], "json")
            self.assertEqual(body["outstanding_balance_gbp"], "2812.50")
            self.assertTrue(body["chain_valid"])
            manifest_path = Path(body["manifest_path"])
            self.assertTrue(manifest_path.exists())
            self.assertEqual(body["signature"]["algorithm"], "HMAC-SHA256")
            verify_resp = client.post(
                "/invoices/inv-api-1/ledger-manifests/verify",
                json={"output_filename": "manifest.json"},
            )
            self.assertEqual(verify_resp.status_code, 200)
            verify_body = verify_resp.json()
            self.assertTrue(verify_body["signature_valid"])
            self.assertTrue(verify_body["core_matches_current_ledger"])
            self.assertTrue(verify_body["overall_valid"])

            audit_trail_resp = client.get("/invoices/inv-api-1/audit-trail")
            self.assertEqual(audit_trail_resp.status_code, 200)
            audit_trail_body = audit_trail_resp.json()
            self.assertGreaterEqual(audit_trail_body["count"], 3)
            self.assertIn("EXPORT", {item["category"] for item in audit_trail_body["entries"]})

            manifest_pdf_resp = client.post(
                "/invoices/inv-api-1/ledger-manifests",
                json={"output_filename": "manifest.pdf", "output_format": "pdf"},
            )
            self.assertEqual(manifest_pdf_resp.status_code, 200)
            pdf_body = manifest_pdf_resp.json()
            self.assertEqual(pdf_body["manifest_format"], "pdf")
            manifest_pdf_path = Path(pdf_body["manifest_path"])
            self.assertTrue(manifest_pdf_path.exists())
            self.assertTrue(manifest_pdf_path.read_bytes().startswith(b"%PDF-1.4"))

            calc_resp = client.post(
                "/invoices/inv-api-1/late-payment-calculations",
                json={
                    "as_of_date": "2026-03-15",
                    "is_commercial_transaction": True,
                    "base_rate_override": "0.05",
                },
            )
            self.assertEqual(calc_resp.status_code, 200)
            calc_body = calc_resp.json()
            self.assertTrue(calc_body["eligible"])
            self.assertEqual(calc_body["rule_id"], "ni-commercial-invoice-recovery")
            self.assertIsNotNone(calc_body["breakdown"])

    def test_upload_limit_enforced(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-limit.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(
                db_path=db_path,
                artifacts_dir=artifacts_dir,
                bundles_dir=bundles_dir,
                max_upload_bytes=8,
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-limit",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            below_limit_resp = client.post(
                "/invoices/inv-api-limit/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("below.txt", b"1234567", "text/plain")},
            )
            self.assertEqual(below_limit_resp.status_code, 200)
            self.assertEqual(Path(below_limit_resp.json()["file_path"]).read_bytes(), b"1234567")

            exact_limit_resp = client.post(
                "/invoices/inv-api-limit/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("exact.txt", b"12345678", "text/plain")},
            )
            self.assertEqual(exact_limit_resp.status_code, 200)
            self.assertEqual(Path(exact_limit_resp.json()["file_path"]).read_bytes(), b"12345678")

            over_limit_resp = client.post(
                "/invoices/inv-api-limit/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"123456789", "text/plain")},
            )
            self.assertEqual(over_limit_resp.status_code, 413)

    def test_bounded_upload_reader_stops_after_limit_exceeded(self) -> None:
        class RecordingUpload:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload
                self._offset = 0
                self.read_sizes: list[int] = []

            async def read(self, size: int = -1) -> bytes:
                self.read_sizes.append(size)
                if size < 0:
                    raise AssertionError("unbounded read requested")
                chunk = self._payload[self._offset : self._offset + size]
                self._offset += len(chunk)
                return chunk

        upload = RecordingUpload(b"x" * 100)
        result = asyncio.run(_read_upload_content_bounded(upload, max_bytes=8, chunk_size=4))

        self.assertTrue(result.limit_exceeded)
        self.assertEqual(upload.read_sizes, [4, 4, 4])
        self.assertLessEqual(len(result.content), 12)

    def test_oversized_upload_quarantine_is_bounded_and_truncated(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-limit-quarantine.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            quarantine_dir = str(Path(tmp_dir) / "quarantine")
            app = create_app(
                db_path=db_path,
                artifacts_dir=artifacts_dir,
                bundles_dir=bundles_dir,
                quarantine_dir=quarantine_dir,
                max_upload_bytes=8,
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-limit-quarantine",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            upload_resp = client.post(
                "/invoices/inv-api-limit-quarantine/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("large.txt", b"x" * (UPLOAD_READ_CHUNK_BYTES + 100), "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 413)
            self.assertIn("Quarantine reference:", upload_resp.json()["detail"])

            quarantine_invoice_dir = Path(quarantine_dir) / "inv-api-limit-quarantine"
            metadata_path = next(path for path in quarantine_invoice_dir.glob("*.json"))
            payload = json.loads(metadata_path.read_text(encoding="utf-8"))
            quarantine_blob = next(path for path in quarantine_invoice_dir.iterdir() if path.suffix != ".json")
            self.assertTrue(payload["truncated"])
            self.assertFalse(payload["original_size_known"])
            self.assertEqual(payload["captured_bytes"], quarantine_blob.stat().st_size)
            self.assertLessEqual(payload["captured_bytes"], 8 + UPLOAD_READ_CHUNK_BYTES)
            self.assertNotIn("size_bytes", payload)
            self.assertIn("truncation_reason", payload)

    def test_upload_content_type_allowlist_enforced(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-content-type.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(
                db_path=db_path,
                artifacts_dir=artifacts_dir,
                bundles_dir=bundles_dir,
                allowed_upload_content_types=("application/pdf",),
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-ct",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            upload_resp = client.post(
                "/invoices/inv-api-ct/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"contract terms", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 415)

    def test_legal_safety_gate_requires_all_declarations(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-gate.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-gate",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            gate_resp = client.post(
                "/invoices/inv-api-gate/legal-safety-gate/confirm",
                json={
                    "user_id": "USER-1",
                    "amount_claimed_gbp": "100",
                    "payments_recorded_gbp": "0",
                    "authorised_to_act": True,
                    "info_accurate": True,
                    "invoice_unpaid": True,
                    "payments_recorded_complete": False,
                    "genuine_supporting_docs": True,
                    "no_unresolved_dispute": True,
                    "commercial_not_excluded": True,
                },
            )
            self.assertEqual(gate_resp.status_code, 400)

    def test_escalation_blocked_until_health_and_accuracy_resolution(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-escalation-guard.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-guard",
                    "currency": "GBP",
                    "principal_amount": "500",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            blocked_resp = client.post(
                "/invoices/inv-api-guard/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_resp.status_code, 409)

            health_resp = client.post(
                "/invoices/inv-api-guard/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(health_resp.status_code, 200)

            challenge_resp = client.post(
                "/invoices/inv-api-guard/debtor-actions/data-accuracy-challenge",
                json={
                    "debtor_identifier": "debtor@example.com",
                    "challenge_reason": "DATA_INACCURATE",
                    "challenge_details": "Address record is outdated.",
                },
            )
            self.assertEqual(challenge_resp.status_code, 200)

            blocked_challenge_resp = client.post(
                "/invoices/inv-api-guard/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_challenge_resp.status_code, 409)

            resolve_resp = client.post(
                "/invoices/inv-api-guard/debtor-actions/data-accuracy-challenge/resolve",
                json={
                    "creditor_user_id": "USER-1",
                    "resolution_notes": "Corrected records uploaded.",
                },
            )
            self.assertEqual(resolve_resp.status_code, 200)

            allowed_resp = client.post(
                "/invoices/inv-api-guard/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(allowed_resp.status_code, 200)

    def test_escalation_blocked_by_viability_financial_distress(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-viability-block.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-viability",
                    "currency": "GBP",
                    "principal_amount": "800",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            health_resp = client.post(
                "/invoices/inv-api-viability/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(health_resp.status_code, 200)
            discrepancy_resp = client.post(
                "/invoices/inv-api-viability/discrepancy-check",
                json={
                    "claim_amount": "800",
                    "evidence_document_amount": "800",
                    "principal": "800",
                    "payments_recorded": "0",
                    "outstanding_entered": "800",
                },
            )
            self.assertEqual(discrepancy_resp.status_code, 200)
            blocked_resp = client.post(
                "/invoices/inv-api-viability/escalate",
                json={
                    "today": "2026-02-01",
                    "current_state": "OVERDUE_CHASER",
                    "company_status": "INSOLVENT",
                },
            )
            self.assertEqual(blocked_resp.status_code, 409)

    def test_portal_actions_execute_workflows(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-portal-actions.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-portal",
                    "currency": "GBP",
                    "principal_amount": "1200",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            reg_resp = client.post(
                "/invoices/inv-api-portal/debtor-verification/register",
                json={"creditor_name": "Creditor Ltd", "invoice_reference": "INV-PORTAL-1"},
            )
            self.assertEqual(reg_resp.status_code, 200)
            case_id = reg_resp.json()["case_id"]
            code = reg_resp.json()["verification_code"]

            accuracy_resp = client.post(
                "/portal/actions/data-accuracy-challenge",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "challenge_reason": "Incorrect amount",
                    "challenge_details": "Please verify amount and credits.",
                },
            )
            self.assertEqual(accuracy_resp.status_code, 200)
            self.assertTrue(accuracy_resp.json()["recovery_restricted"])

            plan_resp = client.post(
                "/portal/actions/payment-plan-proposals",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "installment_amount_gbp": "100",
                    "installment_count": 3,
                    "first_due_date": "2026-03-01",
                    "frequency_days": 30,
                    "notes": "Debtor-proposed schedule",
                },
            )
            self.assertEqual(plan_resp.status_code, 200)
            self.assertEqual(plan_resp.json()["status"], "PROPOSED")
            self.assertFalse(plan_resp.json()["chasers_paused"])

            offer_resp = client.post(
                "/portal/actions/settlement-offers",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "offered_amount_gbp": "900",
                    "expiry_date": "2026-04-01",
                    "notes": "Settlement proposal",
                },
            )
            self.assertEqual(offer_resp.status_code, 200)
            self.assertEqual(offer_resp.json()["status"], "OPEN")

            question_resp = client.post(
                "/portal/actions/questions",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "question": "Can you confirm which invoice line this relates to?",
                },
            )
            self.assertEqual(question_resp.status_code, 200)

            promise_date_resp = client.post(
                "/portal/actions/confirm-payment-date",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "promised_payment_date": "2026-03-15",
                    "notes": "Payment expected by bank transfer.",
                },
            )
            self.assertEqual(promise_date_resp.status_code, 200)

            already_paid_resp = client.post(
                "/portal/actions/already-paid",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "payment_reference": "PAID-REF-1",
                    "payment_date": "2026-02-10",
                    "amount_gbp": "100",
                    "details": "Please reconcile this payment.",
                },
            )
            self.assertEqual(already_paid_resp.status_code, 200)

            comm_resp = client.post(
                "/invoices/inv-api-portal/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Reminder",
                    "body_summary": "Pending send",
                    "automated": True,
                },
            )
            self.assertEqual(comm_resp.status_code, 200)
            comm_id = comm_resp.json()["communication_id"]
            client.post(
                f"/invoices/inv-api-portal/communications/{comm_id}/delivery-events",
                json={"state": "QUEUED", "note": "queued"},
            )

            paid_resp = client.post(
                "/portal/actions/confirm-paid",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "amount_gbp": "250",
                    "payment_reference": "BANK-XYZ",
                    "payment_date": "2026-02-11",
                    "details": "Bank transfer reported by debtor.",
                },
            )
            self.assertEqual(paid_resp.status_code, 200)
            report_id = paid_resp.json()["report_id"]
            self.assertEqual(paid_resp.json()["status"], "PAYMENT_VERIFICATION_PENDING")
            self.assertEqual(paid_resp.json()["outstanding_balance_gbp"], "1200.00")
            self.assertEqual(len(paid_resp.json()["cancelled_pending_communication_ids"]), 1)
            ledger_events_before_confirm = client.get("/invoices/inv-api-portal/ledger-events")
            self.assertEqual(ledger_events_before_confirm.status_code, 200)
            event_types_before_confirm = {item["event_type"] for item in ledger_events_before_confirm.json()["events"]}
            self.assertIn("DEBTOR_PAYMENT_REPORTED", event_types_before_confirm)
            self.assertNotIn("PAYMENT_RECEIVED", event_types_before_confirm)
            debtor_ledger_resp = client.get("/invoices/inv-api-portal/debtor-ledger")
            self.assertEqual(debtor_ledger_resp.status_code, 200)
            self.assertEqual(debtor_ledger_resp.json()["balance_gbp"], "1200.00")

            payment_evidence_resp = client.post(
                f"/portal/actions/reported-payments/{report_id}/evidence",
                data={"case": case_id, "code": code, "debtor_identifier": "debtor-portal"},
                files={"file": ("remittance.txt", b"proof of transfer", "text/plain")},
            )
            self.assertEqual(payment_evidence_resp.status_code, 200)
            self.assertEqual(payment_evidence_resp.json()["artifact_type"], "PAYMENT_EVIDENCE")

            list_reports_resp = client.get("/invoices/inv-api-portal/reported-payments")
            self.assertEqual(list_reports_resp.status_code, 200)
            self.assertEqual(list_reports_resp.json()["count"], 1)
            self.assertTrue(list_reports_resp.json()["payment_verification_pending"])
            self.assertEqual(list_reports_resp.json()["reports"][0]["status"], "PAYMENT_VERIFICATION_PENDING")
            self.assertEqual(len(list_reports_resp.json()["reports"][0]["evidence_document_ids"]), 1)

            needs_evidence_resp = client.post(
                f"/invoices/inv-api-portal/reported-payments/{report_id}/needs-evidence",
                json={"creditor_user_id": "USER-1", "notes": "Please confirm remittance advice."},
            )
            self.assertEqual(needs_evidence_resp.status_code, 200)
            self.assertEqual(needs_evidence_resp.json()["status"], "NEEDS_EVIDENCE")

            confirm_payment_resp = client.post(
                f"/invoices/inv-api-portal/reported-payments/{report_id}/confirm",
                json={"creditor_user_id": "USER-1", "notes": "Matched to bank statement."},
            )
            self.assertEqual(confirm_payment_resp.status_code, 200)
            self.assertEqual(confirm_payment_resp.json()["status"], "PAYMENT_CONFIRMED_BY_CREDITOR")
            self.assertEqual(confirm_payment_resp.json()["outstanding_balance_gbp"], "950.00")

            compliance_resp = client.get("/invoices/inv-api-portal/compliance-ledger")
            self.assertEqual(compliance_resp.status_code, 200)
            events = {item["event_type"] for item in compliance_resp.json()["entries"]}
            self.assertIn("DATA_ACCURACY_CHALLENGE_OPEN", events)
            self.assertIn("PAYMENT_PLAN_PROPOSED", events)
            self.assertIn("SETTLEMENT_OFFER_PROPOSED", events)
            self.assertIn("PORTAL_QUESTION_SUBMITTED", events)
            self.assertIn("PORTAL_PAYMENT_DATE_CONFIRMED", events)
            self.assertIn("DEBTOR_PAYMENT_REPORTED", events)
            self.assertIn("PAYMENT_VERIFICATION_PENDING", events)
            self.assertIn("DEBTOR_PAYMENT_EVIDENCE_UPLOADED", events)
            self.assertIn("PAYMENT_EVIDENCE_REQUESTED", events)
            self.assertIn("PAYMENT_CONFIRMED_BY_CREDITOR", events)

    def test_reported_payment_confirmation_caps_overreported_amount(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-overreported-payment.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-overreport",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            reg_resp = client.post(
                "/invoices/inv-api-overreport/debtor-verification/register",
                json={"creditor_name": "Creditor Ltd", "invoice_reference": "INV-OVER-1"},
            )
            self.assertEqual(reg_resp.status_code, 200)
            case_id = reg_resp.json()["case_id"]
            code = reg_resp.json()["verification_code"]
            paid_resp = client.post(
                "/portal/actions/confirm-paid",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-overreport",
                    "amount_gbp": "250",
                    "payment_reference": "BANK-OVER",
                    "payment_date": "2026-02-11",
                    "details": "Reported amount exceeds balance.",
                },
            )
            self.assertEqual(paid_resp.status_code, 200)
            self.assertEqual(paid_resp.json()["status"], "PAYMENT_VERIFICATION_PENDING")
            report_id = paid_resp.json()["report_id"]

            confirm_resp = client.post(
                f"/invoices/inv-api-overreport/reported-payments/{report_id}/confirm",
                json={"creditor_user_id": "USER-1", "notes": "Matched to statement."},
            )
            self.assertEqual(confirm_resp.status_code, 200)
            self.assertEqual(confirm_resp.json()["status"], "PAYMENT_CONFIRMED_BY_CREDITOR")
            self.assertEqual(confirm_resp.json()["confirmed_amount_gbp"], "100.00")
            self.assertEqual(confirm_resp.json()["outstanding_balance_gbp"], "0.00")
            debtor_ledger_resp = client.get("/invoices/inv-api-overreport/debtor-ledger")
            self.assertEqual(debtor_ledger_resp.status_code, 200)
            self.assertEqual(debtor_ledger_resp.json()["balance_gbp"], "0.00")

    def test_escalation_blocked_while_reported_payment_awaits_creditor_verification(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-payment-verification-gate.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-payment-gate",
                    "currency": "GBP",
                    "principal_amount": "700",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            register_resp = client.post(
                "/invoices/inv-api-payment-gate/debtor-verification/register",
                json={"creditor_name": "Creditor Ltd", "invoice_reference": "INV-GATE-1"},
            )
            self.assertEqual(register_resp.status_code, 200)
            case_id = register_resp.json()["case_id"]
            code = register_resp.json()["verification_code"]
            health_resp = client.post(
                "/invoices/inv-api-payment-gate/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(health_resp.status_code, 200)
            discrepancy_resp = client.post(
                "/invoices/inv-api-payment-gate/discrepancy-check",
                json={
                    "claim_amount": "700",
                    "evidence_document_amount": "700",
                    "principal": "700",
                    "payments_recorded": "0",
                    "outstanding_entered": "700",
                },
            )
            self.assertEqual(discrepancy_resp.status_code, 200)
            report_resp = client.post(
                "/portal/actions/confirm-paid",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "amount_gbp": "175",
                    "payment_reference": "BANK-175",
                },
            )
            self.assertEqual(report_resp.status_code, 200)
            report_id = report_resp.json()["report_id"]

            blocked_escalate_resp = client.post(
                "/invoices/inv-api-payment-gate/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_escalate_resp.status_code, 409)
            self.assertIn("awaiting creditor verification", blocked_escalate_resp.json()["detail"])

            reject_resp = client.post(
                f"/invoices/inv-api-payment-gate/reported-payments/{report_id}/reject",
                json={
                    "creditor_user_id": "USER-1",
                    "reason": "No matching funds received.",
                    "notes": "Checked current account ledger.",
                },
            )
            self.assertEqual(reject_resp.status_code, 200)
            self.assertTrue(reject_resp.json()["requires_gate_re_evaluation"])

            debtor_ledger_resp = client.get("/invoices/inv-api-payment-gate/debtor-ledger")
            self.assertEqual(debtor_ledger_resp.status_code, 200)
            self.assertEqual(debtor_ledger_resp.json()["balance_gbp"], "700.00")

            resumed_escalate_resp = client.post(
                "/invoices/inv-api-payment-gate/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(resumed_escalate_resp.status_code, 200)

    def test_escalation_blocked_on_delivery_failure_until_requeued(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-delivery-block.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-delivery",
                    "currency": "GBP",
                    "principal_amount": "700",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            health_resp = client.post(
                "/invoices/inv-api-delivery/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(health_resp.status_code, 200)
            discrepancy_resp = client.post(
                "/invoices/inv-api-delivery/discrepancy-check",
                json={
                    "claim_amount": "700",
                    "evidence_document_amount": "700",
                    "principal": "700",
                    "payments_recorded": "0",
                    "outstanding_entered": "700",
                },
            )
            self.assertEqual(discrepancy_resp.status_code, 200)
            comm_resp = client.post(
                "/invoices/inv-api-delivery/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Notice",
                    "body_summary": "Notice summary",
                },
            )
            self.assertEqual(comm_resp.status_code, 200)
            communication_id = comm_resp.json()["communication_id"]
            client.post(
                f"/invoices/inv-api-delivery/communications/{communication_id}/delivery-events",
                json={"state": "QUEUED", "note": "queued"},
            )
            client.post(
                f"/invoices/inv-api-delivery/communications/{communication_id}/delivery-events",
                json={"state": "SENT", "note": "sent"},
            )
            fail_resp = client.post(
                f"/invoices/inv-api-delivery/communications/{communication_id}/delivery-events",
                json={"state": "BOUNCED", "note": "bounced"},
            )
            self.assertEqual(fail_resp.status_code, 200)
            blocked_escalate = client.post(
                "/invoices/inv-api-delivery/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_escalate.status_code, 409)
            requeue_resp = client.post(
                f"/invoices/inv-api-delivery/communications/{communication_id}/delivery-events",
                json={"state": "QUEUED", "note": "contact corrected and requeued"},
            )
            self.assertEqual(requeue_resp.status_code, 200)
            resumed_escalate = client.post(
                "/invoices/inv-api-delivery/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(resumed_escalate.status_code, 200)

    def test_escalation_blocked_by_portal_dispute_and_promised_date(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-portal-blocks.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-portal-blocks",
                    "currency": "GBP",
                    "principal_amount": "950",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            client.post(
                "/invoices/inv-api-portal-blocks/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            client.post(
                "/invoices/inv-api-portal-blocks/discrepancy-check",
                json={
                    "claim_amount": "950",
                    "evidence_document_amount": "950",
                    "principal": "950",
                    "payments_recorded": "0",
                    "outstanding_entered": "950",
                },
            )
            reg = client.post(
                "/invoices/inv-api-portal-blocks/debtor-verification/register",
                json={"creditor_name": "Creditor Ltd", "invoice_reference": "INV-PORTAL-BLOCK"},
            ).json()
            case_id = reg["case_id"]
            code = reg["verification_code"]

            client.post(
                "/portal/actions/disputes",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "reason": "Quality dispute",
                    "details": "Goods not as described",
                },
            )
            blocked_dispute = client.post(
                "/invoices/inv-api-portal-blocks/escalate",
                json={"today": "2026-02-10", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_dispute.status_code, 409)

            resolve_dispute = client.post(
                "/invoices/inv-api-portal-blocks/debtor-actions/dispute/resolve",
                json={"creditor_user_id": "USER-1", "resolution_notes": "Resolved by evidence review."},
            )
            self.assertEqual(resolve_dispute.status_code, 200)

            client.post(
                "/portal/actions/confirm-payment-date",
                json={
                    "case": case_id,
                    "code": code,
                    "debtor_identifier": "debtor-portal",
                    "promised_payment_date": "2026-03-01",
                    "notes": "Pending transfer",
                },
            )
            blocked_promised_date = client.post(
                "/invoices/inv-api-portal-blocks/escalate",
                json={"today": "2026-02-20", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_promised_date.status_code, 409)

            allowed_after_date = client.post(
                "/invoices/inv-api-portal-blocks/escalate",
                json={"today": "2026-03-02", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(allowed_after_date.status_code, 200)

    def test_balance_correction_withdraws_and_reissues_statement(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-balance-correction.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-correction",
                    "currency": "GBP",
                    "principal_amount": "900",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            communication_resp = client.post(
                "/invoices/inv-api-correction/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Outstanding Balance Notice",
                    "body_summary": "Balance reminder",
                    "automated": True,
                },
            )
            self.assertEqual(communication_resp.status_code, 200)
            communication_id = communication_resp.json()["communication_id"]
            queue_resp = client.post(
                f"/invoices/inv-api-correction/communications/{communication_id}/delivery-events",
                json={"state": "QUEUED", "note": "queued"},
            )
            self.assertEqual(queue_resp.status_code, 200)

            correction_resp = client.post(
                f"/invoices/inv-api-correction/communications/{communication_id}/balance-corrections",
                json={
                    "corrected_by": "USER-1",
                    "correction_reason": "Payment allocation error corrected.",
                    "corrected_statement_summary": "Revised balance statement issued after correction.",
                    "corrected_statement_subject": "Corrected Balance Statement",
                },
            )
            self.assertEqual(correction_resp.status_code, 200)
            self.assertTrue(correction_resp.json()["cancelled_original"])

            comms_resp = client.get("/invoices/inv-api-correction/communications")
            self.assertEqual(comms_resp.status_code, 200)
            by_id = {item["communication_id"]: item for item in comms_resp.json()["communications"]}
            self.assertEqual(by_id[communication_id]["latest_state"], "CANCELLED")
            self.assertIn("Withdrawal Notice:", by_id[correction_resp.json()["withdrawal_notice_communication_id"]]["subject"])
            self.assertEqual(
                by_id[correction_resp.json()["corrected_statement_communication_id"]]["subject"],
                "Corrected Balance Statement",
            )

            compliance_resp = client.get("/invoices/inv-api-correction/compliance-ledger")
            self.assertEqual(compliance_resp.status_code, 200)
            event_types = {item["event_type"] for item in compliance_resp.json()["entries"]}
            self.assertIn("ERROR_CORRECTED", event_types)
            self.assertIn("COMMUNICATION_WITHDRAWN", event_types)

            ledger_resp = client.get("/invoices/inv-api-correction/ledger-events")
            self.assertEqual(ledger_resp.status_code, 200)
            ledger_event_types = {item["event_type"] for item in ledger_resp.json()["events"]}
            self.assertIn("ERROR_CORRECTED", ledger_event_types)
            self.assertIn("COMMUNICATION_WITHDRAWN", ledger_event_types)

    def test_payment_or_credit_cancels_pending_automated_communications(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-cancel-pending.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-cancel",
                    "currency": "GBP",
                    "principal_amount": "500",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            comm_one = client.post(
                "/invoices/inv-api-cancel/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Reminder 1",
                    "body_summary": "Pending reminder one",
                    "automated": True,
                },
            ).json()["communication_id"]
            comm_two = client.post(
                "/invoices/inv-api-cancel/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Reminder 2",
                    "body_summary": "Pending reminder two",
                    "automated": True,
                },
            ).json()["communication_id"]
            client.post(
                f"/invoices/inv-api-cancel/communications/{comm_one}/delivery-events",
                json={"state": "QUEUED", "note": "queued one"},
            )
            client.post(
                f"/invoices/inv-api-cancel/communications/{comm_two}/delivery-events",
                json={"state": "QUEUED", "note": "queued two"},
            )
            payment_resp = client.post(
                "/invoices/inv-api-cancel/debtor-ledger/entries",
                json={"entry_type": "PAYMENT_RECEIVED", "amount_gbp": "-100", "description": "Partial payment"},
            )
            self.assertEqual(payment_resp.status_code, 200)
            cancelled = payment_resp.json()["cancelled_pending_communication_ids"]
            self.assertEqual(len(cancelled), 2)
            comms_resp = client.get("/invoices/inv-api-cancel/communications")
            self.assertEqual(comms_resp.status_code, 200)
            self.assertEqual(
                {item["latest_state"] for item in comms_resp.json()["communications"]},
                {"CANCELLED"},
            )

    def test_pre_send_balance_lock_blocks_send_when_no_outstanding(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-balance-lock.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-lock",
                    "currency": "GBP",
                    "principal_amount": "250",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            client.post(
                "/invoices/inv-api-lock/debtor-ledger/entries",
                json={"entry_type": "PAYMENT_RECEIVED", "amount_gbp": "-250", "description": "Paid in full"},
            )
            preview_resp = client.get(
                "/invoices/inv-api-lock/communication-preview?state=OVERDUE_CHASER&on_date=2026-02-01"
            )
            self.assertEqual(preview_resp.status_code, 200)
            self.assertIn("£0.00", preview_resp.json()["message"])
            comm_resp = client.post(
                "/invoices/inv-api-lock/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Manual note",
                    "body_summary": "Non-automated note",
                    "automated": False,
                },
            )
            self.assertEqual(comm_resp.status_code, 200)
            communication_id = comm_resp.json()["communication_id"]
            queued_resp = client.post(
                f"/invoices/inv-api-lock/communications/{communication_id}/delivery-events",
                json={"state": "QUEUED", "note": "queued"},
            )
            self.assertEqual(queued_resp.status_code, 200)
            blocked_send = client.post(
                f"/invoices/inv-api-lock/communications/{communication_id}/delivery-events",
                json={"state": "SENT", "note": "attempt send"},
            )
            self.assertEqual(blocked_send.status_code, 200)

            automated_comm = client.post(
                "/invoices/inv-api-lock/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "debtor@example.com",
                    "subject": "Automated note",
                    "body_summary": "Automated comm",
                    "automated": True,
                },
            )
            self.assertEqual(automated_comm.status_code, 409)

    def test_late_payment_calculation_uses_current_balance(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-late-payment.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-late",
                    "currency": "GBP",
                    "principal_amount": "2000",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            client.post(
                "/invoices/inv-api-late/debtor-ledger/entries",
                json={"entry_type": "PAYMENT_RECEIVED", "amount_gbp": "-1500", "description": "Partial payment"},
            )
            calc_resp = client.post(
                "/invoices/inv-api-late/late-payment-calculations",
                json={
                    "as_of_date": "2026-02-10",
                    "is_commercial_transaction": True,
                    "base_rate_override": "0.05",
                },
            )
            self.assertEqual(calc_resp.status_code, 200)
            self.assertEqual(calc_resp.json()["breakdown"]["fixed_compensation"], "40")

    def test_escalation_uses_current_balance_for_jurisdiction_limit(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-jurisdiction-balance.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-jur-balance",
                    "currency": "GBP",
                    "principal_amount": "6500",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "SCOTLAND",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            client.post(
                "/invoices/inv-api-jur-balance/case-health-check",
                json={
                    "user_id": "USER-204",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            client.post(
                "/invoices/inv-api-jur-balance/legal-safety-gate/confirm",
                json={
                    "user_id": "USER-204",
                    "amount_claimed_gbp": "6500",
                    "payments_recorded_gbp": "0",
                    "authorised_to_act": True,
                    "info_accurate": True,
                    "invoice_unpaid": True,
                    "payments_recorded_complete": True,
                    "genuine_supporting_docs": True,
                    "no_unresolved_dispute": True,
                    "commercial_not_excluded": True,
                },
            )
            client.post(
                "/invoices/inv-api-jur-balance/discrepancy-check",
                json={
                    "claim_amount": "6500",
                    "evidence_document_amount": "6500",
                    "principal": "6500",
                    "payments_recorded": "0",
                    "outstanding_entered": "6500",
                },
            )
            client.post(
                "/invoices/inv-api-jur-balance/debtor-ledger/entries",
                json={
                    "entry_type": "PAYMENT_RECEIVED",
                    "amount_gbp": "-2600",
                    "description": "Partial payment",
                },
            )
            escalate_resp = client.post(
                "/invoices/inv-api-jur-balance/escalate",
                json={"today": "2026-02-01", "current_state": "ISSUED"},
            )
            self.assertEqual(escalate_resp.status_code, 200)
            self.assertEqual(escalate_resp.json()["next_state"], "FRIENDLY_REMINDER")

    def test_upload_rejection_quarantine_and_metrics(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-quarantine.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            quarantine_dir = str(Path(tmp_dir) / "quarantine")
            app = create_app(
                db_path=db_path,
                artifacts_dir=artifacts_dir,
                bundles_dir=bundles_dir,
                quarantine_dir=quarantine_dir,
                allowed_upload_extensions=(".pdf",),
                allowed_upload_content_types=("application/pdf",),
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-quarantine",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            upload_resp = client.post(
                "/invoices/inv-api-quarantine/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("payload.exe", b"malicious", "application/octet-stream")},
            )
            self.assertEqual(upload_resp.status_code, 415)
            self.assertIn("Quarantine reference:", upload_resp.json()["detail"])

            metrics_resp = client.get("/metrics")
            self.assertEqual(metrics_resp.status_code, 200)
            metrics_body = metrics_resp.json()
            self.assertEqual(metrics_body["upload_rejected_total"], 1)
            self.assertEqual(metrics_body["upload_quarantined_total"], 1)
            self.assertGreaterEqual(
                metrics_body["upload_rejections_by_reason"].get(
                    "Unsupported file extension. Allowed extensions: .pdf",
                    0,
                ),
                1,
            )

            quarantine_files = list((Path(quarantine_dir) / "inv-api-quarantine").glob("*"))
            self.assertGreaterEqual(len(quarantine_files), 2)
            metadata_path = next(path for path in quarantine_files if path.suffix == ".json")
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            self.assertEqual(metadata["size_bytes"], len(b"malicious"))
            self.assertEqual(metadata["captured_bytes"], len(b"malicious"))
            self.assertFalse(metadata["truncated"])
            self.assertTrue(metadata["original_size_known"])

    def test_data_retention_disposal_workflow(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-retention.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-retention",
                    "currency": "GBP",
                    "principal_amount": "600",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            upload_resp = client.post(
                "/invoices/inv-api-retention/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"signed terms", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 200)
            artifact_path = Path(upload_resp.json()["file_path"])
            self.assertTrue(artifact_path.exists())

            policy_resp = client.get("/data-retention-policy")
            self.assertEqual(policy_resp.status_code, 200)
            self.assertGreater(policy_resp.json()["policy"]["retention_days"], 0)

            review_resp = client.get("/invoices/inv-api-retention/data-retention-review?as_of_date=2035-01-01")
            self.assertEqual(review_resp.status_code, 200)
            self.assertTrue(review_resp.json()["eligible_for_disposal"])
            self.assertEqual(review_resp.json()["retention_state"], "ELIGIBLE_FOR_DISPOSAL")
            self.assertEqual(review_resp.json()["days_until_disposal_eligibility"], 0)

            queue_resp = client.get("/data-retention-queue?as_of_date=2035-01-01")
            self.assertEqual(queue_resp.status_code, 200)
            self.assertEqual(queue_resp.json()["summary"]["eligible_for_disposal"], 1)
            self.assertEqual(queue_resp.json()["items"][0]["invoice_id"], "inv-api-retention")

            dispose_resp = client.post(
                "/invoices/inv-api-retention/data-retention-disposals",
                json={"approved_by": "ADMIN-1", "reason": "Retention period complete", "as_of_date": "2035-01-01"},
            )
            self.assertEqual(dispose_resp.status_code, 200)
            self.assertEqual(dispose_resp.json()["deleted_file_count"], 1)
            self.assertFalse(artifact_path.exists())

            compliance_resp = client.get("/invoices/inv-api-retention/compliance-ledger")
            self.assertEqual(compliance_resp.status_code, 200)
            self.assertIn(
                "DATA_RETENTION_DISPOSAL_EXECUTED",
                {entry["event_type"] for entry in compliance_resp.json()["entries"]},
            )

    def test_data_retention_legal_hold_blocks_disposal(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-retention-hold.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-retention-hold",
                    "currency": "GBP",
                    "principal_amount": "700",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            upload_resp = client.post(
                "/invoices/inv-api-retention-hold/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"signed terms", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 200)
            artifact_path = Path(upload_resp.json()["file_path"])
            self.assertTrue(artifact_path.exists())

            open_hold = client.post(
                "/invoices/inv-api-retention-hold/data-retention-legal-holds/open",
                json={"held_by": "ADMIN-1", "reason": "Solicitor review pending", "hold_type": "LITIGATION_REVIEW"},
            )
            self.assertEqual(open_hold.status_code, 200)
            self.assertTrue(open_hold.json()["legal_hold_open"])

            review_resp = client.get("/invoices/inv-api-retention-hold/data-retention-review?as_of_date=2035-01-01")
            self.assertEqual(review_resp.status_code, 200)
            self.assertTrue(review_resp.json()["legal_hold_open"])
            self.assertIn("Active legal hold blocks retention disposal.", review_resp.json()["blockers"])
            self.assertEqual(review_resp.json()["retention_state"], "LEGAL_HOLD")
            self.assertIsNone(review_resp.json()["days_until_disposal_eligibility"])

            blocked_dispose = client.post(
                "/invoices/inv-api-retention-hold/data-retention-disposals",
                json={"approved_by": "ADMIN-1", "reason": "Retention complete", "as_of_date": "2035-01-01"},
            )
            self.assertEqual(blocked_dispose.status_code, 409)
            self.assertTrue(artifact_path.exists())

            release_hold = client.post(
                "/invoices/inv-api-retention-hold/data-retention-legal-holds/release",
                json={"released_by": "ADMIN-2", "reason": "Review completed"},
            )
            self.assertEqual(release_hold.status_code, 200)
            self.assertFalse(release_hold.json()["legal_hold_open"])

            dispose_after_release = client.post(
                "/invoices/inv-api-retention-hold/data-retention-disposals",
                json={"approved_by": "ADMIN-1", "reason": "Retention complete", "as_of_date": "2035-01-01"},
            )
            self.assertEqual(dispose_after_release.status_code, 200)
            self.assertFalse(artifact_path.exists())

    def test_client_handoff_quotes_england_wales_mid_band_fee(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-handoff-gap.db")
            app = create_app(db_path=db_path, artifacts_dir=str(Path(tmp_dir) / "artifacts"), bundles_dir=str(Path(tmp_dir) / "bundles"))
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-ew-gap",
                    "currency": "GBP",
                    "principal_amount": "1250",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            handoff_resp = client.get("/invoices/inv-ew-gap/client-handoff")
            self.assertEqual(handoff_resp.status_code, 200)
            self.assertEqual(handoff_resp.json()["official_court_fee_gbp"], "80")
            self.assertIn("payable to the court authority", handoff_resp.json()["external_fee_notice"])

            fee_quote_resp = client.post(
                "/invoices/inv-ew-gap/court-fee-quotes",
                json={"claim_value_gbp": "1250"},
            )
            self.assertEqual(fee_quote_resp.status_code, 200)
            self.assertEqual(fee_quote_resp.json()["official_court_fee_gbp"], "80")

    def test_data_retention_taxonomy_and_active_hold_guardrail(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-retention-taxonomy.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-retention-taxonomy",
                    "currency": "GBP",
                    "principal_amount": "1500",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "SCOTLAND",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            policy_resp = client.get("/data-retention-policy")
            self.assertEqual(policy_resp.status_code, 200)
            policy = policy_resp.json()["policy"]
            self.assertIn("STANDARD_COMMERCIAL", policy["retention_variants"])
            self.assertIn("VAT_TAX_AUDIT", policy["retention_variants"])

            open_hold = client.post(
                "/invoices/inv-api-retention-taxonomy/data-retention-legal-holds/open",
                json={
                    "held_by": "ADMIN-1",
                    "reason": "Tax audit",
                    "holdType": "TAX_AUDIT",
                    "reason_code": "VAT-01",
                    "version": 2,
                    "retentionVariant": "VAT_TAX_AUDIT",
                },
            )
            self.assertEqual(open_hold.status_code, 200)
            self.assertEqual(open_hold.json()["details"]["hold_type"], "TAX_AUDIT")
            self.assertEqual(open_hold.json()["details"]["version"], 2)

            blocked_dispose = client.post(
                "/invoices/inv-api-retention-taxonomy/data-retention-disposals",
                json={"approved_by": "ADMIN-1", "reason": "Retention complete", "as_of_date": "2035-01-01"},
            )
            self.assertEqual(blocked_dispose.status_code, 409)
            self.assertIn("LEGAL_HOLD_ACTIVE", blocked_dispose.json()["detail"])

    def test_resolution_and_settlement_endpoints(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-resolution.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-resolution",
                    "currency": "GBP",
                    "principal_amount": "1000",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)
            verification_resp = client.post(
                "/invoices/inv-api-resolution/debtor-verification/register",
                json={"creditor_name": "Creditor Ltd", "invoice_reference": "INV-RES"},
            )
            self.assertEqual(verification_resp.status_code, 200)
            verification_case = verification_resp.json()

            health_resp = client.post(
                "/invoices/inv-api-resolution/case-health-check",
                json={
                    "user_id": "USER-1",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(health_resp.status_code, 200)

            discrepancy_resp = client.post(
                "/invoices/inv-api-resolution/discrepancy-check",
                json={
                    "claim_amount": "1000",
                    "evidence_document_amount": "1000",
                    "principal": "1000",
                    "payments_recorded": "0",
                    "outstanding_entered": "1000",
                },
            )
            self.assertEqual(discrepancy_resp.status_code, 200)

            first_due_date = date.today() + timedelta(days=5)
            settlement_expiry_date = date.today() + timedelta(days=20)
            settlement_payment_date = date.today()

            plan_resp = client.post(
                "/invoices/inv-api-resolution/resolution/payment-plans",
                json={
                    "proposed_by": "USER-1",
                    "installment_amount_gbp": "200",
                    "installment_count": 3,
                    "first_due_date": first_due_date.isoformat(),
                    "frequency_days": 30,
                    "notes": "Plan terms",
                },
            )
            self.assertEqual(plan_resp.status_code, 200)
            plan_body = plan_resp.json()
            plan_id = plan_body["plan_id"]
            self.assertEqual(plan_body["status"], "PROPOSED")
            self.assertFalse(plan_body["chasers_paused"])

            proposal_escalate_resp = client.post(
                "/invoices/inv-api-resolution/escalate",
                json={"today": "2026-02-15", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(proposal_escalate_resp.status_code, 200)

            accept_plan_resp = client.post(
                f"/invoices/inv-api-resolution/resolution/payment-plans/{plan_id}/accept",
                json={"accepted_by": "Debtor Contact", "accepter_role": "DEBTOR"},
            )
            self.assertEqual(accept_plan_resp.status_code, 200)
            self.assertEqual(accept_plan_resp.json()["status"], "ACTIVE")
            self.assertTrue(accept_plan_resp.json()["chasers_paused"])

            blocked_escalate_resp = client.post(
                "/invoices/inv-api-resolution/escalate",
                json={"today": "2026-02-15", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(blocked_escalate_resp.status_code, 409)

            pay_resp = client.post(
                f"/invoices/inv-api-resolution/resolution/payment-plans/{plan_id}/payments",
                json={
                    "installment_id": plan_body["installments"][0]["installment_id"],
                    "amount_gbp": "200",
                    "recorded_by": "USER-1",
                },
            )
            self.assertEqual(pay_resp.status_code, 200)
            report_id = pay_resp.json()["report_id"]
            self.assertEqual(pay_resp.json()["status"], "PAYMENT_VERIFICATION_PENDING")

            confirm_pay_resp = client.post(
                f"/invoices/inv-api-resolution/reported-payments/{report_id}/confirm",
                json={"creditor_user_id": "USER-1", "notes": "Cleared funds matched."},
            )
            self.assertEqual(confirm_pay_resp.status_code, 200)
            self.assertIsNotNone(confirm_pay_resp.json()["payment_plan_payment_id"])

            plans_list_resp = client.get(
                f"/invoices/inv-api-resolution/resolution/payment-plans?as_of_date={(first_due_date + timedelta(days=95)).isoformat()}"
            )
            self.assertEqual(plans_list_resp.status_code, 200)
            self.assertEqual(plans_list_resp.json()["plans"][0]["status"], "DEFAULTED")
            self.assertEqual(plans_list_resp.json()["plans"][0]["paid_amount_gbp"], "200.00")

            promise_artifact_resp = client.post(
                "/invoices/inv-api-resolution/resolution/artifacts/promise-to-pay",
                json={"plan_id": plan_id, "output_filename": "promise-to-pay.pdf"},
            )
            self.assertEqual(promise_artifact_resp.status_code, 200)
            promise_body = promise_artifact_resp.json()
            self.assertEqual(promise_body["artifact_type"], "PROMISE_TO_PAY")
            self.assertTrue(Path(promise_body["artifact_path"]).exists())

            resumed_escalate_resp = client.post(
                "/invoices/inv-api-resolution/escalate",
                json={"today": (first_due_date + timedelta(days=95)).isoformat(), "current_state": "FRIENDLY_REMINDER"},
            )
            self.assertEqual(resumed_escalate_resp.status_code, 200)
            self.assertEqual(resumed_escalate_resp.json()["next_state"], "FORMAL_NOTICE")

            offer_resp = client.post(
                "/invoices/inv-api-resolution/resolution/settlement-offers",
                json={
                    "offered_by": "USER-1",
                    "offered_amount_gbp": "750",
                    "expiry_date": settlement_expiry_date.isoformat(),
                    "notes": "Full and final",
                },
            )
            self.assertEqual(offer_resp.status_code, 200)
            offer_id = offer_resp.json()["offer_id"]

            accept_debtor_resp = client.post(
                f"/invoices/inv-api-resolution/resolution/settlement-offers/{offer_id}/accept",
                json={"accepted_by": "Debtor Contact", "accepter_role": "DEBTOR"},
            )
            self.assertEqual(accept_debtor_resp.status_code, 200)
            self.assertFalse(accept_debtor_resp.json()["finalized"])
            self.assertEqual(accept_debtor_resp.json()["status"], "OPEN")

            accept_creditor_resp = client.post(
                f"/invoices/inv-api-resolution/resolution/settlement-offers/{offer_id}/accept",
                json={"accepted_by": "Creditor User", "accepter_role": "CREDITOR"},
            )
            self.assertEqual(accept_creditor_resp.status_code, 200)
            self.assertFalse(accept_creditor_resp.json()["finalized"])
            self.assertEqual(accept_creditor_resp.json()["status"], "AWAITING_PAYMENT")
            self.assertTrue(accept_creditor_resp.json()["chasers_paused"])

            blocked_settlement_escalate_resp = client.post(
                "/invoices/inv-api-resolution/escalate",
                json={"today": date.today().isoformat(), "current_state": "FORMAL_NOTICE"},
            )
            self.assertEqual(blocked_settlement_escalate_resp.status_code, 409)

            settlement_payment_report_resp = client.post(
                "/portal/actions/confirm-paid",
                json={
                    "case": verification_case["case_id"],
                    "code": verification_case["verification_code"],
                    "debtor_identifier": "debtor-resolution",
                    "amount_gbp": "750",
                    "payment_reference": "SETTLE-750",
                    "payment_date": settlement_payment_date.isoformat(),
                    "details": "Settlement payment sent.",
                    "settlement_offer_id": offer_id,
                },
            )
            self.assertEqual(settlement_payment_report_resp.status_code, 200)
            settlement_report_id = settlement_payment_report_resp.json()["report_id"]
            self.assertEqual(settlement_payment_report_resp.json()["status"], "PAYMENT_VERIFICATION_PENDING")
            self.assertEqual(settlement_payment_report_resp.json()["settlement_offer_id"], offer_id)

            settlement_confirm_resp = client.post(
                f"/invoices/inv-api-resolution/reported-payments/{settlement_report_id}/confirm",
                json={"creditor_user_id": "USER-1", "notes": "Settlement payment matched."},
            )
            self.assertEqual(settlement_confirm_resp.status_code, 200)
            self.assertEqual(settlement_confirm_resp.json()["settlement_offer_id"], offer_id)
            self.assertEqual(settlement_confirm_resp.json()["settlement_offer_status"], "FINALIZED")
            self.assertIsNotNone(settlement_confirm_resp.json()["settlement_offer_finalization_id"])
            self.assertEqual(settlement_confirm_resp.json()["outstanding_balance_gbp"], "0.00")

            settlement_artifact_resp = client.post(
                "/invoices/inv-api-resolution/resolution/artifacts/settlement-agreement",
                json={"offer_id": offer_id, "output_filename": "settlement-agreement.pdf"},
            )
            self.assertEqual(settlement_artifact_resp.status_code, 200)
            settlement_body = settlement_artifact_resp.json()
            self.assertEqual(settlement_body["artifact_type"], "FULL_AND_FINAL_SETTLEMENT")
            self.assertTrue(Path(settlement_body["artifact_path"]).exists())

            promise_artifacts_resp = client.get(
                "/invoices/inv-api-resolution/evidence-artifacts?artifact_type=PROMISE_TO_PAY&limit=10&offset=0"
            )
            self.assertEqual(promise_artifacts_resp.status_code, 200)
            self.assertGreaterEqual(promise_artifacts_resp.json()["count"], 1)
            settlement_artifacts_resp = client.get(
                "/invoices/inv-api-resolution/evidence-artifacts?artifact_type=FULL_AND_FINAL_SETTLEMENT&limit=10&offset=0"
            )
            self.assertEqual(settlement_artifacts_resp.status_code, 200)
            self.assertGreaterEqual(settlement_artifacts_resp.json()["count"], 1)

            offers_resp = client.get("/invoices/inv-api-resolution/resolution/settlement-offers")
            self.assertEqual(offers_resp.status_code, 200)
            self.assertEqual(offers_resp.json()["offers"][0]["status"], "FINALIZED")
            self.assertEqual(offers_resp.json()["offers"][0]["confirmed_payment_total_gbp"], "750.00")
            self.assertEqual(offers_resp.json()["offers"][0]["remaining_payment_gbp"], "0.00")

            carve_out_resp = client.post(
                "/invoices/inv-api-resolution/resolution/dispute-carve-outs",
                json={
                    "disputed_amount_gbp": "100",
                    "reason": "Partial quality dispute",
                    "created_by": "USER-1",
                },
            )
            self.assertEqual(carve_out_resp.status_code, 400)

            carve_outs_resp = client.get("/invoices/inv-api-resolution/resolution/dispute-carve-outs")
            self.assertEqual(carve_outs_resp.status_code, 200)
            self.assertEqual(len(carve_outs_resp.json()["carve_outs"]), 0)

            communication_resp = client.post(
                "/invoices/inv-api-resolution/communications",
                json={
                    "channel": "EMAIL",
                    "recipient": "ap@example.com",
                    "subject": "Resolution Update",
                    "body_summary": "Installment plan progress",
                    "automated": True,
                },
            )
            self.assertEqual(communication_resp.status_code, 409)

            open_challenge_resp = client.post(
                "/invoices/inv-api-resolution/debtor-actions/data-accuracy-challenge",
                json={
                    "debtor_identifier": "debtor-1",
                    "challenge_reason": "Incorrect address",
                    "challenge_details": "Registered office corrected",
                },
            )
            self.assertEqual(open_challenge_resp.status_code, 200)
            resolve_challenge_resp = client.post(
                "/invoices/inv-api-resolution/debtor-actions/data-accuracy-challenge/resolve",
                json={"creditor_user_id": "USER-1", "resolution_notes": "Address corrected and confirmed"},
            )
            self.assertEqual(resolve_challenge_resp.status_code, 200)

            bundle_resp = client.post(
                "/invoices/inv-api-resolution/evidence-bundles",
                json={
                    "communications": ["Resolution update"],
                    "formal_notices": ["Procedural notice"],
                    "include_resolution_artifacts": True,
                    "output_filename": "resolution_bundle.pdf",
                },
            )
            self.assertEqual(bundle_resp.status_code, 200)
            bundle_path = Path(bundle_resp.json()["bundle_path"])
            self.assertTrue(bundle_path.exists())
            bundle_bytes = bundle_path.read_bytes()
            self.assertIn(b"Communication Delivery Timeline:", bundle_bytes)
            self.assertIn(b"Correction and Withdrawal Notices:", bundle_bytes)
            self.assertIn(b"DATA_ACCURACY_CHALLENGE_OPEN", bundle_bytes)
            self.assertIn(b"Evidence Artifact Inventory:", bundle_bytes)
            self.assertIn(b"Compliance Snapshot:", bundle_bytes)
            self.assertIn(b"Event Chain Attestation:", bundle_bytes)

    def test_dispute_carve_out_endpoint_on_positive_outstanding_balance(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-carve-out.db")
            app = create_app(
                db_path=db_path,
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-carve-out",
                    "currency": "GBP",
                    "principal_amount": "1000",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            carve_out_resp = client.post(
                "/invoices/inv-api-carve-out/resolution/dispute-carve-outs",
                json={
                    "disputed_amount_gbp": "100",
                    "reason": "Partial quality dispute",
                    "created_by": "USER-1",
                },
            )
            self.assertEqual(carve_out_resp.status_code, 200)
            self.assertEqual(carve_out_resp.json()["suggested_state"], "DISPUTE_REVIEW")

            carve_outs_resp = client.get("/invoices/inv-api-carve-out/resolution/dispute-carve-outs")
            self.assertEqual(carve_outs_resp.status_code, 200)
            self.assertEqual(len(carve_outs_resp.json()["carve_outs"]), 1)

    def test_public_verification_pages_and_bundle_download(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-public.db")
            app = create_app(db_path=db_path, artifacts_dir=str(Path(tmp_dir) / "artifacts"), bundles_dir=str(Path(tmp_dir) / "bundles"))
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-public-portal",
                    "currency": "GBP",
                    "principal_amount": "1500",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            register_resp = client.post(
                "/invoices/inv-public-portal/debtor-verification/register",
                json={"creditor_name": "First Cairn Digital Client Ltd", "invoice_reference": "INV-PORTAL-1"},
            )
            self.assertEqual(register_resp.status_code, 200)
            case_id = register_resp.json()["case_id"]
            code = register_resp.json()["verification_code"]

            verify_html = client.get(f"/verify?case={case_id}&code={code}", headers={"Accept": "text/html"})
            self.assertEqual(verify_html.status_code, 200)
            self.assertIn("First Cairn Digital case verification", verify_html.text)
            self.assertIn("genuine", verify_html.text.lower())
            self.assertIn(f"/portal?case={case_id}&code={code}", verify_html.text)

            approval_resp = client.post(
                "/invoices/inv-public-portal/settlement-bank-details/approvals",
                headers={"x-api-key": "approver-key"},
                json={
                    "approval_reference": "APPROVAL-REF-2",
                    "approval_method": "AUTHENTICATED_ADMIN_APPROVAL",
                    "notes": "Verified for public portal bank details.",
                },
            )
            self.assertEqual(approval_resp.status_code, 200)

            bank_update_resp = client.post(
                "/invoices/inv-public-portal/settlement-bank-details",
                headers={"x-api-key": "requester-key"},
                json={
                    "updated_by": "USER-1",
                    "account_holder_name": "First Cairn Digital Client Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "dual_control_approval_reference": "APPROVAL-REF-2",
                },
            )
            self.assertEqual(bank_update_resp.status_code, 200)

            portal_html = client.get(f"/portal?case={case_id}&code={code}", headers={"Accept": "text/html"})
            self.assertEqual(portal_html.status_code, 200)
            self.assertIn("Debtor verification portal", portal_html.text)
            self.assertIn("Source of data", portal_html.text)
            self.assertIn("Case status", portal_html.text)
            self.assertIn("Recent recorded portal activity", portal_html.text)
            self.assertIn("/portal/actions/confirm-payment-date", portal_html.text)
            self.assertIn("Business Debtline", portal_html.text)
            self.assertIn(f"/portal/payment-link?case={case_id}&amp;code={code}", portal_html.text)

            portal_json = client.get(f"/portal?case={case_id}&code={code}")
            self.assertEqual(portal_json.status_code, 200)
            self.assertEqual(portal_json.json()["outstanding_balance_gbp"], "1500.00")
            self.assertIn("DEBTOR_VERIFICATION_REGISTERED", [item["event_type"] for item in portal_json.json()["recent_activity"]])
            self.assertTrue(portal_json.json()["settlement_destination_available"])

            payment_link_resp = client.get(f"/portal/payment-link?case={case_id}&code={code}", headers={"Accept": "text/html"})
            self.assertEqual(payment_link_resp.status_code, 200)
            self.assertIn("Verified settlement destination", payment_link_resp.text)
            self.assertIn("does not take payment", payment_link_resp.text)

            bundle_resp = client.get(
                "/invoices/inv-public-portal/evidence-bundle",
                params={"output_filename": "portal_bundle.pdf"},
            )
            self.assertEqual(bundle_resp.status_code, 200)
            self.assertEqual(bundle_resp.headers["content-type"].split(";", 1)[0], "application/pdf")
            self.assertGreater(len(bundle_resp.content), 200)

    def test_humane_pause_and_client_handoff_workflows(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-humane-handoff.db")
            app = create_app(db_path=db_path, artifacts_dir=str(Path(tmp_dir) / "artifacts"), bundles_dir=str(Path(tmp_dir) / "bundles"))
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-humane-handoff",
                    "currency": "GBP",
                    "principal_amount": "6000",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "SCOTLAND",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            case_health_resp = client.post(
                "/invoices/inv-humane-handoff/case-health-check",
                json={
                    "user_id": "USER-102",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )
            self.assertEqual(case_health_resp.status_code, 200)

            humane_open_resp = client.post(
                "/invoices/inv-humane-handoff/humane-pauses/open",
                json={
                    "opened_by": "USER-7",
                    "concern_type": "VULNERABILITY_NOTICE",
                    "summary": "Debtor contact suggested a welfare concern and requested reduced contact.",
                    "notes": "Record summary only.",
                    "review_due_date": "2026-02-15",
                    "sensitive_details_present": True,
                },
            )
            self.assertEqual(humane_open_resp.status_code, 200)
            self.assertTrue(humane_open_resp.json()["chasers_paused"])

            governance_resp = client.get("/invoices/inv-humane-handoff/governance-summary")
            self.assertEqual(governance_resp.status_code, 200)
            self.assertTrue(governance_resp.json()["restricted"])
            self.assertIn("HUMANE_PAUSE", governance_resp.json()["restriction_codes"])

            escalate_resp = client.post(
                "/invoices/inv-humane-handoff/escalate",
                json={"today": "2026-02-01", "current_state": "FORMAL_NOTICE"},
            )
            self.assertEqual(escalate_resp.status_code, 409)
            self.assertIn("humane pause", escalate_resp.json()["detail"].lower())

            handoff_resp = client.get("/invoices/inv-humane-handoff/client-handoff")
            self.assertEqual(handoff_resp.status_code, 200)
            self.assertTrue(handoff_resp.json()["eligible_for_handoff"])
            self.assertEqual(handoff_resp.json()["destination_label"], "Ordinary Cause / Scottish Solicitor review")
            self.assertIn("Formal Notice", handoff_resp.json()["required_documents"])

            handoff_review_resp = client.post(
                "/invoices/inv-humane-handoff/client-handoff/review",
                json={"reviewed_by": "USER-7", "ready_to_export": True, "notes": "Ready for client decision."},
            )
            self.assertEqual(handoff_review_resp.status_code, 200)
            self.assertEqual(handoff_review_resp.json()["latest_review"]["reviewed_by"], "USER-7")

            humane_release_resp = client.post(
                "/invoices/inv-humane-handoff/humane-pauses/release",
                json={"released_by": "USER-7", "release_reason": "CREDITOR_REVIEW_COMPLETE", "resolution_notes": "Manual review complete."},
            )
            self.assertEqual(humane_release_resp.status_code, 200)
            self.assertFalse(humane_release_resp.json()["governance"]["restricted"])

    def test_company_status_pause_and_restricted_note_workflows(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-phase-f.db")
            app = create_app(db_path=db_path, artifacts_dir=str(Path(tmp_dir) / "artifacts"), bundles_dir=str(Path(tmp_dir) / "bundles"))
            client = TestClient(app)

            client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-phase-f",
                    "currency": "GBP",
                    "principal_amount": "4800",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            client.post(
                "/invoices/inv-phase-f/case-health-check",
                json={
                    "user_id": "USER-9",
                    "correct_customer_legal_entity": True,
                    "description_of_goods_or_services": True,
                    "invoice_number_and_date_verified": True,
                    "amount_matches_contract_or_quote": True,
                    "correct_billing_address": True,
                    "vat_numbers_checked": True,
                    "purchase_order_supplied_if_required": True,
                    "payment_terms_and_due_date_established": True,
                    "delivery_or_acceptance_proof_attached": True,
                    "no_unresolved_credit_notes": True,
                    "direct_payments_checked": True,
                    "no_known_dispute": True,
                    "creditor_authority_verified": True,
                    "limitation_period_checked": True,
                    "debtor_contact_details_verified": True,
                    "court_handoff_boundary_acknowledged": True,
                },
            )

            company_status_resp = client.post(
                "/invoices/inv-phase-f/company-status-checks",
                json={
                    "checked_by": "USER-9",
                    "company_status": "INSOLVENT",
                    "source": "COMPANIES_HOUSE",
                    "company_number": "12345678",
                    "evidence_summary": "Company register shows insolvency marker.",
                    "official_register_url": "https://find-and-update.company-information.service.gov.uk/company/12345678",
                },
            )
            self.assertEqual(company_status_resp.status_code, 200)
            check_id = company_status_resp.json()["check_id"]

            company_status_list = client.get("/invoices/inv-phase-f/company-status-checks")
            self.assertEqual(company_status_list.status_code, 200)
            self.assertEqual(company_status_list.json()["latest"]["company_status"], "INSOLVENT")

            viability_resp = client.post(
                "/invoices/inv-phase-f/viability-proportionality-assessments",
                json={"on_date": "2026-02-05"},
            )
            self.assertEqual(viability_resp.status_code, 200)
            self.assertEqual(viability_resp.json()["company_status"], "INSOLVENT")
            self.assertEqual(viability_resp.json()["company_status_source"], "persisted_check")
            self.assertTrue(viability_resp.json()["blocked"])

            insolvency_open_resp = client.post(
                "/invoices/inv-phase-f/insolvency-reviews/open",
                json={
                    "opened_by": "USER-9",
                    "source": "COMPANIES_HOUSE",
                    "reason": "Register indicates insolvency review is required.",
                    "company_status_check_id": check_id,
                },
            )
            self.assertEqual(insolvency_open_resp.status_code, 200)
            self.assertTrue(insolvency_open_resp.json()["governance"]["handoff_required"])
            self.assertIn("INSOLVENCY_REVIEW", insolvency_open_resp.json()["governance"]["restriction_codes"])

            blocked_insolvency_escalate = client.post(
                "/invoices/inv-phase-f/escalate",
                json={"today": "2026-02-06", "current_state": "CLIENT_HANDOFF"},
            )
            self.assertEqual(blocked_insolvency_escalate.status_code, 409)

            insolvency_release_resp = client.post(
                "/invoices/inv-phase-f/insolvency-reviews/release",
                json={
                    "released_by": "USER-9",
                    "release_reason": "False positive resolved.",
                    "resume_state": "OVERDUE_CHASER",
                },
            )
            self.assertEqual(insolvency_release_resp.status_code, 200)
            self.assertFalse(insolvency_release_resp.json()["governance"]["handoff_required"])

            breathing_open_resp = client.post(
                "/invoices/inv-phase-f/breathing-space/open",
                json={
                    "opened_by": "USER-9",
                    "source": "DEBT_ADVICE_PROVIDER",
                    "reason": "Protected breathing space period active.",
                    "reference": "BS-REF-1",
                    "start_date": "2026-02-07",
                    "expected_end_date": "2026-03-07",
                },
            )
            self.assertEqual(breathing_open_resp.status_code, 200)
            self.assertIn("BREATHING_SPACE", breathing_open_resp.json()["governance"]["restriction_codes"])

            blocked_breathing_escalate = client.post(
                "/invoices/inv-phase-f/escalate",
                json={"today": "2026-02-10", "current_state": "BREATHING_SPACE_PAUSE"},
            )
            self.assertEqual(blocked_breathing_escalate.status_code, 409)

            breathing_release_resp = client.post(
                "/invoices/inv-phase-f/breathing-space/release",
                json={
                    "released_by": "USER-9",
                    "release_reason": "Protected period ended.",
                    "resume_state": "OVERDUE_CHASER",
                },
            )
            self.assertEqual(breathing_release_resp.status_code, 200)
            self.assertNotIn("BREATHING_SPACE", breathing_release_resp.json()["governance"]["restriction_codes"])

            humane_open_resp = client.post(
                "/invoices/inv-phase-f/humane-pauses/open",
                json={
                    "opened_by": "USER-9",
                    "concern_type": "VULNERABILITY_NOTICE",
                    "summary": "Store a summary only in the workflow ledger.",
                    "notes": "Operator summary for workflow.",
                    "sensitive_details_present": True,
                    "sensitive_details": "Detailed sensitive welfare information.",
                },
            )
            self.assertEqual(humane_open_resp.status_code, 200)
            self.assertIsNotNone(humane_open_resp.json()["restricted_note_id"])

            restricted_notes_resp = client.get("/invoices/inv-phase-f/restricted-notes", params={"viewer_id": "USER-9"})
            self.assertEqual(restricted_notes_resp.status_code, 200)
            self.assertEqual(restricted_notes_resp.json()["count"], 1)
            self.assertEqual(restricted_notes_resp.json()["notes"][0]["related_event_type"], "HUMANE_PAUSE_OPENED")

            governance_resp = client.get("/invoices/inv-phase-f/governance-summary")
            self.assertEqual(governance_resp.status_code, 200)
            self.assertEqual(governance_resp.json()["restricted_note_count"], 1)
            self.assertNotIn("Detailed sensitive welfare information.", str(governance_resp.json()["humane_pause"]["opened"]))

            audit_resp = client.get("/invoices/inv-phase-f/audit-trail")
            self.assertEqual(audit_resp.status_code, 200)
            self.assertIn("RESTRICTED_CASE_NOTES_ACCESSED", [entry["action"] for entry in audit_resp.json()["entries"]])

    def test_health_and_production_readiness_aliases(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-health.db")
            app = create_app(db_path=db_path, artifacts_dir=str(Path(tmp_dir) / "artifacts"), bundles_dir=str(Path(tmp_dir) / "bundles"))
            client = TestClient(app)
            self.assertEqual(client.get("/health").status_code, 200)
            self.assertEqual(client.get("/health/liveness").status_code, 200)
            readiness = client.get("/health/readiness")
            self.assertIn(readiness.status_code, {200, 503})
            self.assertIn("status", readiness.json())

    def test_validate_production_config(self) -> None:
        valid = validate_production_config(
            {
                "DATABASE_URL": "postgresql://user:pass@example.com:5432/app?sslmode=require",
                "SBC_API_KEY": "sbc-key-123",
                "FCD_API_CLIENTS": "legacy-credential:CLIENT-LEGACY",
                "SBC_ENDPOINT": "https://sbc.example.com",
                "CRYPTO_SIGNING_KEY": "A" * 32,
                "DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
            }
        )
        self.assertTrue(valid["valid"])

        invalid = validate_production_config({})
        self.assertFalse(invalid["valid"])
        self.assertIn("FCD_MANIFEST_SIGNING_KEY", "\n".join(invalid["errors"]))

    def test_validate_production_config_with_fcd_env_names(self) -> None:
        valid = validate_production_config(
            {
                "FCD_APP_ENV": "production",
                "FCD_MANIFEST_SIGNING_KEY": "A" * 32,
                "FCD_MANIFEST_KEY_ID": "fcd-kms-key-1",
                "FCD_MANIFEST_VERIFY_KEYS": "fcd-kms-key-1:" + ("B" * 32),
                "FCD_API_KEYS": "admin-key:admin,ops-key:operator,ro-key:viewer",
                "FCD_API_CLIENTS": "admin-key:FCD-ADMIN,ops-key:CLIENT-OPS,ro-key:CLIENT-RO",
                "FCD_RATE_LIMIT_PER_MINUTE": "120",
                "FCD_AUTH_FAILURE_ALERT_THRESHOLD": "10",
                "FCD_RATE_LIMIT_ALERT_THRESHOLD": "10",
                "FCD_SERVER_ERROR_ALERT_THRESHOLD": "5",
                "FCD_MAX_UPLOAD_BYTES": "5242880",
                "FCD_ALLOWED_UPLOAD_CONTENT_TYPES": "application/pdf,text/plain",
                "FCD_ALLOWED_UPLOAD_EXTENSIONS": ".pdf,.txt",
                "FCD_QUARANTINE_DIR": "data/quarantine",
                "FCD_DATA_RETENTION_DAYS": "2190",
                "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
            }
        )
        self.assertTrue(valid["valid"])
        self.assertEqual(valid["manifest_key_id"], "fcd-kms-key-1")
        self.assertEqual(valid["data_retention_cron_schedule"], "0 2 * * *")

    def test_validate_production_config_prefers_canonical_over_legacy_aliases(self) -> None:
        config = validate_production_config(
            {
                "FCD_APP_ENV": "production",
                "FCD_MANIFEST_SIGNING_KEY": "C" * 32,
                "CRYPTO_SIGNING_KEY": "LEGACY-SECRET",
                "FCD_MANIFEST_KEY_ID": "fcd-kms-key-1",
                "FCD_API_KEYS": "admin-key:admin",
                "FCD_API_CLIENTS": "admin-key:FCD-ADMIN",
                "SBC_API_KEY": "legacy-key",
                "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
                "DATA_RETENTION_CRON_SCHEDULE": "0 3 * * *",
                "FCD_RATE_LIMIT_PER_MINUTE": "60",
                "FCD_AUTH_FAILURE_ALERT_THRESHOLD": "8",
                "FCD_RATE_LIMIT_ALERT_THRESHOLD": "6",
                "FCD_SERVER_ERROR_ALERT_THRESHOLD": "4",
                "FCD_MAX_UPLOAD_BYTES": "1048576",
                "FCD_ALLOWED_UPLOAD_CONTENT_TYPES": "application/pdf",
                "FCD_ALLOWED_UPLOAD_EXTENSIONS": ".pdf",
                "FCD_QUARANTINE_DIR": "data/quarantine",
                "FCD_DATA_RETENTION_DAYS": "365",
            }
        )
        self.assertTrue(config["valid"])
        self.assertEqual(config["crypto_signing_key_present"], True)
        self.assertEqual(config["data_retention_cron_schedule"], "0 2 * * *")
        warning_text = "\n".join(config["warnings"])
        self.assertIn("legacy alias", warning_text)
        self.assertIn("FCD_API_KEYS", warning_text)
        self.assertIn("FCD_DATA_RETENTION_CRON_SCHEDULE", warning_text)

    def test_validate_production_config_rejects_incomplete_or_stale_client_mappings(self) -> None:
        missing_mapping = validate_production_config(
            {
                "FCD_APP_ENV": "production",
                "FCD_MANIFEST_SIGNING_KEY": "A" * 32,
                "FCD_MANIFEST_KEY_ID": "fcd-kms-key-1",
                "FCD_API_KEYS": "admin-key:admin,ops-key:operator",
                "FCD_API_CLIENTS": "admin-key:FCD-ADMIN",
                "FCD_RATE_LIMIT_PER_MINUTE": "120",
                "FCD_AUTH_FAILURE_ALERT_THRESHOLD": "10",
                "FCD_RATE_LIMIT_ALERT_THRESHOLD": "10",
                "FCD_SERVER_ERROR_ALERT_THRESHOLD": "5",
                "FCD_MAX_UPLOAD_BYTES": "5242880",
                "FCD_ALLOWED_UPLOAD_CONTENT_TYPES": "application/pdf,text/plain",
                "FCD_ALLOWED_UPLOAD_EXTENSIONS": ".pdf,.txt",
                "FCD_QUARANTINE_DIR": "data/quarantine",
                "FCD_DATA_RETENTION_DAYS": "2190",
                "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
            }
        )
        self.assertFalse(missing_mapping["valid"])
        self.assertIn("lack an explicit client mapping", "\n".join(missing_mapping["errors"]))

        stale_mapping = validate_production_config(
            {
                "FCD_APP_ENV": "production",
                "FCD_MANIFEST_SIGNING_KEY": "A" * 32,
                "FCD_MANIFEST_KEY_ID": "fcd-kms-key-1",
                "FCD_API_KEYS": "admin-key:admin",
                "FCD_API_CLIENTS": "admin-key:FCD-ADMIN,stale-key:CLIENT-B",
                "FCD_RATE_LIMIT_PER_MINUTE": "120",
                "FCD_AUTH_FAILURE_ALERT_THRESHOLD": "10",
                "FCD_RATE_LIMIT_ALERT_THRESHOLD": "10",
                "FCD_SERVER_ERROR_ALERT_THRESHOLD": "5",
                "FCD_MAX_UPLOAD_BYTES": "5242880",
                "FCD_ALLOWED_UPLOAD_CONTENT_TYPES": "application/pdf,text/plain",
                "FCD_ALLOWED_UPLOAD_EXTENSIONS": ".pdf,.txt",
                "FCD_QUARANTINE_DIR": "data/quarantine",
                "FCD_DATA_RETENTION_DAYS": "2190",
                "FCD_DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
            }
        )
        self.assertFalse(stale_mapping["valid"])
        self.assertIn("do not match configured API credentials", "\n".join(stale_mapping["errors"]))

    def test_ready_report_uses_runtime_configuration_without_exposing_secrets(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            previous_schedule = os.environ.get("FCD_DATA_RETENTION_CRON_SCHEDULE")
            os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = "0 2 * * *"
            try:
                db_path = str(Path(tmp_dir) / "api-config-ready.db")
                app = create_app(
                    db_path=db_path,
                    artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                    bundles_dir=str(Path(tmp_dir) / "bundles"),
                    manifest_signing_key="A" * 32,
                    manifest_key_id="fcd-ready-key",
                    auth_enabled=True,
                    api_keys={"admin-key": "admin"},
                    api_clients={"admin-key": "FCD-ADMIN"},
                    rate_limit_per_minute=77,
                    max_upload_bytes=4321,
                    allowed_upload_content_types=("application/pdf",),
                    allowed_upload_extensions=(".pdf",),
                    quarantine_dir=str(Path(tmp_dir) / "quarantine"),
                    app_env="production",
                )
                ready = TestClient(app).get("/ready")
            finally:
                if previous_schedule is None:
                    os.environ.pop("FCD_DATA_RETENTION_CRON_SCHEDULE", None)
                else:
                    os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = previous_schedule
            self.assertEqual(ready.status_code, 200)
            payload = ready.json()
            self.assertEqual(payload["manifest_key_id"], "fcd-ready-key")
            self.assertEqual(payload["api_client_mapping_count"], 1)
            self.assertEqual(payload["rate_limit_per_minute"], 77)
            self.assertEqual(payload["max_upload_bytes"], 4321)
            self.assertNotIn("A" * 32, str(payload))
            self.assertNotIn("manifest_signing_key", str(payload))
            self.assertNotIn("admin-key", str(payload))

    def test_development_auth_retains_default_client_compatibility(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_app(
                db_path=str(Path(tmp_dir) / "api-dev-client-map.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
                app_env="development",
                auth_enabled=True,
                api_keys={"operator-key": "operator"},
                rate_limit_per_minute=100,
            )
            client = TestClient(app)
            create_resp = client.post(
                "/invoices",
                headers={"x-api-key": "operator-key"},
                json={
                    "invoice_id": "inv-dev-client-map",
                    "currency": "GBP",
                    "principal_amount": "100",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

    def test_data_retention_disposal_partial_failure_is_audited_and_retryable(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-retention-partial.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            client = TestClient(app)

            create_resp = client.post(
                "/invoices",
                json={
                    "invoice_id": "inv-api-retention-partial",
                    "currency": "GBP",
                    "principal_amount": "150",
                    "issue_date": "2026-01-01",
                    "due_date": "2026-01-31",
                    "jurisdiction": "ENGLAND_WALES",
                    "debtor_type": "LIMITED",
                },
            )
            self.assertEqual(create_resp.status_code, 200)

            first_upload = client.post(
                "/invoices/inv-api-retention-partial/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract-a.txt", b"first file", "text/plain")},
            )
            second_upload = client.post(
                "/invoices/inv-api-retention-partial/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "INVOICE"},
                files={"file": ("contract-b.txt", b"second file", "text/plain")},
            )
            self.assertEqual(first_upload.status_code, 200)
            self.assertEqual(second_upload.status_code, 200)

            artifact_paths = [
                Path(first_upload.json()["file_path"]),
                Path(second_upload.json()["file_path"]),
            ]
            self.assertTrue(artifact_paths[0].exists())
            self.assertTrue(artifact_paths[1].exists())

            original_unlink = Path.unlink

            def fail_second_delete(path_obj: Path, *args, **kwargs):
                if str(path_obj) == str(artifact_paths[1]):
                    raise OSError("simulated filesystem deletion failure")
                return original_unlink(path_obj, *args, **kwargs)

            with patch("pathlib.Path.unlink", autospec=True, side_effect=lambda self, *args, **kwargs: fail_second_delete(self, *args, **kwargs)):
                partial_resp = client.post(
                    "/invoices/inv-api-retention-partial/data-retention-disposals",
                    json={"approved_by": "USER-1", "reason": "Scheduled retention cleanup", "as_of_date": "2035-01-01"},
                )
            self.assertEqual(partial_resp.status_code, 200)
            self.assertEqual(partial_resp.json()["status"], "PARTIAL_FAILURE")
            self.assertEqual(partial_resp.json()["deleted_file_count"], 1)
            self.assertEqual(partial_resp.json()["failed_file_count"], 1)
            self.assertEqual(partial_resp.json()["remaining_paths"], [str(artifact_paths[1])])
            self.assertTrue(artifact_paths[1].exists())

            compliance_resp = client.get("/invoices/inv-api-retention-partial/compliance-ledger")
            self.assertEqual(compliance_resp.status_code, 200)
            events = compliance_resp.json()["entries"]
            event_types = {entry["event_type"] for entry in events}
            self.assertIn("DATA_RETENTION_DISPOSAL_PARTIAL_FAILURE", event_types)
            self.assertNotIn("DATA_RETENTION_DISPOSAL_EXECUTED", event_types)
            partial_event = next(item for item in events if item["event_type"] == "DATA_RETENTION_DISPOSAL_PARTIAL_FAILURE")
            self.assertEqual(partial_event["details"]["status"], "PARTIAL_FAILURE")
            self.assertEqual(partial_event["details"]["remaining_paths"], [str(artifact_paths[1])])

            retry_resp = client.post(
                "/invoices/inv-api-retention-partial/data-retention-disposals",
                json={"approved_by": "USER-1", "reason": "Retry remaining files", "as_of_date": "2035-01-01"},
            )
            self.assertEqual(retry_resp.status_code, 200)
            self.assertEqual(retry_resp.json()["status"], "SUCCESS")
            self.assertEqual(retry_resp.json()["deleted_file_count"], 1)
            self.assertEqual(retry_resp.json()["failed_file_count"], 0)
            self.assertFalse(artifact_paths[1].exists())

    def test_startup_report_exposes_retention_schedule(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "api-health-schedule.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            original_schedule = os.environ.get("FCD_DATA_RETENTION_CRON_SCHEDULE")
            try:
                os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = "0 2 * * *"
                app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            finally:
                if original_schedule is None:
                    os.environ.pop("FCD_DATA_RETENTION_CRON_SCHEDULE", None)
                else:
                    os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = original_schedule
            client = TestClient(app)
            report = client.get("/deployment/startup-config-validation/report")
            self.assertEqual(report.status_code, 200)
            self.assertEqual(report.json()["data_retention_cron_schedule"], "0 2 * * *")


if __name__ == "__main__":
    unittest.main()
