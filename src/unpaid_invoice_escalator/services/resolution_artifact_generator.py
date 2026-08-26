from __future__ import annotations

from datetime import datetime
from pathlib import Path

from unpaid_invoice_escalator.models import (
    PaymentPlanAgreement,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    SettlementAcceptance,
    SettlementOffer,
)
from unpaid_invoice_escalator.services.pdf_text_renderer import TextPdfRenderer


class ResolutionArtifactGenerator:
    def __init__(self) -> None:
        self._pdf_renderer = TextPdfRenderer()

    def generate_promise_to_pay(
        self,
        *,
        agreement: PaymentPlanAgreement,
        installments: tuple[PaymentPlanInstallment, ...],
        payments: tuple[PaymentPlanPayment, ...],
        output_path: str,
    ) -> str:
        paid_by_installment: dict[str, float] = {}
        for payment in payments:
            paid_by_installment[payment.installment_id] = paid_by_installment.get(payment.installment_id, 0.0) + float(
                payment.amount_gbp
            )
        lines = [
            "Promise to Pay Schedule",
            f"Plan ID: {agreement.plan_id}",
            f"Invoice ID: {agreement.invoice_id}",
            f"Proposed By: {agreement.proposed_by}",
            f"Created At: {agreement.created_at.isoformat()}",
            f"Installment Amount (GBP): {agreement.installment_amount_gbp}",
            f"Installment Count: {agreement.installment_count}",
            f"First Due Date: {agreement.first_due_date.isoformat()}",
            f"Frequency (days): {agreement.frequency_days}",
            "",
            "Installment Schedule:",
        ]
        for item in installments:
            paid = paid_by_installment.get(item.installment_id, 0.0)
            status = "PAID" if paid >= float(item.amount_gbp) else "DUE"
            lines.append(
                f"- #{item.sequence_number} | Due {item.due_date.isoformat()} | GBP {item.amount_gbp} | Status={status}"
            )
        lines.extend(
            [
                "",
                "Terms:",
                "- This schedule records a bilateral payment arrangement for invoice resolution.",
                "- If an installment is missed, escalation may resume from overdue procedures.",
                "- Parties retain rights to independent legal advice.",
            ]
        )
        return self._write_pdf(lines=lines, output_path=output_path)

    def generate_settlement_agreement(
        self,
        *,
        offer: SettlementOffer,
        acceptances: tuple[SettlementAcceptance, ...],
        output_path: str,
    ) -> str:
        lines = [
            "Full and Final Settlement Agreement",
            f"Offer ID: {offer.offer_id}",
            f"Invoice ID: {offer.invoice_id}",
            f"Offered By: {offer.offered_by}",
            f"Offered Amount (GBP): {offer.offered_amount_gbp}",
            f"Offer Date: {offer.offered_at.isoformat()}",
            f"Offer Expiry Date: {offer.expiry_date.isoformat()}",
            "",
            "Acceptance Record:",
        ]
        for acceptance in acceptances:
            lines.append(
                f"- {acceptance.accepter_role} accepted by {acceptance.accepted_by} at {acceptance.accepted_at.isoformat()}"
            )
        lines.extend(
            [
                "",
                "Terms:",
                "- On bilateral acceptance, this agreement records full and final settlement intent.",
                "- Payment and ledger adjustments are tracked in immutable audit records.",
                "- Parties retain rights to independent legal advice.",
            ]
        )
        return self._write_pdf(lines=lines, output_path=output_path)

    def _write_pdf(self, *, lines: list[str], output_path: str) -> str:
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        pdf_bytes = self._pdf_renderer.render(lines)
        output.write_bytes(pdf_bytes)
        return str(output)
