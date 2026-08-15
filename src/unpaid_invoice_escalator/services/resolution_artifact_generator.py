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


class ResolutionArtifactGenerator:
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
        pdf_bytes = self._render_single_page_pdf(lines)
        output.write_bytes(pdf_bytes)
        return str(output)

    def _render_single_page_pdf(self, lines: list[str]) -> bytes:
        safe_lines = [self._escape_pdf_text(line) for line in lines]
        y_start = 780
        line_height = 14
        commands = ["BT", "/F1 11 Tf", f"72 {y_start} Td"]
        for i, line in enumerate(safe_lines):
            if i > 0:
                commands.append(f"0 -{line_height} Td")
            commands.append(f"({line}) Tj")
        commands.append("ET")
        stream = "\n".join(commands).encode("latin-1", errors="replace")

        objects: list[bytes] = []
        objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
        objects.append(b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>")
        objects.append(
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 595 842] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>"
        )
        objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")
        objects.append(f"<< /Length {len(stream)} >>\nstream\n".encode("latin-1") + stream + b"\nendstream")

        pdf = bytearray(b"%PDF-1.4\n")
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(pdf))
            pdf.extend(f"{idx} 0 obj\n".encode("latin-1"))
            pdf.extend(obj)
            pdf.extend(b"\nendobj\n")

        xref_start = len(pdf)
        pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("latin-1"))
        pdf.extend(b"0000000000 65535 f \n")
        for offset in offsets[1:]:
            pdf.extend(f"{offset:010d} 00000 n \n".encode("latin-1"))
        pdf.extend(
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF\n".encode("latin-1")
        )
        return bytes(pdf)

    @staticmethod
    def _escape_pdf_text(value: str) -> str:
        return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
