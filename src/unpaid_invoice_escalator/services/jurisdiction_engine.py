from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from unpaid_invoice_escalator.models import DebtorType, EngineDecision, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.rulepacks import RulePack, RulePackLoader


@dataclass(frozen=True)
class JurisdictionFacts:
    creditor_country_code: str | None = None
    debtor_country_code: str | None = None
    contract_jurisdiction: Jurisdiction | None = None
    place_of_supply_country_code: str | None = None


@dataclass(frozen=True)
class EscalationContext:
    current_state: InvoiceState
    today: date
    state_entered_on: date | None = None
    outstanding_amount: Decimal | None = None
    debtor_feedback: str | None = None
    system_flag: str | None = None
    insolvency_flag: bool = False
    payment_plan_proposed: bool = False
    partially_paid: bool = False
    regulated_debt_suspected: bool = False
    jurisdiction_facts: JurisdictionFacts | None = None


class JurisdictionEngine:
    def __init__(self, rule_pack_loader: RulePackLoader | None = None) -> None:
        self._rule_pack_loader = rule_pack_loader or RulePackLoader()

    def decide(self, invoice: Invoice, context: EscalationContext) -> EngineDecision:
        if invoice.debtor_type == DebtorType.CONSUMER_CREDIT:
            raise ValueError("CONSUMER_CREDIT invoices are out of scope for this system.")

        if self._is_jurisdiction_ambiguous(invoice.jurisdiction, context.jurisdiction_facts):
            return EngineDecision(
                next_state=InvoiceState.JURISDICTION_UNCERTAIN,
                outreach_frozen=True,
                instructions="Jurisdiction facts conflict. Freeze outreach and move to client/legal review.",
            )

        if context.current_state == InvoiceState.JURISDICTION_UNCERTAIN:
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions="Jurisdiction uncertainty unresolved. Handoff for independent legal review.",
            )

        hard_stop = self._hard_stop_decision(context)
        if hard_stop is not None:
            return hard_stop

        if context.current_state in (
            InvoiceState.DISPUTED,
            InvoiceState.BREATHING_SPACE_PAUSE,
            InvoiceState.CLIENT_HANDOFF,
            InvoiceState.RESOLVED_PAID,
        ):
            return EngineDecision(
                next_state=context.current_state,
                outreach_frozen=context.current_state != InvoiceState.RESOLVED_PAID,
                instructions="No auto-escalation from paused or terminal state.",
            )

        pack = self._rule_pack_loader.load_for(invoice.jurisdiction, context.today)
        if invoice.jurisdiction == Jurisdiction.SCOTLAND:
            return self._scotland(invoice, context, pack)
        if invoice.jurisdiction == Jurisdiction.NORTHERN_IRELAND:
            return self._northern_ireland(invoice, context, pack)
        return self._england_wales(invoice, context, pack)

    def _hard_stop_decision(self, context: EscalationContext) -> EngineDecision | None:
        if context.debtor_feedback == "DISPUTE":
            return EngineDecision(
                next_state=InvoiceState.DISPUTED,
                outreach_frozen=True,
                instructions="Dispute detected. Freeze outreach and route to client-led resolution.",
            )
        if context.system_flag == "BREATHING_SPACE":
            return EngineDecision(
                next_state=InvoiceState.BREATHING_SPACE_PAUSE,
                outreach_frozen=True,
                instructions="Breathing Space flag active. Freeze outreach immediately.",
            )
        if context.system_flag == "INSOLVENCY" or context.insolvency_flag:
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions="Insolvency flag detected. Freeze automation and escalate for specialist review.",
            )
        if (
            context.debtor_feedback == "PAYMENT_PLAN_REQUEST"
            or context.debtor_feedback == "PARTIALLY_PAID"
            or context.payment_plan_proposed
            or context.partially_paid
        ):
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions="Payment arrangement event detected. Freeze outreach and require client review.",
            )
        if context.regulated_debt_suspected:
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions="Regulated debt suspected. Freeze automation and handoff immediately.",
            )
        return None

    def _scotland(self, invoice: Invoice, context: EscalationContext, pack: RulePack) -> EngineDecision:
        outstanding = self._effective_outstanding_amount(invoice, context)
        automation_limit = Decimal(str(pack.fcd_automation_limit))
        enforcement_note = str(pack.workflow["enforcement_note"])
        if outstanding > automation_limit:
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions=(
                    f"Exceeds automated workflow limit (£{int(automation_limit)}). "
                    "Briefing Pack generated for Ordinary Cause / Scottish Solicitor review. "
                    f"Enforcement reference: {enforcement_note}."
                ),
                documents_to_generate=tuple(pack.workflow["over_limit_pack"]),
            )

        if context.current_state != InvoiceState.PRE_ACTION_PROTOCOL:
            return EngineDecision(
                next_state=self._advance_non_terminal(context.current_state),
                outreach_frozen=False,
                instructions="Continue pre-court settlement workflow under Scottish rule pack.",
            )

        return EngineDecision(
            next_state=InvoiceState.CLIENT_HANDOFF,
            outreach_frozen=True,
            instructions=f"Simple Procedure timeline complete. Submit via SCTS Civil Online. Enforcement reference: {enforcement_note}.",
            documents_to_generate=tuple(pack.workflow["small_claims_pack"]),
        )

    def _england_wales(self, invoice: Invoice, context: EscalationContext, pack: RulePack) -> EngineDecision:
        if invoice.debtor_type in (DebtorType.SOLE_TRADER, DebtorType.INDIVIDUAL):
            wait_days = int(pack.workflow["sole_trader_wait_days"])
            return self._protocol_flow(
                context=context,
                wait_days=wait_days,
                start_state=InvoiceState.PRE_ACTION_PROTOCOL,
                entry_documents=tuple(pack.workflow["sole_trader_documents"]),
                    handoff_documents=self._handoff_documents(invoice, context, pack),
                    handoff_instructions=self._handoff_instructions(
                        invoice, context, pack, "Money Claim Online / County Court"
                    ),
                )

        wait_days = int(pack.workflow["corporate_wait_days"])
        return self._corporate_lba_flow(
            context=context,
            wait_days=wait_days,
            entry_documents=tuple(pack.workflow["corporate_documents"]),
            handoff_documents=self._handoff_documents(invoice, context, pack),
            handoff_instructions=self._handoff_instructions(
                invoice, context, pack, "Money Claim Online / County Court"
            ),
        )

    def _northern_ireland(self, invoice: Invoice, context: EscalationContext, pack: RulePack) -> EngineDecision:
        outstanding = self._effective_outstanding_amount(invoice, context)
        automation_limit = Decimal(str(pack.fcd_automation_limit))
        enforcement_note = str(pack.workflow["enforcement_note"])
        if outstanding > automation_limit:
            return EngineDecision(
                next_state=InvoiceState.CLIENT_HANDOFF,
                outreach_frozen=True,
                instructions=(
                    f"Exceeds NI Small Claims limit (£{int(automation_limit)}). "
                    "Export Evidence Pack for County Court Civil Bill / NI Solicitor review. "
                    f"Enforcement reference: {enforcement_note}."
                ),
                documents_to_generate=tuple(pack.workflow["over_limit_pack"]),
            )

        if invoice.debtor_type in (DebtorType.SOLE_TRADER, DebtorType.INDIVIDUAL):
            wait_days = int(pack.workflow["sole_trader_wait_days"])
            return self._protocol_flow(
                context=context,
                wait_days=wait_days,
                start_state=InvoiceState.PRE_ACTION_PROTOCOL,
                entry_documents=tuple(pack.workflow["sole_trader_documents"]),
                handoff_documents=tuple(pack.workflow["small_claims_pack"]),
                handoff_instructions=(
                    "Pre-action protocol complete. Prepare NI Direct Small Claims Evidence Pack. "
                    f"Enforcement reference: {enforcement_note}."
                ),
            )

        wait_days = int(pack.workflow["corporate_wait_days"])
        return self._corporate_lba_flow(
            context=context,
            wait_days=wait_days,
            entry_documents=tuple(pack.workflow["corporate_documents"]),
            handoff_documents=tuple(pack.workflow["small_claims_pack"]),
            handoff_instructions=(
                "County Court commercial pre-action timeline complete. "
                f"Prepare NI Direct Small Claims Evidence Pack. Enforcement reference: {enforcement_note}."
            ),
        )

    def _protocol_flow(
        self,
        *,
        context: EscalationContext,
        wait_days: int,
        start_state: InvoiceState,
        entry_documents: tuple[str, ...],
        handoff_documents: tuple[str, ...],
        handoff_instructions: str,
    ) -> EngineDecision:
        protocol_start = context.state_entered_on or context.today
        wait_until = protocol_start + timedelta(days=wait_days)
        if context.current_state != start_state:
            return EngineDecision(
                next_state=start_state,
                outreach_frozen=True,
                instructions=f"Issue protocol pack and enforce mandatory {wait_days}-day response window.",
                documents_to_generate=entry_documents,
                wait_until=context.today + timedelta(days=wait_days),
            )
        if context.today < wait_until:
            return EngineDecision(
                next_state=start_state,
                outreach_frozen=True,
                instructions=f"Mandatory {wait_days}-day protocol freeze active; do not proceed.",
                wait_until=wait_until,
            )
        return EngineDecision(
            next_state=InvoiceState.CLIENT_HANDOFF,
            outreach_frozen=True,
            instructions=handoff_instructions,
            documents_to_generate=handoff_documents,
        )

    def _corporate_lba_flow(
        self,
        *,
        context: EscalationContext,
        wait_days: int,
        entry_documents: tuple[str, ...],
        handoff_documents: tuple[str, ...],
        handoff_instructions: str,
    ) -> EngineDecision:
        if context.current_state != InvoiceState.FORMAL_NOTICE:
            return EngineDecision(
                next_state=InvoiceState.FORMAL_NOTICE,
                outreach_frozen=True,
                instructions=f"Issue formal notice and enforce {wait_days}-day wait period.",
                documents_to_generate=entry_documents,
                wait_until=context.today + timedelta(days=wait_days),
            )
        wait_until = (context.state_entered_on or context.today) + timedelta(days=wait_days)
        if context.today < wait_until:
            return EngineDecision(
                next_state=InvoiceState.FORMAL_NOTICE,
                outreach_frozen=True,
                instructions=f"{wait_days}-day formal notice period active; pause further automation.",
                wait_until=wait_until,
            )
        return EngineDecision(
            next_state=InvoiceState.CLIENT_HANDOFF,
            outreach_frozen=True,
            instructions=handoff_instructions,
            documents_to_generate=handoff_documents,
        )

    def _handoff_documents(self, invoice: Invoice, context: EscalationContext, pack: RulePack) -> tuple[str, ...]:
        if self._effective_outstanding_amount(invoice, context) > Decimal(str(pack.fcd_automation_limit)):
            return tuple(pack.workflow["over_limit_pack"])
        return tuple(pack.workflow["small_claims_pack"])

    def _handoff_instructions(
        self, invoice: Invoice, context: EscalationContext, pack: RulePack, filing_label: str
    ) -> str:
        enforcement_note = str(pack.workflow["enforcement_note"])
        if self._effective_outstanding_amount(invoice, context) > Decimal(str(pack.fcd_automation_limit)):
            return (
                "This case has reached the FCD automated workflow limit. Download your evidence pack for independent "
                f"filing or legal review. Enforcement reference: {enforcement_note}."
            )
        return f"Pre-action timeline complete. Prepare {filing_label} Evidence Pack. Enforcement reference: {enforcement_note}."

    @staticmethod
    def _effective_outstanding_amount(invoice: Invoice, context: EscalationContext) -> Decimal:
            if context.outstanding_amount is not None:
                return context.outstanding_amount
            return invoice.principal_amount

    @staticmethod
    def _advance_non_terminal(current: InvoiceState) -> InvoiceState:
        order = (
            InvoiceState.ISSUED,
            InvoiceState.FRIENDLY_REMINDER,
            InvoiceState.OVERDUE_CHASER,
            InvoiceState.FORMAL_NOTICE,
            InvoiceState.PRE_ACTION_PROTOCOL,
        )
        try:
            idx = order.index(current)
        except ValueError as exc:
            raise ValueError(f"Unsupported escalation state: {current}") from exc
        if idx == len(order) - 1:
            return InvoiceState.CLIENT_HANDOFF
        return order[idx + 1]

    @staticmethod
    def _is_jurisdiction_ambiguous(selected: Jurisdiction, facts: JurisdictionFacts | None) -> bool:
        if facts is None:
            return False
        if facts.contract_jurisdiction is not None and facts.contract_jurisdiction != selected:
            return True
        inferred: set[Jurisdiction] = set()
        for country_code in (
            facts.creditor_country_code,
            facts.debtor_country_code,
            facts.place_of_supply_country_code,
        ):
            inferred_jurisdiction = JurisdictionEngine._country_code_to_jurisdiction(country_code)
            if inferred_jurisdiction is not None:
                inferred.add(inferred_jurisdiction)
        if len(inferred) > 1:
            return True
        if len(inferred) == 1 and selected not in inferred:
            return True
        return False

    @staticmethod
    def _country_code_to_jurisdiction(country_code: str | None) -> Jurisdiction | None:
        if country_code is None:
            return None
        normalized = country_code.strip().upper().replace(" ", "_").replace("-", "_")
        if normalized in {"GB_ENG", "ENG", "ENGLAND", "GB_WLS", "WLS", "WALES"}:
            return Jurisdiction.ENGLAND_WALES
        if normalized in {"GB_SCT", "SCT", "SCOTLAND"}:
            return Jurisdiction.SCOTLAND
        if normalized in {"GB_NIR", "NIR", "NORTHERN_IRELAND"}:
            return Jurisdiction.NORTHERN_IRELAND
        return None
