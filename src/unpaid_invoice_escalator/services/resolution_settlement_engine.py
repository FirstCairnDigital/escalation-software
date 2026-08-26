from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from uuid import uuid4

from unpaid_invoice_escalator.models import (
    Actor,
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    DisputeCarveOut,
    PaymentPlanAgreement,
    PaymentPlanDecision,
    PaymentPlanDecisionStatus,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    ReportedPaymentStatus,
    SettlementAcceptance,
    SettlementOffer,
    SettlementOfferFinalization,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger

TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class PaymentPlanStatus:
    plan_id: str
    status: str
    total_amount_gbp: Decimal
    paid_amount_gbp: Decimal
    remaining_amount_gbp: Decimal
    missed_installment_count: int
    status_history: tuple[dict[str, str], ...]


@dataclass(frozen=True)
class SettlementOfferStatus:
    offer_id: str
    status: str
    accepted_roles: tuple[str, ...]
    confirmed_payment_total_gbp: Decimal
    remaining_payment_gbp: Decimal
    finalized_at: str | None


class ResolutionAndSettlementEngine:
    def __init__(self, *, store: SQLiteStore, event_ledger: InvoiceLedger) -> None:
        self._store = store
        self._event_ledger = event_ledger

    def propose_payment_plan(
        self,
        *,
        invoice_id: str,
        proposed_by: str,
        proposer_role: str,
        installment_amount_gbp: Decimal,
        installment_count: int,
        first_due_date: date,
        frequency_days: int,
        notes: str = "",
        parent_plan_id: str | None = None,
    ) -> tuple[PaymentPlanAgreement, tuple[PaymentPlanInstallment, ...]]:
        if installment_count < 1:
            raise ValueError("installment_count must be >= 1.")
        if frequency_days < 1:
            raise ValueError("frequency_days must be >= 1.")
        normalized_role = proposer_role.strip().upper()
        if normalized_role not in {"DEBTOR", "CREDITOR"}:
            raise ValueError("proposer_role must be DEBTOR or CREDITOR.")
        amount = installment_amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if amount <= Decimal("0.00"):
            raise ValueError("installment_amount_gbp must be > 0.")
        version_number = 1
        if parent_plan_id is not None:
            parent_plan = self._store.payment_plan_agreement_by_id(parent_plan_id)
            if parent_plan is None or parent_plan.invoice_id != invoice_id:
                raise ValueError("parent_plan_id must reference an existing payment plan for this invoice.")
            parent_status = self.payment_plan_status(plan_id=parent_plan_id, as_of_date=date.today()).status
            if parent_status in {"ACTIVE", "COMPLETED", "DEFAULTED", "REJECTED", "WITHDRAWN", "EXPIRED"}:
                raise ValueError("Counter-offers can only be made against a currently open payment-plan proposal.")
            version_number = parent_plan.version_number + 1
        now = datetime.now(timezone.utc)
        plan = PaymentPlanAgreement(
            plan_id=str(uuid4()),
            invoice_id=invoice_id,
            created_at=now,
            proposed_by=proposed_by,
            installment_amount_gbp=amount,
            installment_count=installment_count,
            first_due_date=first_due_date,
            frequency_days=frequency_days,
            notes=notes,
            proposer_role=normalized_role,
            parent_plan_id=parent_plan_id,
            version_number=version_number,
        )
        installments = tuple(
            PaymentPlanInstallment(
                installment_id=str(uuid4()),
                plan_id=plan.plan_id,
                invoice_id=invoice_id,
                due_date=first_due_date + timedelta(days=frequency_days * idx),
                amount_gbp=amount,
                sequence_number=idx + 1,
            )
            for idx in range(installment_count)
        )
        self._store.append_payment_plan_agreement(plan)
        self._store.append_payment_plan_installments(installments)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT if normalized_role == "CREDITOR" else Actor.DEBTOR,
            event_type="PAYMENT_PLAN_COUNTER_OFFERED" if parent_plan_id is not None else "PAYMENT_PLAN_PROPOSED",
            timestamp=now,
            data_payload={
                "plan_id": plan.plan_id,
                "proposed_by": proposed_by,
                "proposer_role": normalized_role,
                "installment_amount_gbp": str(amount),
                "installment_count": installment_count,
                "first_due_date": first_due_date.isoformat(),
                "frequency_days": frequency_days,
                "parent_plan_id": parent_plan_id,
                "version_number": version_number,
            },
        )
        return plan, installments

    def accept_payment_plan(
        self,
        *,
        plan_id: str,
        accepted_by: str,
        accepter_role: str,
    ) -> tuple[PaymentPlanDecision, PaymentPlanDecision]:
        plan = self._store.payment_plan_agreement_by_id(plan_id)
        if plan is None:
            raise ValueError("Payment plan not found.")
        normalized_role = accepter_role.strip().upper()
        if normalized_role not in {"DEBTOR", "CREDITOR"}:
            raise ValueError("accepter_role must be DEBTOR or CREDITOR.")
        if normalized_role == plan.proposer_role:
            raise ValueError("Plan proposer cannot separately accept their own proposed terms.")
        current_status = self.payment_plan_status(plan_id=plan_id, as_of_date=date.today()).status
        if current_status in {"REJECTED", "WITHDRAWN", "EXPIRED", "ACTIVE", "COMPLETED", "DEFAULTED"}:
            raise ValueError(f"Payment plan cannot be accepted while in status {current_status}.")
        existing = self._store.payment_plan_decisions_for_plan(plan_id)
        if any(item.status == PaymentPlanDecisionStatus.ACCEPTED and item.actor_role == normalized_role for item in existing):
            raise ValueError(f"{normalized_role} has already accepted this payment plan.")
        now = datetime.now(timezone.utc)
        acceptance = PaymentPlanDecision(
            decision_id=str(uuid4()),
            plan_id=plan_id,
            invoice_id=plan.invoice_id,
            decided_at=now,
            decided_by=accepted_by,
            actor_role=normalized_role,
            status=PaymentPlanDecisionStatus.ACCEPTED,
        )
        activation = PaymentPlanDecision(
            decision_id=str(uuid4()),
            plan_id=plan_id,
            invoice_id=plan.invoice_id,
            decided_at=now,
            decided_by=accepted_by,
            actor_role="SYSTEM",
            status=PaymentPlanDecisionStatus.ACTIVATED,
            notes="Mutual assent complete for current payment-plan terms.",
        )
        self._store.append_payment_plan_decision(acceptance)
        self._store.append_payment_plan_decision(activation)
        self._event_ledger.append_event(
            invoice_id=plan.invoice_id,
            actor=Actor.CLIENT if normalized_role == "CREDITOR" else Actor.DEBTOR,
            event_type="PAYMENT_PLAN_ACCEPTED",
            timestamp=now,
            data_payload={"plan_id": plan_id, "accepted_by": accepted_by, "accepter_role": normalized_role},
        )
        self._event_ledger.append_event(
            invoice_id=plan.invoice_id,
            actor=Actor.SYSTEM,
            event_type="PAYMENT_PLAN_ACTIVATED",
            timestamp=now,
            data_payload={"plan_id": plan_id, "version_number": plan.version_number},
        )
        return acceptance, activation

    def reject_payment_plan(
        self,
        *,
        plan_id: str,
        rejected_by: str,
        rejecter_role: str,
        notes: str = "",
    ) -> PaymentPlanDecision:
        return self._record_plan_decision(
            plan_id=plan_id,
            decided_by=rejected_by,
            actor_role=rejecter_role,
            status=PaymentPlanDecisionStatus.REJECTED,
            notes=notes,
            event_type="PAYMENT_PLAN_REJECTED",
        )

    def withdraw_payment_plan(
        self,
        *,
        plan_id: str,
        withdrawn_by: str,
        withdrawer_role: str,
        notes: str = "",
    ) -> PaymentPlanDecision:
        return self._record_plan_decision(
            plan_id=plan_id,
            decided_by=withdrawn_by,
            actor_role=withdrawer_role,
            status=PaymentPlanDecisionStatus.WITHDRAWN,
            notes=notes,
            event_type="PAYMENT_PLAN_WITHDRAWN",
            require_proposer=True,
        )

    def expire_payment_plan(
        self,
        *,
        plan_id: str,
        expired_by: str,
        notes: str = "",
    ) -> PaymentPlanDecision:
        return self._record_plan_decision(
            plan_id=plan_id,
            decided_by=expired_by,
            actor_role="SYSTEM",
            status=PaymentPlanDecisionStatus.EXPIRED,
            notes=notes,
            event_type="PAYMENT_PLAN_EXPIRED",
        )

    def _record_plan_decision(
        self,
        *,
        plan_id: str,
        decided_by: str,
        actor_role: str,
        status: PaymentPlanDecisionStatus,
        notes: str,
        event_type: str,
        require_proposer: bool = False,
    ) -> PaymentPlanDecision:
        plan = self._store.payment_plan_agreement_by_id(plan_id)
        if plan is None:
            raise ValueError("Payment plan not found.")
        normalized_role = actor_role.strip().upper()
        if normalized_role not in {"DEBTOR", "CREDITOR", "SYSTEM"}:
            raise ValueError("actor_role must be DEBTOR, CREDITOR, or SYSTEM.")
        if require_proposer and normalized_role != plan.proposer_role:
            raise ValueError("Only the current payment-plan proposer may withdraw these terms.")
        current_status = self.payment_plan_status(plan_id=plan_id, as_of_date=date.today()).status
        if current_status in {"REJECTED", "WITHDRAWN", "EXPIRED", "ACTIVE", "COMPLETED", "DEFAULTED"}:
            raise ValueError(f"Payment plan cannot be updated while in status {current_status}.")
        now = datetime.now(timezone.utc)
        decision = PaymentPlanDecision(
            decision_id=str(uuid4()),
            plan_id=plan_id,
            invoice_id=plan.invoice_id,
            decided_at=now,
            decided_by=decided_by,
            actor_role=normalized_role,
            status=status,
            notes=notes,
        )
        self._store.append_payment_plan_decision(decision)
        self._event_ledger.append_event(
            invoice_id=plan.invoice_id,
            actor=Actor.SYSTEM if normalized_role == "SYSTEM" else (Actor.CLIENT if normalized_role == "CREDITOR" else Actor.DEBTOR),
            event_type=event_type,
            timestamp=now,
            data_payload={"plan_id": plan_id, "decided_by": decided_by, "actor_role": normalized_role, "notes": notes},
        )
        return decision

    def record_confirmed_installment_payment(
        self,
        *,
        invoice_id: str,
        plan_id: str,
        installment_id: str,
        amount_gbp: Decimal,
        recorded_by: str,
        reported_payment_id: str | None = None,
    ) -> PaymentPlanPayment:
        current_status = self.payment_plan_status(plan_id=plan_id, as_of_date=date.today()).status
        if current_status not in {"ACTIVE", "DEFAULTED"}:
            raise ValueError("Installment payments can only be confirmed against an active or defaulted plan.")
        amount = amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if amount <= Decimal("0.00"):
            raise ValueError("amount_gbp must be > 0.")
        now = datetime.now(timezone.utc)
        payment = PaymentPlanPayment(
            payment_id=str(uuid4()),
            plan_id=plan_id,
            installment_id=installment_id,
            invoice_id=invoice_id,
            paid_at=now,
            amount_gbp=amount,
            recorded_by=recorded_by,
            reported_payment_id=reported_payment_id,
        )
        self._store.append_payment_plan_payment(payment)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="PAYMENT_PLAN_INSTALLMENT_CONFIRMED",
            timestamp=now,
            data_payload={
                "plan_id": plan_id,
                "installment_id": installment_id,
                "amount_gbp": str(amount),
                "recorded_by": recorded_by,
                "reported_payment_id": reported_payment_id,
            },
        )
        return payment

    def payment_plan_status(self, *, plan_id: str, as_of_date: date) -> PaymentPlanStatus:
        plan = self._store.payment_plan_agreement_by_id(plan_id)
        if plan is None:
            raise ValueError("Payment plan not found.")
        installments = self._store.payment_plan_installments_for_plan(plan_id)
        payments = self._store.payment_plan_payments_for_plan(plan_id)
        decisions = self._store.payment_plan_decisions_for_plan(plan_id)
        sibling_plans = self._store.payment_plan_agreements_for_invoice(plan.invoice_id)
        has_counter_offer = any(item.parent_plan_id == plan_id for item in sibling_plans)
        activation_date = None
        for decision in decisions:
            if decision.status == PaymentPlanDecisionStatus.ACTIVATED:
                activation_date = decision.decided_at.date()
        paid_by_installment: dict[str, Decimal] = {}
        for payment in payments:
            paid_by_installment[payment.installment_id] = paid_by_installment.get(payment.installment_id, Decimal("0.00")) + (
                payment.amount_gbp
            )

        total = sum((item.amount_gbp for item in installments), start=Decimal("0.00"))
        paid = sum((payment.amount_gbp for payment in payments), start=Decimal("0.00"))
        missed_count = 0
        all_paid = True
        for installment in installments:
            installment_paid = paid_by_installment.get(installment.installment_id, Decimal("0.00"))
            if installment_paid < installment.amount_gbp:
                all_paid = False
                if installment.due_date < as_of_date and (activation_date is None or installment.due_date >= activation_date):
                    missed_count += 1
        accepted = any(item.status == PaymentPlanDecisionStatus.ACCEPTED for item in decisions)
        activated = any(item.status == PaymentPlanDecisionStatus.ACTIVATED for item in decisions)
        rejected = any(item.status == PaymentPlanDecisionStatus.REJECTED for item in decisions)
        withdrawn = any(item.status == PaymentPlanDecisionStatus.WITHDRAWN for item in decisions)
        expired = any(item.status == PaymentPlanDecisionStatus.EXPIRED for item in decisions)
        if all_paid and activated:
            status = "COMPLETED"
        elif missed_count > 0 and activated:
            status = "DEFAULTED"
        elif rejected:
            status = "REJECTED"
        elif withdrawn:
            status = "WITHDRAWN"
        elif expired:
            status = "EXPIRED"
        elif activated or accepted:
            status = "ACTIVE"
        elif has_counter_offer:
            status = "COUNTER_OFFERED"
        else:
            status = "COUNTER_OFFERED" if plan.parent_plan_id is not None else "PROPOSED"
        remaining = max(Decimal("0.00"), total - paid)
        history: list[dict[str, str]] = [
            {
                "status": "COUNTER_OFFERED" if plan.parent_plan_id is not None else "PROPOSED",
                "timestamp": plan.created_at.isoformat(),
                "actor_role": plan.proposer_role,
            }
        ]
        history.extend(
            {
                "status": item.status.value,
                "timestamp": item.decided_at.isoformat(),
                "actor_role": item.actor_role,
            }
            for item in decisions
        )
        return PaymentPlanStatus(
            plan_id=plan_id,
            status=status,
            total_amount_gbp=total.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            paid_amount_gbp=paid.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            remaining_amount_gbp=remaining.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            missed_installment_count=missed_count,
            status_history=tuple(history),
        )

    def propose_settlement_offer(
        self,
        *,
        invoice_id: str,
        offered_by: str,
        offered_amount_gbp: Decimal,
        expiry_date: date,
        notes: str = "",
    ) -> SettlementOffer:
        amount = offered_amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if amount <= Decimal("0.00"):
            raise ValueError("offered_amount_gbp must be > 0.")
        now = datetime.now(timezone.utc)
        offer = SettlementOffer(
            offer_id=str(uuid4()),
            invoice_id=invoice_id,
            offered_at=now,
            offered_by=offered_by,
            offered_amount_gbp=amount,
            expiry_date=expiry_date,
            notes=notes,
        )
        self._store.append_settlement_offer(offer)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="SETTLEMENT_OFFER_PROPOSED",
            timestamp=now,
            data_payload={
                "offer_id": offer.offer_id,
                "offered_by": offered_by,
                "offered_amount_gbp": str(amount),
                "expiry_date": expiry_date.isoformat(),
            },
        )
        return offer

    def accept_settlement_offer(
        self,
        *,
        offer_id: str,
        accepted_by: str,
        accepter_role: str,
    ) -> tuple[SettlementAcceptance, bool]:
        offer = self._store.settlement_offer_by_id(offer_id)
        if offer is None:
            raise ValueError("Settlement offer not found.")
        normalized_role = accepter_role.strip().upper()
        if normalized_role not in {"DEBTOR", "CREDITOR"}:
            raise ValueError("accepter_role must be DEBTOR or CREDITOR.")
        existing = self._store.settlement_acceptances_for_offer(offer_id)
        if any(item.accepter_role == normalized_role for item in existing):
            raise ValueError(f"{normalized_role} has already accepted this settlement offer.")
        now = datetime.now(timezone.utc)
        acceptance = SettlementAcceptance(
            acceptance_id=str(uuid4()),
            offer_id=offer_id,
            invoice_id=offer.invoice_id,
            accepted_at=now,
            accepted_by=accepted_by,
            accepter_role=normalized_role,
        )
        self._store.append_settlement_acceptance(acceptance)
        self._event_ledger.append_event(
            invoice_id=offer.invoice_id,
            actor=Actor.CLIENT if normalized_role == "CREDITOR" else Actor.DEBTOR,
            event_type="SETTLEMENT_OFFER_ACCEPTED",
            timestamp=now,
            data_payload={"offer_id": offer_id, "accepter_role": normalized_role, "accepted_by": accepted_by},
        )
        finalized = self._store.settlement_offer_finalization_by_offer_id(offer_id) is not None
        return acceptance, finalized

    def settlement_offer_status(self, *, offer_id: str, as_of_date: date) -> SettlementOfferStatus:
        offer = self._store.settlement_offer_by_id(offer_id)
        if offer is None:
            raise ValueError("Settlement offer not found.")
        acceptances = self._store.settlement_acceptances_for_offer(offer_id)
        accepted_roles = tuple(sorted({item.accepter_role for item in acceptances}))
        finalization = self._store.settlement_offer_finalization_by_offer_id(offer_id)
        confirmed_total = self._confirmed_settlement_payment_total(offer=offer, as_of_date=as_of_date)
        remaining = max(Decimal("0.00"), offer.offered_amount_gbp - confirmed_total).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        if finalization is not None:
            status = "FINALIZED"
        elif accepted_roles == ("CREDITOR", "DEBTOR"):
            status = "EXPIRED" if as_of_date > offer.expiry_date else "AWAITING_PAYMENT"
        elif as_of_date > offer.expiry_date:
            status = "EXPIRED"
        else:
            status = "OPEN"
        return SettlementOfferStatus(
            offer_id=offer_id,
            status=status,
            accepted_roles=accepted_roles,
            confirmed_payment_total_gbp=confirmed_total,
            remaining_payment_gbp=remaining,
            finalized_at=None if finalization is None else finalization.finalized_at.isoformat(),
        )

    def finalize_settlement_offer_if_paid(
        self,
        *,
        offer_id: str,
        finalized_by: str,
        triggering_report_id: str | None = None,
    ) -> SettlementOfferFinalization | None:
        offer = self._store.settlement_offer_by_id(offer_id)
        if offer is None:
            raise ValueError("Settlement offer not found.")
        existing_finalization = self._store.settlement_offer_finalization_by_offer_id(offer_id)
        if existing_finalization is not None:
            return existing_finalization
        acceptances = self._store.settlement_acceptances_for_offer(offer_id)
        accepted_roles = {item.accepter_role for item in acceptances}
        if accepted_roles != {"DEBTOR", "CREDITOR"}:
            raise ValueError("Settlement offer requires bilateral acceptance before payment can finalize it.")
        confirmed_total = self._confirmed_settlement_payment_total(offer=offer, as_of_date=offer.expiry_date)
        if confirmed_total < offer.offered_amount_gbp:
            return None
        now = datetime.now(timezone.utc)
        outstanding_before = self._store.debtor_ledger_balance_for_invoice(offer.invoice_id).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        discount = max(Decimal("0.00"), outstanding_before).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if discount > Decimal("0.00"):
            self._store.append_debtor_ledger_entry(
                DebtorLedgerEntry(
                    entry_id=str(uuid4()),
                    invoice_id=offer.invoice_id,
                    timestamp=now,
                    entry_type=DebtorLedgerEntryType.SETTLEMENT_DISCOUNT,
                    amount_gbp=-discount,
                    description=f"Full and final settlement discount for offer {offer.offer_id}.",
                )
            )
        finalization = SettlementOfferFinalization(
            finalization_id=str(uuid4()),
            offer_id=offer.offer_id,
            invoice_id=offer.invoice_id,
            finalized_at=now,
            finalized_by=finalized_by,
            triggering_report_id=triggering_report_id,
            confirmed_payment_total_gbp=confirmed_total,
            outstanding_before_gbp=outstanding_before,
            settlement_discount_applied_gbp=discount,
        )
        self._store.append_settlement_offer_finalization(finalization)
        self._event_ledger.append_event(
            invoice_id=offer.invoice_id,
            actor=Actor.SYSTEM,
            event_type="SETTLEMENT_OFFER_FINALIZED",
            timestamp=now,
            data_payload={
                "offer_id": offer.offer_id,
                "offered_amount_gbp": str(offer.offered_amount_gbp),
                "outstanding_before_gbp": str(outstanding_before),
                "confirmed_payment_total_gbp": str(confirmed_total),
                "settlement_discount_applied_gbp": str(discount),
                "triggering_report_id": triggering_report_id,
            },
        )
        return finalization

    def _confirmed_settlement_payment_total(self, *, offer: SettlementOffer, as_of_date: date) -> Decimal:
        total = Decimal("0.00")
        for report in self._store.reported_payments_for_invoice(offer.invoice_id):
            if report.settlement_offer_id != offer.offer_id:
                continue
            decisions = self._store.reported_payment_decisions_for_report(report.report_id)
            if not decisions or decisions[-1].status != ReportedPaymentStatus.PAYMENT_CONFIRMED_BY_CREDITOR:
                continue
            effective_date = report.payment_date or report.reported_at.date()
            if effective_date > as_of_date:
                continue
            confirmed_amount = decisions[-1].confirmed_amount_gbp or report.amount_gbp
            total += confirmed_amount
        return total.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    def create_dispute_carve_out(
        self,
        *,
        invoice_id: str,
        disputed_amount_gbp: Decimal,
        reason: str,
        created_by: str,
    ) -> DisputeCarveOut:
        disputed = disputed_amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if disputed <= Decimal("0.00"):
            raise ValueError("disputed_amount_gbp must be > 0.")
        outstanding_before = self._store.debtor_ledger_balance_for_invoice(invoice_id)
        if disputed > outstanding_before:
            raise ValueError("disputed_amount_gbp cannot exceed current outstanding balance.")
        undisputed = (outstanding_before - disputed).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        now = datetime.now(timezone.utc)
        carve_out = DisputeCarveOut(
            carve_out_id=str(uuid4()),
            invoice_id=invoice_id,
            created_at=now,
            disputed_amount_gbp=disputed,
            undisputed_amount_gbp=undisputed,
            reason=reason,
            created_by=created_by,
        )
        self._store.append_dispute_carve_out(carve_out)
        self._store.append_debtor_ledger_entry(
            DebtorLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                entry_type=DebtorLedgerEntryType.DISPUTED_CARVE_OUT,
                amount_gbp=-disputed,
                description=f"Dispute carve-out applied: {reason}",
            )
        )
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="DISPUTE_CARVE_OUT_CREATED",
            timestamp=now,
            data_payload={
                "carve_out_id": carve_out.carve_out_id,
                "disputed_amount_gbp": str(disputed),
                "undisputed_amount_gbp": str(undisputed),
                "suggested_state": "DISPUTE_REVIEW",
            },
        )
        return carve_out
