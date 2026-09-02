import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import ClientFeeAction, Jurisdiction
from unpaid_invoice_escalator.rulepacks.fee_loader import FeePackLoader


class TestFeePackLoader(unittest.TestCase):
    def test_pricing_schedule_and_court_quote(self) -> None:
        loader = FeePackLoader()
        schedule = loader.load_pricing_schedule(date(2026, 8, 15))
        self.assertEqual(schedule.version, "v1.2-2026Q3")
        self.assertEqual(schedule.action_fees[ClientFeeAction.FORMAL_ESCALATION], Decimal("9.95"))

        fee_ew_mid = loader.quote_court_fee(Jurisdiction.ENGLAND_WALES, Decimal("1250"), date(2026, 8, 15))
        self.assertEqual(fee_ew_mid, Decimal("80"))
        fee_ew = loader.quote_court_fee(Jurisdiction.ENGLAND_WALES, Decimal("12000"), date(2026, 8, 15))
        self.assertEqual(fee_ew, Decimal("600.00"))
        fee_scotland = loader.quote_court_fee(Jurisdiction.SCOTLAND, Decimal("250"), date(2026, 8, 15))
        self.assertEqual(fee_scotland, Decimal("23"))

    def test_pricing_schedule_prefers_latest_valid_version(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            base = Path(tmp_dir)
            older = {
                "schedule_id": "older",
                "version": "v1",
                "effective_from": "2026-01-01",
                "effective_to": "2026-06-30",
                "source_reference": "old",
                "vat_rate": 0.20,
                "action_fees": {"FORMAL_ESCALATION": 10.00},
            }
            newer = {
                "schedule_id": "newer",
                "version": "v2",
                "effective_from": "2026-07-01",
                "effective_to": None,
                "source_reference": "new",
                "vat_rate": 0.20,
                "action_fees": {"FORMAL_ESCALATION": 12.00},
            }
            (base / "pricing_schedule_zzz_old.json").write_text(json.dumps(older), encoding="utf-8")
            (base / "pricing_schedule_aaa_new.json").write_text(json.dumps(newer), encoding="utf-8")

            loader = FeePackLoader(base_path=tmp_dir)
            schedule = loader.load_pricing_schedule(date(2026, 8, 1))
            self.assertEqual(schedule.schedule_id, "newer")
            self.assertEqual(schedule.action_fees[ClientFeeAction.FORMAL_ESCALATION], Decimal("12.00"))


if __name__ == "__main__":
    unittest.main()
