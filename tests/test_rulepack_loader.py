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

