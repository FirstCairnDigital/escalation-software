from datetime import date, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
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
            self.assertEqual(client.get("/ui/compliance").status_code, 200)
            reports_page = client.get("/ui/reports")
            self.assertEqual(reports_page.status_code, 200)
            self.assertIn("Environment checks", reports_page.text)
            self.assertIn("Policy controls", reports_page.text)

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
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "First Cairn Digital Client Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "mfa_reauthenticated": False,
                },
            )
            self.assertEqual(unauthorized_bank_update.status_code, 403)

            authorized_bank_update = client.post(
                "/invoices/inv-api-1/settlement-bank-details",
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "First Cairn Digital Client Ltd",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "dual_control_approved_by": "ADMIN-1",
                    "dual_control_approval_reference": "APPROVAL-REF-1",
                },
            )
            self.assertEqual(authorized_bank_update.status_code, 200)
            self.assertEqual(authorized_bank_update.json()["cop_state"], "COP_EXACT_MATCH")

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
                json={
                    "updated_by": "USER-102",
                    "account_holder_name": "Unexpected Name",
                    "sort_code": "12-34-56",
                    "account_number": "12345678",
                    "expected_payee_name": "First Cairn Digital Client Ltd",
                    "mfa_reauthenticated": True,
                },
            )
            self.assertEqual(failed_bank_update.status_code, 200)
            self.assertEqual(failed_bank_update.json()["cop_state"], "COP_FAILED")

            portal_with_failed_bank = client.get(
                f"/portal?case={verification_body['case_id']}&code={verification_body['verification_code']}"
            )
            self.assertEqual(portal_with_failed_bank.status_code, 200)
            self.assertFalse(portal_with_failed_bank.json()["settlement_destination_available"])

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

            upload_resp = client.post(
                "/invoices/inv-api-limit/evidence-artifacts",
                data={"user_id": "client-1", "artifact_type": "CONTRACT"},
                files={"file": ("contract.txt", b"123456789", "text/plain")},
            )
            self.assertEqual(upload_resp.status_code, 413)

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

            portal_html = client.get(f"/portal?case={case_id}&code={code}", headers={"Accept": "text/html"})
            self.assertEqual(portal_html.status_code, 200)
            self.assertIn("Debtor verification portal", portal_html.text)
            self.assertIn("Source of data", portal_html.text)

            bundle_resp = client.get(
                "/invoices/inv-public-portal/evidence-bundle",
                params={"output_filename": "portal_bundle.pdf"},
            )
            self.assertEqual(bundle_resp.status_code, 200)
            self.assertEqual(bundle_resp.headers["content-type"].split(";", 1)[0], "application/pdf")
            self.assertGreater(len(bundle_resp.content), 200)

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
                "SBC_ENDPOINT": "https://sbc.example.com",
                "CRYPTO_SIGNING_KEY": "A" * 32,
                "DATA_RETENTION_CRON_SCHEDULE": "0 2 * * *",
            }
        )
        self.assertTrue(valid["valid"])

        invalid = validate_production_config({})
        self.assertFalse(invalid["valid"])
        self.assertIn("DATABASE_URL", "\n".join(invalid["errors"]))


if __name__ == "__main__":
    unittest.main()
