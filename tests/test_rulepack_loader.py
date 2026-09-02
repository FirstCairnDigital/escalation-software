from datetime import date
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import Jurisdiction
from unpaid_invoice_escalator.rulepacks import RulePackLoader, RulePackValidationError


class TestRulePackLoader(unittest.TestCase):
    def test_describe_active_pack(self) -> None:
        loader = RulePackLoader()
        active = loader.describe_active(Jurisdiction.ENGLAND_WALES, date(2026, 2, 1))
        self.assertEqual(active["jurisdiction"], "ENGLAND_WALES")
        self.assertEqual(active["rule_id"], "ew-commercial-invoice-recovery")

    def test_resolves_latest_valid_pack_by_metadata_not_filename(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            older = {
                "rule_id": "older-pack",
                "jurisdiction": "ENGLAND_WALES",
                "rule_version": "2025.01",
                "effective_from": "2025-01-01",
                "effective_to": "2025-12-31",
                "source_authority": "test",
                "source_reference": "older",
                "fcd_automation_limit": 1000,
                "human_approval_required": True,
                "workflow": {"notes": "older"},
            }
            newer = {
                "rule_id": "newer-pack",
                "jurisdiction": "ENGLAND_WALES",
                "rule_version": "2026.01",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "newer",
                "fcd_automation_limit": 10000,
                "human_approval_required": True,
                "workflow": {"notes": "newer"},
            }
            (base / "zzz-last.json").write_text(json.dumps(older), encoding="utf-8")
            (base / "aaa-first.json").write_text(json.dumps(newer), encoding="utf-8")

            loader = RulePackLoader(base_path=tmp_dir)
            selected = loader.load_for(Jurisdiction.ENGLAND_WALES, date(2026, 2, 1))
            self.assertEqual(selected.rule_id, "newer-pack")
            self.assertEqual(selected.rule_version, "2026.01")

    def test_ignores_future_and_superseded_packs(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            future = {
                "rule_id": "future-pack",
                "jurisdiction": "SCOTLAND",
                "rule_version": "2027.01",
                "effective_from": "2027-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "future",
                "fcd_automation_limit": 5000,
                "human_approval_required": False,
                "workflow": {"notes": "future"},
            }
            current = {
                "rule_id": "current-pack",
                "jurisdiction": "SCOTLAND",
                "rule_version": "2026.01",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "current",
                "fcd_automation_limit": 5000,
                "human_approval_required": False,
                "workflow": {"notes": "current"},
            }
            (base / "future.json").write_text(json.dumps(future), encoding="utf-8")
            (base / "current.json").write_text(json.dumps(current), encoding="utf-8")

            loader = RulePackLoader(base_path=tmp_dir)
            selected = loader.load_for(Jurisdiction.SCOTLAND, date(2026, 6, 1))
            self.assertEqual(selected.rule_id, "current-pack")

    def test_overlapping_valid_packs_raise_ambiguity_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            pack_a = {
                "rule_id": "pack-a",
                "jurisdiction": "NORTHERN_IRELAND",
                "rule_version": "2026.01",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "a",
                "fcd_automation_limit": 5000,
                "human_approval_required": False,
                "workflow": {"notes": "a"},
            }
            pack_b = {
                "rule_id": "pack-b",
                "jurisdiction": "NORTHERN_IRELAND",
                "rule_version": "2026.01",
                "effective_from": "2026-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "b",
                "fcd_automation_limit": 6000,
                "human_approval_required": False,
                "workflow": {"notes": "b"},
            }
            (base / "a.json").write_text(json.dumps(pack_a), encoding="utf-8")
            (base / "b.json").write_text(json.dumps(pack_b), encoding="utf-8")

            loader = RulePackLoader(base_path=tmp_dir)
            with self.assertRaises(RulePackValidationError):
                loader.load_for(Jurisdiction.NORTHERN_IRELAND, date(2026, 2, 1))

    def test_invalid_pack_raises_validation_error(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            invalid_path = Path(tmp_dir) / "invalid.json"
            invalid_path.write_text(
                json.dumps(
                    {
                        "rule_id": "invalid",
                        "jurisdiction": "ENGLAND_WALES",
                        "rule_version": "1",
                        "effective_from": "2020-01-01",
                        "effective_to": None,
                        "source_authority": "test",
                        "source_reference": "test"
                    }
                ),
                encoding="utf-8",
            )
            loader = RulePackLoader(base_path=tmp_dir)
            with self.assertRaises(RulePackValidationError):
                loader.load_for(Jurisdiction.ENGLAND_WALES, date(2026, 2, 1))


if __name__ == "__main__":
    unittest.main()

