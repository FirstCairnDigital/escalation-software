from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Iterable

from unpaid_invoice_escalator.models import Actor, EngineDecision, Invoice, InvoiceState
from unpaid_invoice_escalator.services.evidence_pack_compiler import EvidenceBundleInput, EvidencePackCompiler
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger
from unpaid_invoice_escalator.services.jurisdiction_engine import EscalationContext, JurisdictionEngine, JurisdictionFacts


@dataclass(frozen=True)
class EscalationStepResult:
    decision: EngineDecision
    recorded_at: datetime


class EscalationRunner:
    def __init__(
        self,
        *,
        ledger: InvoiceLedger | None = None,
        jurisdiction_engine: JurisdictionEngine | None = None,
        evidence_pack_compiler: EvidencePackCompiler | None = None,
    ) -> None:
        self._ledger = ledger or InvoiceLedger()
        self._jurisdiction_engine = jurisdiction_engine or JurisdictionEngine()
        self._evidence_pack_compiler = evidence_pack_compiler or EvidencePackCompiler()

    @property
    def ledger(self) -> InvoiceLedger:
        return self._ledger

    def run_step(
        self,
        *,
        invoice: Invoice,
        current_state: InvoiceState,
        today: date,
        state_entered_on: date | None = None,
        debtor_feedback: str | None = None,
        system_flag: str | None = None,
        insolvency_flag: bool = False,
        payment_plan_proposed: bool = False,
        partially_paid: bool = False,
        regulated_debt_suspected: bool = False,
        jurisdiction_facts: JurisdictionFacts | None = None,
    ) -> EscalationStepResult:
        decision = self._jurisdiction_engine.decide(
            invoice,
            EscalationContext(
                current_state=current_state,
                today=today,
                state_entered_on=state_entered_on,
                debtor_feedback=debtor_feedback,
                system_flag=system_flag,
                insolvency_flag=insolvency_flag,
                payment_plan_proposed=payment_plan_proposed,
                partially_paid=partially_paid,
                regulated_debt_suspected=regulated_debt_suspected,
                jurisdiction_facts=jurisdiction_facts,
            ),
        )
        now = datetime.now(timezone.utc)
        self._ledger.append_event(
            invoice_id=invoice.invoice_id,
            actor=Actor.SYSTEM,
            event_type="ESCALATION_DECISION",
            timestamp=now,
            data_payload={
                "from_state": current_state.value,
                "next_state": decision.next_state.value,
                "outreach_frozen": decision.outreach_frozen,
                "instructions": decision.instructions,
                "documents_to_generate": list(decision.documents_to_generate),
                "wait_until": decision.wait_until.isoformat() if decision.wait_until else None,
            },
        )
        if decision.next_state != current_state:
            self._ledger.append_event(
                invoice_id=invoice.invoice_id,
                actor=Actor.SYSTEM,
                event_type="STATE_TRANSITION",
                timestamp=now,
                data_payload={"from_state": current_state.value, "to_state": decision.next_state.value},
            )
        return EscalationStepResult(decision=decision, recorded_at=now)

    def compile_evidence_bundle(
        self,
        *,
        invoice: Invoice,
        output_path: str,
        communications: Iterable[str],
        contract_paths: Iterable[str],
        proof_of_supply_paths: Iterable[str],
        formal_notices: Iterable[str],
        debtor_ledger_breakdown: Iterable[str] = (),
        client_fee_ledger_breakdown: Iterable[str] = (),
        resolution_artifact_paths: Iterable[str] = (),
    ) -> str:
        bundle = EvidenceBundleInput(
            invoice=invoice,
            communications=tuple(communications),
            contract_paths=tuple(contract_paths),
            proof_of_supply_paths=tuple(proof_of_supply_paths),
            formal_notices=tuple(formal_notices),
            ledger_events=self._ledger.events_for_invoice(invoice.invoice_id),
            generated_at=datetime.now(timezone.utc),
            debtor_ledger_breakdown=tuple(debtor_ledger_breakdown),
            client_fee_ledger_breakdown=tuple(client_fee_ledger_breakdown),
            resolution_artifact_paths=tuple(resolution_artifact_paths),
        )
        generated_path = self._evidence_pack_compiler.compile_bundle(bundle, output_path)
        self._ledger.append_event(
            invoice_id=invoice.invoice_id,
            actor=Actor.SYSTEM,
            event_type="EVIDENCE_PACK_GENERATED",
            data_payload={"output_path": generated_path},
        )
        return generated_path
