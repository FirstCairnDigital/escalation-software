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
    PaymentPlanInstallment,
    PaymentPlanPayment,
    SettlementAcceptance,
    SettlementOffer,
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


class ResolutionAndSettlementEngine:
    def __init__(self, *, store: SQLiteStore, event_ledger: InvoiceLedger) -> None:
        self._store = store
        self._event_ledger = event_ledger

    def propose_payment_plan(
        self,
        *,
        invoice_id: str,
        proposed_by: str,
        installment_amount_gbp: Decimal,
        installment_count: int,
        first_due_date: date,
        frequency_days: int,
        notes: str = "",
    ) -> tuple[PaymentPlanAgreement, tuple[PaymentPlanInstallment, ...]]:
        if installment_count < 1:
            raise ValueError("installment_count must be >= 1.")
        if frequency_days < 1:
            raise ValueError("frequency_days must be >= 1.")
        amount = installment_amount_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if amount <= Decimal("0.00"):
            raise ValueError("installment_amount_gbp must be > 0.")
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
            actor=Actor.CLIENT,
            event_type="PAYMENT_PLAN_PROPOSED",
            timestamp=now,
            data_payload={
                "plan_id": plan.plan_id,
                "proposed_by": proposed_by,
                "installment_amount_gbp": str(amount),
                "installment_count": installment_count,
                "first_due_date": first_due_date.isoformat(),
                "frequency_days": frequency_days,
            },
        )
        return plan, installments

    def record_installment_payment(
        self,
        *,
        invoice_id: str,
        plan_id: str,
        installment_id: str,
        amount_gbp: Decimal,
        recorded_by: str,
    ) -> PaymentPlanPayment:
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
        )
        self._store.append_payment_plan_payment(payment)
        debtor_entry = DebtorLedgerEntry(
            entry_id=str(uuid4()),
            invoice_id=invoice_id,
            timestamp=now,
            entry_type=DebtorLedgerEntryType.PAYMENT_RECEIVED,
            amount_gbp=-amount,
            description=f"Payment plan installment received (plan {plan_id}, installment {installment_id}).",
        )
        self._store.append_debtor_ledger_entry(debtor_entry)
        self._event_ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.DEBTOR,
            event_type="PAYMENT_PLAN_INSTALLMENT_RECORDED",
            timestamp=now,
            data_payload={
                "plan_id": plan_id,
                "installment_id": installment_id,
                "amount_gbp": str(amount),
                "recorded_by": recorded_by,
                "automation_cancelled_pending_communications": True,
            },
        )
        return payment

    def payment_plan_status(self, *, plan_id: str, as_of_date: date) -> PaymentPlanStatus:
        installments = self._store.payment_plan_installments_for_plan(plan_id)
        payments = self._store.payment_plan_payments_for_plan(plan_id)
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
                if installment.due_date < as_of_date:
                    missed_count += 1
        if all_paid:
            status = "COMPLETED"
        elif missed_count > 0:
            status = "DEFAULTED"
        else:
            status = "ACTIVE"
        remaining = max(Decimal("0.00"), total - paid)
        return PaymentPlanStatus(
            plan_id=plan_id,
            status=status,
            total_amount_gbp=total.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            paid_amount_gbp=paid.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            remaining_amount_gbp=remaining.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            missed_installment_count=missed_count,
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
        all_roles = {item.accepter_role for item in existing} | {normalized_role}
        finalized = all_roles == {"DEBTOR", "CREDITOR"}
        self._event_ledger.append_event(
            invoice_id=offer.invoice_id,
            actor=Actor.CLIENT if normalized_role == "CREDITOR" else Actor.DEBTOR,
            event_type="SETTLEMENT_OFFER_ACCEPTED",
            timestamp=now,
            data_payload={"offer_id": offer_id, "accepter_role": normalized_role, "accepted_by": accepted_by},
        )
        if finalized:
            self._finalize_settlement_offer(offer=offer, finalized_at=now)
        return acceptance, finalized

    def _finalize_settlement_offer(self, *, offer: SettlementOffer, finalized_at: datetime) -> None:
        outstanding_before = self._store.debtor_ledger_balance_for_invoice(offer.invoice_id)
        discount = outstanding_before - offer.offered_amount_gbp
        if discount > Decimal("0.00"):
            self._store.append_debtor_ledger_entry(
                DebtorLedgerEntry(
                    entry_id=str(uuid4()),
                    invoice_id=offer.invoice_id,
                    timestamp=finalized_at,
                    entry_type=DebtorLedgerEntryType.SETTLEMENT_DISCOUNT,
                    amount_gbp=-discount.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
                    description=f"Full and final settlement discount for offer {offer.offer_id}.",
                )
            )
        self._event_ledger.append_event(
            invoice_id=offer.invoice_id,
            actor=Actor.SYSTEM,
            event_type="SETTLEMENT_OFFER_FINALIZED",
            timestamp=finalized_at,
            data_payload={
                "offer_id": offer.offer_id,
                "offered_amount_gbp": str(offer.offered_amount_gbp),
                "outstanding_before_gbp": str(outstanding_before),
                "settlement_discount_applied_gbp": str(max(Decimal("0.00"), discount)),
            },
        )

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
