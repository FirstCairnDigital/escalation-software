from datetime import date
from decimal import Decimal
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.rulepacks.loader import RulePackLoader
from unpaid_invoice_escalator.services.communication_severity_engine import CommunicationSeverityEngine


class TestCommunicationSeverityEngine(unittest.TestCase):
    def test_generates_level_from_state(self) -> None:
        engine = CommunicationSeverityEngine()
        invoice = Invoice(
            invoice_id="inv-comms-1",
            currency="GBP",
            principal_amount=Decimal("1200"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        preview = engine.preview_for_state(
            invoice=invoice,
            state=InvoiceState.PRE_ACTION_PROTOCOL,
            on_date=date(2026, 2, 1),
            instructions="Protocol response window active.",
            wait_until=date(2026, 3, 1),
        )
        self.assertEqual(preview.level, 5)
        self.assertEqual(preview.stage_name, "Pre-Action Procedural Notice")
        self.assertIn("Pre-action procedural notice", preview.message)

    def test_guardrail_rewrites_banned_phrases(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            pack_dir = Path(tmp_dir)
            payload = {
                "rule_id": "ew-test",
                "jurisdiction": "ENGLAND_WALES",
                "rule_version": "1.0",
                "effective_from": "2020-01-01",
                "effective_to": None,
                "source_authority": "test",
                "source_reference": "test",
                "fcd_automation_limit": 10000,
                "human_approval_required": True,
                "workflow": {
                    "communication_templates": {
                        "LEVEL_2": "Final warning for Invoice {invoice_id}. This is your last chance countdown."
                    }
                },
            }
            (pack_dir / "ew.json").write_text(json.dumps(payload), encoding="utf-8")
            engine = CommunicationSeverityEngine(rule_pack_loader=RulePackLoader(base_path=str(pack_dir)))
            invoice = Invoice(
                invoice_id="inv-comms-2",
                currency="GBP",
                principal_amount=Decimal("999"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            preview = engine.preview_for_state(
                invoice=invoice,
                state=InvoiceState.OVERDUE_CHASER,
                on_date=date(2026, 2, 1),
                instructions="n/a",
                wait_until=None,
            )
            self.assertIn("formal notice", preview.message.lower())
            self.assertNotIn("final warning", preview.message.lower())
            self.assertGreaterEqual(len(preview.guardrail_flags), 1)


if __name__ == "__main__":
    unittest.main()
