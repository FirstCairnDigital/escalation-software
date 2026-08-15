from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from unpaid_invoice_escalator.models import Invoice, Jurisdiction, LedgerEvent


@dataclass(frozen=True)
class EvidenceBundleInput:
    invoice: Invoice
    communications: tuple[str, ...]
    contract_paths: tuple[str, ...]
    proof_of_supply_paths: tuple[str, ...]
    formal_notices: tuple[str, ...]
    ledger_events: tuple[LedgerEvent, ...]
    generated_at: datetime
    debtor_ledger_breakdown: tuple[str, ...] = ()
    client_fee_ledger_breakdown: tuple[str, ...] = ()
    resolution_artifact_paths: tuple[str, ...] = ()


class EvidencePackCompiler:
    """
    Builds a single structured PDF evidence bundle for client handoff.
    """

    def compile_bundle(self, bundle: EvidenceBundleInput, output_path: str) -> str:
        lines = self._bundle_lines(bundle)
        pdf_bytes = self._render_single_page_pdf(lines)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(pdf_bytes)
        return str(output)

    def _bundle_lines(self, bundle: EvidenceBundleInput) -> list[str]:
        invoice = bundle.invoice
        filing_portal, enforcement_route = self._jurisdiction_routes(invoice)
        lines: list[str] = [
            "Claim-Ready Evidence Bundle",
            "",
            f"Generated At: {bundle.generated_at.isoformat()}",
            f"Invoice ID: {invoice.invoice_id}",
            f"Jurisdiction: {invoice.jurisdiction.value}",
            f"Debtor Type: {invoice.debtor_type.value}",
            f"Principal: {invoice.currency} {invoice.principal_amount}",
            f"Issue Date: {invoice.issue_date.isoformat()}",
            f"Due Date: {invoice.due_date.isoformat()}",
            f"Filing Portal: {filing_portal}",
            f"Enforcement Route: {enforcement_route}",
            "",
            "Communications Log:",
        ]
        lines.extend([f"- {entry}" for entry in bundle.communications] or ["- None provided"])
        lines.append("")
        lines.append("Formal Pre-Action Notices:")
        lines.extend([f"- {notice}" for notice in bundle.formal_notices] or ["- None provided"])
        lines.append("")
        lines.append("Contract Artifacts:")
        if bundle.contract_paths:
            for raw_path in bundle.contract_paths:
                path = Path(raw_path)
                exists = path.exists()
                checksum = hashlib.sha256(path.read_bytes()).hexdigest() if exists else "MISSING_FILE"
                lines.append(f"- {path.name} | Exists={exists} | SHA256={checksum}")
        else:
            lines.append("- None provided")
        lines.append("")
        lines.append("Proof of Supply Artifacts:")
        if bundle.proof_of_supply_paths:
            for raw_path in bundle.proof_of_supply_paths:
                path = Path(raw_path)
                exists = path.exists()
                checksum = hashlib.sha256(path.read_bytes()).hexdigest() if exists else "MISSING_FILE"
                lines.append(f"- {path.name} | Exists={exists} | SHA256={checksum}")
        else:
            lines.append("- None provided")
        lines.append("")
        lines.append("Ledger Events:")
        if bundle.ledger_events:
            for event in bundle.ledger_events:
                lines.append(
                    f"- {event.timestamp.isoformat()} | {event.actor.value} | {event.event_type} | hash={event.hash}"
                )
        else:
            lines.append("- None provided")
        lines.append("")
        lines.append("Debtor Ledger Breakdown:")
        lines.extend([f"- {line}" for line in bundle.debtor_ledger_breakdown] or ["- None provided"])
        lines.append("")
        lines.append("FCD Client Fee Ledger Breakdown:")
        lines.extend([f"- {line}" for line in bundle.client_fee_ledger_breakdown] or ["- None provided"])
        lines.append("")
        lines.append("Resolution Artifacts:")
        if bundle.resolution_artifact_paths:
            for raw_path in bundle.resolution_artifact_paths:
                path = Path(raw_path)
                exists = path.exists()
                checksum = hashlib.sha256(path.read_bytes()).hexdigest() if exists else "MISSING_FILE"
                lines.append(f"- {path.name} | Exists={exists} | SHA256={checksum}")
        else:
            lines.append("- None provided")
        return lines

    @staticmethod
    def _jurisdiction_routes(invoice: Invoice) -> tuple[str, str]:
        if invoice.jurisdiction == Jurisdiction.SCOTLAND:
            return ("SCTS Civil Online", "Sheriff Officers")
        if invoice.jurisdiction == Jurisdiction.NORTHERN_IRELAND:
            return ("NI Direct Small Claims Portal", "Enforcement of Judgments Office (EJO)")
        return (
            "Make a Money Claim Online (MMCO)",
            "County Court Bailiffs / High Court Enforcement Officers (HCEOs)",
        )

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
