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
            rule_resp = client.get("/rule-packs/NORTHERN_IRELAND/active?on_date=2026-02-01")
            self.assertEqual(rule_resp.status_code, 200)
            self.assertEqual(rule_resp.json()["rule_id"], "ni-commercial-invoice-recovery")

            escalate_resp = client.post(
                "/invoices/inv-api-1/escalate",
                json={"today": "2026-02-01", "current_state": "OVERDUE_CHASER"},
            )
            self.assertEqual(escalate_resp.status_code, 200)
            self.assertEqual(escalate_resp.json()["next_state"], "PRE_ACTION_PROTOCOL")

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

            artifacts_resp = client.get("/invoices/inv-api-1/evidence-artifacts")
            self.assertEqual(artifacts_resp.status_code, 200)
            artifacts_body = artifacts_resp.json()
            self.assertEqual(artifacts_body["count"], 2)
            self.assertEqual(artifacts_body["artifacts"][0]["artifact_type"], "CONTRACT")
            self.assertEqual(artifacts_body["artifacts"][1]["artifact_type"], "PROOF_OF_DELIVERY")

            events_resp = client.get("/invoices/inv-api-1/ledger-events?limit=5")
            self.assertEqual(events_resp.status_code, 200)
            events_body = events_resp.json()
            self.assertTrue(events_body["chain_valid"])
            self.assertGreaterEqual(events_body["count"], 1)

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


if __name__ == "__main__":
    unittest.main()
