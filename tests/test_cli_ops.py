from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.api import create_app
from unpaid_invoice_escalator.cli import main as cli_main
from unpaid_invoice_escalator.ops_cli import run_admin_cli


class TestCliOps(unittest.TestCase):
    def test_legacy_cli_runner(self) -> None:
        stdout = StringIO()
        with redirect_stdout(stdout):
            exit_code = cli_main(
                [
                    "--invoice-id",
                    "inv-cli-1",
                    "--principal",
                    "1200",
                    "--issue-date",
                    "2026-01-01",
                    "--due-date",
                    "2026-01-31",
                    "--jurisdiction",
                    "ENGLAND_WALES",
                    "--debtor-type",
                    "LIMITED",
                    "--today",
                    "2026-02-15",
                ]
            )
        payload = json.loads(stdout.getvalue())
        self.assertEqual(exit_code, 0)
        self.assertEqual(payload["invoice_id"], "inv-cli-1")
        self.assertIn("next_state", payload)

    def test_admin_cli_workflows(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "ops-cli.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            app = create_app(db_path=db_path, artifacts_dir=artifacts_dir, bundles_dir=bundles_dir)
            with TestClient(app) as client:
                create_resp = client.post(
                    "/invoices",
                    json={
                        "invoice_id": "inv-cli-ops",
                        "currency": "GBP",
                        "principal_amount": "900",
                        "issue_date": "2026-01-01",
                        "due_date": "2026-01-31",
                        "jurisdiction": "ENGLAND_WALES",
                        "debtor_type": "LIMITED",
                    },
                )
                self.assertEqual(create_resp.status_code, 200)

            queue_stdout = StringIO()
            with redirect_stdout(queue_stdout):
                queue_exit = cli_main(
                    [
                        "retention-queue",
                        "--db-path",
                        db_path,
                        "--artifacts-dir",
                        artifacts_dir,
                        "--bundles-dir",
                        bundles_dir,
                    ]
                )
            queue_payload = json.loads(queue_stdout.getvalue())
            self.assertEqual(queue_exit, 0)
            self.assertEqual(queue_payload["summary"]["total_cases"], 1)
            self.assertEqual(queue_payload["items"][0]["invoice_id"], "inv-cli-ops")

            status_stdout = StringIO()
            with redirect_stdout(status_stdout):
                status_exit = run_admin_cli(
                    [
                        "company-status-check",
                        "--db-path",
                        db_path,
                        "--artifacts-dir",
                        artifacts_dir,
                        "--bundles-dir",
                        bundles_dir,
                        "--invoice-id",
                        "inv-cli-ops",
                        "--checked-by",
                        "USER-1",
                        "--company-status",
                        "ACTIVE",
                        "--source",
                        "COMPANIES_HOUSE",
                        "--evidence-summary",
                        "Register reviewed.",
                    ]
                )
            status_payload = json.loads(status_stdout.getvalue())
            self.assertEqual(status_exit, 0)
            self.assertEqual(status_payload["company_status"], "ACTIVE")
            self.assertEqual(status_payload["invoice_id"], "inv-cli-ops")

    def test_admin_cli_startup_config_report(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "ops-cli-ready.db")
            artifacts_dir = str(Path(tmp_dir) / "artifacts")
            bundles_dir = str(Path(tmp_dir) / "bundles")
            previous_schedule = os.environ.get("FCD_DATA_RETENTION_CRON_SCHEDULE")
            try:
                os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = "0 2 * * *"
                stdout = StringIO()
                with redirect_stdout(stdout):
                    exit_code = cli_main(
                        [
                            "startup-config-report",
                            "--db-path",
                            db_path,
                            "--artifacts-dir",
                            artifacts_dir,
                            "--bundles-dir",
                            bundles_dir,
                        ]
                    )
            finally:
                if previous_schedule is None:
                    os.environ.pop("FCD_DATA_RETENTION_CRON_SCHEDULE", None)
                else:
                    os.environ["FCD_DATA_RETENTION_CRON_SCHEDULE"] = previous_schedule
            payload = json.loads(stdout.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["data_retention_cron_schedule"], "0 2 * * *")
            self.assertIn("runbook", payload)


if __name__ == "__main__":
    unittest.main()
