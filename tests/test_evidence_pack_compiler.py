from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import DebtorType, Invoice, Jurisdiction
from unpaid_invoice_escalator.services.evidence_pack_compiler import EvidenceBundleInput, EvidencePackCompiler


class TestEvidencePackCompiler(unittest.TestCase):
    def test_compile_pdf_bundle(self) -> None:
        invoice = Invoice(
            invoice_id="inv-pack-1",
            currency="GBP",
            principal_amount=Decimal("1200"),
            issue_date=date(2026, 1, 5),
            due_date=date(2026, 2, 5),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
        )
        compiler = EvidencePackCompiler()
        with TemporaryDirectory() as tmp_dir:
            contract_path = Path(tmp_dir) / "contract.txt"
            contract_path.write_text("signed terms", encoding="utf-8")
            proof_path = Path(tmp_dir) / "proof.txt"
            proof_path.write_text("proof of supply", encoding="utf-8")
            output_path = Path(tmp_dir) / "bundle.pdf"
            bundle = EvidenceBundleInput(
                invoice=invoice,
                communications=("Reminder sent", "Formal notice sent"),
                contract_paths=(str(contract_path),),
                proof_of_supply_paths=(str(proof_path),),
                formal_notices=("14-day Letter Before Action",),
                ledger_events=(),
                generated_at=datetime.now(timezone.utc),
            )
            lines = compiler._bundle_lines(bundle)
            generated = compiler.compile_bundle(bundle, str(output_path))
            generated_path = Path(generated)
            self.assertTrue(generated_path.exists())
            content = generated_path.read_bytes()
            self.assertTrue(content.startswith(b"%PDF-1.4"))
            self.assertTrue(any("Handoff Destination: Money Claim Online / County Court" in line for line in lines))
            self.assertTrue(any("Enforcement Route:" in line for line in lines))
            self.assertTrue(any("Required Handoff Pack:" in line for line in lines))
            self.assertTrue(any("Contract Artifacts:" in line for line in lines))
            self.assertTrue(any("Communication Delivery Timeline:" in line for line in lines))
            self.assertTrue(any("Correction and Withdrawal Notices:" in line for line in lines))
            self.assertTrue(any("Evidence Artifact Inventory:" in line for line in lines))
            self.assertTrue(any("Compliance Snapshot:" in line for line in lines))
            self.assertTrue(any("Event Chain Attestation:" in line for line in lines))

    def test_compile_pdf_bundle_paginates_and_respects_over_limit_route(self) -> None:
        invoice = Invoice(
            invoice_id="inv-pack-over-limit",
            currency="GBP",
            principal_amount=Decimal("6000"),
            issue_date=date(2026, 1, 5),
            due_date=date(2026, 2, 5),
            jurisdiction=Jurisdiction.SCOTLAND,
            debtor_type=DebtorType.LIMITED,
        )
        compiler = EvidencePackCompiler()
        with TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "bundle-over-limit.pdf"
            bundle = EvidenceBundleInput(
                invoice=invoice,
                communications=tuple(f"Communication {index}" for index in range(80)),
                contract_paths=(),
                proof_of_supply_paths=(),
                formal_notices=("Formal Notice",),
                ledger_events=(),
                generated_at=datetime.now(timezone.utc),
                outstanding_amount_gbp=Decimal("6000"),
            )
            lines = compiler._bundle_lines(bundle)
            generated = compiler.compile_bundle(bundle, str(output_path))
            self.assertTrue(any("Handoff Destination: Ordinary Cause / Scottish Solicitor review" in line for line in lines))
            self.assertGreaterEqual(Path(generated).read_bytes().count(b"/Type /Page "), 2)


if __name__ == "__main__":
    unittest.main()
