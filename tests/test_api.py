from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app


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
            self.assertIn("P26003 Commercial Invoice Recovery Assistant", home_resp.text)

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
            self.assertEqual(debtor_ledger_resp.json()["balance_gbp"], "12.50")
            client_ledger_resp = client.get("/invoices/inv-api-1/client-fee-ledger")
            self.assertEqual(client_ledger_resp.status_code, 200)
            self.assertEqual(client_ledger_resp.json()["balance_gbp"], "11.94")

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
                json={"entry_type": "ORIGINAL_PRINCIPAL", "amount_gbp": "250", "description": "Principal"},
            )
            client.post(
                "/invoices/inv-api-lock/debtor-ledger/entries",
                json={"entry_type": "PAYMENT_RECEIVED", "amount_gbp": "-250", "description": "Paid in full"},
            )
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

            debtor_resp = client.post(
                "/invoices/inv-api-resolution/debtor-ledger/entries",
                json={"entry_type": "ORIGINAL_PRINCIPAL", "amount_gbp": "1000", "description": "Initial principal"},
            )
            self.assertEqual(debtor_resp.status_code, 200)

            plan_resp = client.post(
                "/invoices/inv-api-resolution/resolution/payment-plans",
                json={
                    "proposed_by": "USER-1",
                    "installment_amount_gbp": "200",
                    "installment_count": 3,
                    "first_due_date": "2026-03-01",
                    "frequency_days": 30,
                    "notes": "Plan terms",
                },
            )
            self.assertEqual(plan_resp.status_code, 200)
            plan_body = plan_resp.json()
            plan_id = plan_body["plan_id"]

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

            plans_list_resp = client.get("/invoices/inv-api-resolution/resolution/payment-plans?as_of_date=2026-08-01")
            self.assertEqual(plans_list_resp.status_code, 200)
            self.assertEqual(plans_list_resp.json()["plans"][0]["status"], "DEFAULTED")

            resumed_escalate_resp = client.post(
                "/invoices/inv-api-resolution/escalate",
                json={"today": "2026-08-01", "current_state": "FRIENDLY_REMINDER"},
            )
            self.assertEqual(resumed_escalate_resp.status_code, 200)
            self.assertEqual(resumed_escalate_resp.json()["next_state"], "FORMAL_NOTICE")

            offer_resp = client.post(
                "/invoices/inv-api-resolution/resolution/settlement-offers",
                json={
                    "offered_by": "USER-1",
                    "offered_amount_gbp": "750",
                    "expiry_date": "2026-09-15",
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

            accept_creditor_resp = client.post(
                f"/invoices/inv-api-resolution/resolution/settlement-offers/{offer_id}/accept",
                json={"accepted_by": "Creditor User", "accepter_role": "CREDITOR"},
            )
            self.assertEqual(accept_creditor_resp.status_code, 200)
            self.assertTrue(accept_creditor_resp.json()["finalized"])

            offers_resp = client.get("/invoices/inv-api-resolution/resolution/settlement-offers")
            self.assertEqual(offers_resp.status_code, 200)
            self.assertEqual(offers_resp.json()["offers"][0]["status"], "FINALIZED")

            carve_out_resp = client.post(
                "/invoices/inv-api-resolution/resolution/dispute-carve-outs",
                json={
                    "disputed_amount_gbp": "100",
                    "reason": "Partial quality dispute",
                    "created_by": "USER-1",
                },
            )
            self.assertEqual(carve_out_resp.status_code, 200)
            self.assertEqual(carve_out_resp.json()["suggested_state"], "DISPUTE_REVIEW")

            carve_outs_resp = client.get("/invoices/inv-api-resolution/resolution/dispute-carve-outs")
            self.assertEqual(carve_outs_resp.status_code, 200)
            self.assertEqual(len(carve_outs_resp.json()["carve_outs"]), 1)


if __name__ == "__main__":
    unittest.main()
