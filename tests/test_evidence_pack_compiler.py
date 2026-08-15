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
            self.assertTrue(any("Filing Portal: Make a Money Claim Online (MMCO)" in line for line in lines))
            self.assertTrue(any("Enforcement Route:" in line for line in lines))
            self.assertTrue(any("Contract Artifacts:" in line for line in lines))
            self.assertTrue(any("Communication Delivery Timeline:" in line for line in lines))
            self.assertTrue(any("Correction and Withdrawal Notices:" in line for line in lines))


if __name__ == "__main__":
    unittest.main()
