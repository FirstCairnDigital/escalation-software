#
# First Cairn Digital
# P26003 customer live shell and container runtime
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient

from unpaid_invoice_escalator.live_app import create_live_app


class TestLiveApp(unittest.TestCase):
    def test_public_home_contains_both_customer_journeys(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-home.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertIn("I am owed money", response.text)
            self.assertIn("I have received a notice", response.text)

    def test_public_home_does_not_link_to_internal_staff_surfaces(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-home-safe.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            response = client.get("/")

            self.assertEqual(response.status_code, 200)
            self.assertNotIn("/ui/operations", response.text)
            self.assertNotIn("/ui/compliance", response.text)
            self.assertNotIn("/metrics", response.text)
            self.assertNotIn("RBAC", response.text)

    def test_creditor_and_debtor_pages_render(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-pages.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            creditor = client.get("/creditor")
            debtor = client.get("/debtor")

            self.assertEqual(creditor.status_code, 200)
            self.assertIn("For creditors", creditor.text)
            self.assertEqual(debtor.status_code, 200)
            self.assertIn("Verify a notice", debtor.text)

    def test_debtor_form_targets_verify_with_required_fields(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-debtor-form.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            response = client.get("/debtor")

            self.assertEqual(response.status_code, 200)
            self.assertIn('form action="/verify" method="get"', response.text)
            self.assertIn('name="case"', response.text)
            self.assertIn('name="code"', response.text)

    def test_core_routes_remain_reachable_through_mount(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-core.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            health = client.get("/health")
            ready = client.get("/ready")
            dashboard = client.get("/ui/dashboard")

            self.assertEqual(health.status_code, 200)
            self.assertEqual(health.json()["status"], "ok")
            self.assertEqual(ready.status_code, 200)
            self.assertEqual(ready.json()["status"], "ready")
            self.assertEqual(dashboard.status_code, 200)
            self.assertIn("Engine Dashboard", dashboard.text)

    def test_public_shell_pages_include_security_headers(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-headers.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            for path in ("/", "/creditor", "/debtor"):
                response = client.get(path)
                self.assertEqual(response.headers.get("x-content-type-options"), "nosniff")
                self.assertEqual(response.headers.get("x-frame-options"), "DENY")
                self.assertEqual(response.headers.get("referrer-policy"), "no-referrer")
                self.assertEqual(response.headers.get("cache-control"), "public, max-age=300")

    def test_public_copy_does_not_expose_api_config_strings(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            app = create_live_app(
                db_path=str(Path(tmp_dir) / "live-copy.db"),
                artifacts_dir=str(Path(tmp_dir) / "artifacts"),
                bundles_dir=str(Path(tmp_dir) / "bundles"),
            )
            client = TestClient(app)

            combined = "\n".join(client.get(path).text for path in ("/", "/creditor", "/debtor"))

            self.assertNotIn("FCD_API_KEYS", combined)
            self.assertNotIn("FCD_API_CLIENTS", combined)
            self.assertNotIn("FCD_API_IDENTITIES", combined)
            self.assertNotIn("x-api-key", combined)
