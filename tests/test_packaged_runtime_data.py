# First Cairn Digital
# P26003 packaged runtime data regression check

from datetime import date
from importlib.resources import files
import unittest

from unpaid_invoice_escalator.models import Jurisdiction
from unpaid_invoice_escalator.rulepacks import RulePackLoader
from unpaid_invoice_escalator.rulepacks.fee_loader import FeePackLoader
from unpaid_invoice_escalator.services.base_rate_provider import BoEBaseRateProvider


class TestPackagedRuntimeData(unittest.TestCase):
    def test_required_runtime_data_is_packaged(self) -> None:
        package_root = files("unpaid_invoice_escalator")
        self.assertTrue(package_root.joinpath("reference_data/boe_base_rates.json").is_file())
        self.assertTrue(package_root.joinpath("rulepacks/packs/england_wales.v1.json").is_file())
        self.assertTrue(package_root.joinpath("rulepacks/fee_packs/court_fees.england_wales.v1.json").is_file())
        self.assertTrue(package_root.joinpath("rulepacks/fee_packs/pricing_schedule.v1_2_2026Q3.json").is_file())

    def test_runtime_data_loads_from_package(self) -> None:
        provider = BoEBaseRateProvider()
        self.assertGreater(len(provider._entries), 0)

        as_of = date(2026, 8, 15)
        rulepack = RulePackLoader().load_for(Jurisdiction.ENGLAND_WALES, as_of)
        self.assertEqual(rulepack.jurisdiction, Jurisdiction.ENGLAND_WALES)

        fee_schedule = FeePackLoader().load_court_fee_schedule(Jurisdiction.ENGLAND_WALES, as_of)
        self.assertEqual(fee_schedule.jurisdiction, Jurisdiction.ENGLAND_WALES)


if __name__ == "__main__":
    unittest.main()
