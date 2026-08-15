from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import (
    PaymentPlanAgreement,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    SettlementAcceptance,
    SettlementOffer,
)
from unpaid_invoice_escalator.services.resolution_artifact_generator import ResolutionArtifactGenerator


class TestResolutionArtifactGenerator(unittest.TestCase):
    def test_generate_artifacts(self) -> None:
        generator = ResolutionArtifactGenerator()
        now = datetime.now(timezone.utc)
        with TemporaryDirectory() as tmp_dir:
            plan = PaymentPlanAgreement(
                plan_id="plan-x",
                invoice_id="inv-x",
                created_at=now,
                proposed_by="USER-1",
                installment_amount_gbp=Decimal("100"),
                installment_count=2,
                first_due_date=date(2026, 2, 1),
                frequency_days=30,
            )
            installments = (
                PaymentPlanInstallment(
                    installment_id="i1",
                    plan_id=plan.plan_id,
                    invoice_id=plan.invoice_id,
                    due_date=date(2026, 2, 1),
                    amount_gbp=Decimal("100"),
                    sequence_number=1,
                ),
                PaymentPlanInstallment(
                    installment_id="i2",
                    plan_id=plan.plan_id,
                    invoice_id=plan.invoice_id,
                    due_date=date(2026, 3, 3),
                    amount_gbp=Decimal("100"),
                    sequence_number=2,
                ),
            )
            payments = (
                PaymentPlanPayment(
                    payment_id="p1",
                    plan_id=plan.plan_id,
                    installment_id="i1",
                    invoice_id=plan.invoice_id,
                    paid_at=now,
                    amount_gbp=Decimal("100"),
                    recorded_by="USER-1",
                ),
            )
            promise_path = generator.generate_promise_to_pay(
                agreement=plan,
                installments=installments,
                payments=payments,
                output_path=str(Path(tmp_dir) / "promise.pdf"),
            )
            self.assertTrue(Path(promise_path).exists())

            offer = SettlementOffer(
                offer_id="offer-x",
                invoice_id="inv-x",
                offered_at=now,
                offered_by="USER-1",
                offered_amount_gbp=Decimal("150"),
                expiry_date=date(2026, 4, 1),
            )
            acceptances = (
                SettlementAcceptance(
                    acceptance_id="a1",
                    offer_id=offer.offer_id,
                    invoice_id=offer.invoice_id,
                    accepted_at=now,
                    accepted_by="Debtor",
                    accepter_role="DEBTOR",
                ),
                SettlementAcceptance(
                    acceptance_id="a2",
                    offer_id=offer.offer_id,
                    invoice_id=offer.invoice_id,
                    accepted_at=now,
                    accepted_by="Creditor",
                    accepter_role="CREDITOR",
                ),
            )
            settlement_path = generator.generate_settlement_agreement(
                offer=offer,
                acceptances=acceptances,
                output_path=str(Path(tmp_dir) / "settlement.pdf"),
            )
            self.assertTrue(Path(settlement_path).exists())


if __name__ == "__main__":
    unittest.main()
