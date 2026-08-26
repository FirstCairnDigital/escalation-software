from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from unpaid_invoice_escalator.models import Invoice, LedgerEvent
from unpaid_invoice_escalator.services.court_handoff_guidance import resolve_court_handoff_guidance
from unpaid_invoice_escalator.services.pdf_text_renderer import TextPdfRenderer


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
    communication_delivery_timeline: tuple[str, ...] = ()
    correction_withdrawal_notices: tuple[str, ...] = ()
    evidence_artifact_inventory: tuple[str, ...] = ()
    compliance_snapshot: tuple[str, ...] = ()
    event_chain_attestation: tuple[str, ...] = ()
    outstanding_amount_gbp: Decimal | None = None


class EvidencePackCompiler:
    """
    Builds a single structured PDF evidence bundle for client handoff.
    """

    def __init__(self) -> None:
        self._pdf_renderer = TextPdfRenderer()

    def compile_bundle(self, bundle: EvidenceBundleInput, output_path: str) -> str:
        lines = self._bundle_lines(bundle)
        pdf_bytes = self._pdf_renderer.render(lines)
        output = Path(output_path)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(pdf_bytes)
        return str(output)

    def _bundle_lines(self, bundle: EvidenceBundleInput) -> list[str]:
        invoice = bundle.invoice
        outstanding_amount = bundle.outstanding_amount_gbp if bundle.outstanding_amount_gbp is not None else invoice.principal_amount
        handoff_guidance = resolve_court_handoff_guidance(invoice, outstanding_amount=outstanding_amount, on_date=bundle.generated_at.date())
        lines: list[str] = [
            "Claim-Ready Evidence Bundle",
            "",
            f"Generated At: {bundle.generated_at.isoformat()}",
            f"Invoice ID: {invoice.invoice_id}",
            f"Jurisdiction: {invoice.jurisdiction.value}",
            f"Debtor Type: {invoice.debtor_type.value}",
            f"Original Principal: {invoice.currency} {invoice.principal_amount}",
            f"Current Outstanding Balance: {invoice.currency} {outstanding_amount}",
            f"Issue Date: {invoice.issue_date.isoformat()}",
            f"Due Date: {invoice.due_date.isoformat()}",
            f"Handoff Destination: {handoff_guidance.destination_label}",
            f"Automation Limit (GBP): {handoff_guidance.automation_limit_gbp}",
            f"Enforcement Route: {handoff_guidance.enforcement_note}",
            f"Required Handoff Pack: {', '.join(handoff_guidance.required_documents)}",
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
        lines.append("")
        lines.append("Communication Delivery Timeline:")
        lines.extend([f"- {line}" for line in bundle.communication_delivery_timeline] or ["- None provided"])
        lines.append("")
        lines.append("Correction and Withdrawal Notices:")
        lines.extend([f"- {line}" for line in bundle.correction_withdrawal_notices] or ["- None provided"])
        lines.append("")
        lines.append("Evidence Artifact Inventory:")
        lines.extend([f"- {line}" for line in bundle.evidence_artifact_inventory] or ["- None provided"])
        lines.append("")
        lines.append("Compliance Snapshot:")
        lines.extend([f"- {line}" for line in bundle.compliance_snapshot] or ["- None provided"])
        lines.append("")
        lines.append("Event Chain Attestation:")
        lines.extend([f"- {line}" for line in bundle.event_chain_attestation] or ["- None provided"])
        return lines
