from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from unpaid_invoice_escalator.models import Invoice, Jurisdiction
from unpaid_invoice_escalator.rulepacks import RulePackLoader


@dataclass(frozen=True)
class CourtHandoffGuidance:
    destination_label: str
    required_documents: tuple[str, ...]
    automation_limit_gbp: Decimal
    enforcement_note: str
    rule_pack_version: str
    source_authority: str
    human_approval_required: bool


def resolve_court_handoff_guidance(
    invoice: Invoice,
    *,
    outstanding_amount: Decimal,
    on_date: date,
    rule_pack_loader: RulePackLoader | None = None,
) -> CourtHandoffGuidance:
    loader = rule_pack_loader or RulePackLoader()
    pack = loader.load_for(invoice.jurisdiction, on_date)
    automation_limit = Decimal(str(pack.fcd_automation_limit)).quantize(Decimal("0.01"))
    workflow = pack.workflow

    if invoice.jurisdiction == Jurisdiction.SCOTLAND:
        if outstanding_amount > automation_limit:
            destination_label = "Ordinary Cause / Scottish Solicitor review"
            required_documents = tuple(str(item) for item in workflow["over_limit_pack"])
        else:
            destination_label = "SCTS Civil Online"
            required_documents = tuple(str(item) for item in workflow["small_claims_pack"])
    elif invoice.jurisdiction == Jurisdiction.NORTHERN_IRELAND:
        if outstanding_amount > automation_limit:
            destination_label = "County Court Civil Bill / NI Solicitor review"
            required_documents = tuple(str(item) for item in workflow["over_limit_pack"])
        else:
            destination_label = "NI Direct Small Claims"
            required_documents = tuple(str(item) for item in workflow["small_claims_pack"])
    else:
        if outstanding_amount > automation_limit:
            destination_label = "County Court / Solicitor review"
            required_documents = tuple(str(item) for item in workflow["over_limit_pack"])
        else:
            destination_label = "Money Claim Online / County Court"
            required_documents = tuple(str(item) for item in workflow["small_claims_pack"])

    return CourtHandoffGuidance(
        destination_label=destination_label,
        required_documents=required_documents,
        automation_limit_gbp=automation_limit,
        enforcement_note=str(workflow["enforcement_note"]),
        rule_pack_version=pack.rule_version,
        source_authority=pack.source_authority,
        human_approval_required=pack.human_approval_required,
    )
