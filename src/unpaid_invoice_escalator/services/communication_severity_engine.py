from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
import re

from unpaid_invoice_escalator.models import Invoice, InvoiceState
from unpaid_invoice_escalator.rulepacks import RulePackLoader


@dataclass(frozen=True)
class CommunicationPreview:
    level: int
    stage_name: str
    template_version: str
    message: str
    guardrail_flags: tuple[str, ...]


class CommunicationSeverityEngine:
    _DEFAULT_TEMPLATES = {
        "LEVEL_0": "This is a courtesy note that Invoice {invoice_id} falls due on {due_date}.",
        "LEVEL_1": "This is a friendly reminder that Invoice {invoice_id} remains outstanding.",
        "LEVEL_2": (
            "Invoice {invoice_id} is overdue. Current balance is £{principal_amount}. "
            "Please review payment or resolution options."
        ),
        "LEVEL_3": "Please confirm payment arrangements or submit a formal dispute update for Invoice {invoice_id}.",
        "LEVEL_4": "Formal notice: Invoice {invoice_id} remains unpaid and may proceed to pre-action process.",
        "LEVEL_5": "Pre-action procedural notice issued for Invoice {invoice_id}. Procedural next steps may follow.",
        "LEVEL_6": "Automated processing has ended for Invoice {invoice_id}. The case is now in client handoff.",
    }
    _STAGE_NAMES = {
        0: "Pre-Due Courtesy",
        1: "Friendly Reminder",
        2: "Overdue Notification",
        3: "Request for Resolution",
        4: "Formal Notice",
        5: "Pre-Action Procedural Notice",
        6: "Client Handoff",
    }
    _STATE_TO_LEVEL = {
        InvoiceState.ISSUED: 0,
        InvoiceState.FRIENDLY_REMINDER: 1,
        InvoiceState.OVERDUE_CHASER: 2,
        InvoiceState.DISPUTE_REVIEW: 3,
        InvoiceState.FORMAL_NOTICE: 4,
        InvoiceState.PRE_ACTION_PROTOCOL: 5,
        InvoiceState.CLIENT_HANDOFF: 6,
    }
    _BANNED_PATTERNS = (
        (re.compile(r"\bfinal warning\b", re.IGNORECASE), "formal notice"),
        (re.compile(r"\blast chance\b", re.IGNORECASE), "next procedural step"),
        (re.compile(r"\bact now or else\b", re.IGNORECASE), "please review the options below"),
        (re.compile(r"\bbailiffs will attend\b", re.IGNORECASE), "independent legal enforcement may apply after court process"),
        (re.compile(r"\bcountdown\b", re.IGNORECASE), "timeline"),
        (re.compile(r"\bimmediate legal action\b", re.IGNORECASE), "possible procedural escalation"),
    )

    def __init__(self, *, rule_pack_loader: RulePackLoader | None = None) -> None:
        self._rule_pack_loader = rule_pack_loader or RulePackLoader()

    def preview_for_state(
        self,
        *,
        invoice: Invoice,
        state: InvoiceState,
        on_date: date,
        instructions: str,
        wait_until: date | None,
        outstanding_amount: Decimal | None = None,
    ) -> CommunicationPreview:
        level = self._STATE_TO_LEVEL.get(state, 3)
        pack = self._rule_pack_loader.load_for(invoice.jurisdiction, on_date)
        workflow = pack.workflow
        raw_templates = workflow.get("communication_templates")
        templates = dict(raw_templates) if isinstance(raw_templates, dict) else {}
        template = str(templates.get(f"LEVEL_{level}", self._DEFAULT_TEMPLATES[f"LEVEL_{level}"]))
        message = template.format(
            invoice_id=invoice.invoice_id,
            due_date=invoice.due_date.isoformat(),
            principal_amount=str(invoice.principal_amount if outstanding_amount is None else outstanding_amount),
            instructions=instructions,
            wait_until=wait_until.isoformat() if wait_until else "n/a",
        )
        sanitized_message, flags = self._apply_guardrails(message)
        return CommunicationPreview(
            level=level,
            stage_name=self._STAGE_NAMES[level],
            template_version=f"{pack.rule_id}:{pack.rule_version}",
            message=sanitized_message,
            guardrail_flags=flags,
        )

    def _apply_guardrails(self, message: str) -> tuple[str, tuple[str, ...]]:
        updated = message
        flags: list[str] = []
        for pattern, replacement in self._BANNED_PATTERNS:
            if pattern.search(updated):
                updated = pattern.sub(replacement, updated)
                flags.append(pattern.pattern)
        updated = re.sub(r"\s+", " ", updated).strip()
        return updated, tuple(flags)
