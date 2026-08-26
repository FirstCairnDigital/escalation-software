from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal, ROUND_HALF_UP

from unpaid_invoice_escalator.models import ClientFeeAction, Invoice
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.rulepacks.fee_loader import CourtFeeSchedule, FeePackLoader, PricingSchedule

TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class ViabilityAssessment:
    company_status: str
    outstanding_amount_gbp: Decimal
    projected_fcd_action_fee_gbp: Decimal
    projected_court_fee_gbp: Decimal
    estimated_time_cost_gbp: Decimal
    projected_total_cost_gbp: Decimal
    cost_ratio: Decimal
    disproportionate: bool
    notice: str | None
    recommendation: str
    blocked: bool


class ViabilityProportionalityCalculator:
    def __init__(self, *, store: SQLiteStore, fee_loader: FeePackLoader | None = None) -> None:
        self._store = store
        self._fee_loader = fee_loader or FeePackLoader()

    def assess(
        self,
        *,
        invoice: Invoice,
        on_date: date,
        projected_action: ClientFeeAction = ClientFeeAction.PRE_ACTION_PACK,
        estimated_time_cost_gbp: Decimal = Decimal("0"),
        company_status: str = "UNKNOWN",
    ) -> ViabilityAssessment:
        normalized_status = company_status.strip().upper() if company_status.strip() else "UNKNOWN"
        outstanding = self._store.debtor_ledger_balance_for_invoice(invoice.invoice_id)
        if outstanding <= Decimal("0.00"):
            blocked = normalized_status in {"INSOLVENT", "DISSOLVED", "IN_ADMINISTRATION", "CEASED"}
            return ViabilityAssessment(
                company_status=normalized_status,
                outstanding_amount_gbp=Decimal("0.00"),
                projected_fcd_action_fee_gbp=Decimal("0.00"),
                projected_court_fee_gbp=Decimal("0.00"),
                estimated_time_cost_gbp=Decimal("0.00"),
                projected_total_cost_gbp=Decimal("0.00"),
                cost_ratio=Decimal("0.00"),
                disproportionate=False,
                notice=None,
                recommendation=(
                    "Entity appears financially distressed. Transition to CLIENT_HANDOFF for specialist review."
                    if blocked
                    else "No outstanding balance available for escalation."
                ),
                blocked=blocked,
            )
        schedule = self._load_pricing_schedule_resolved(on_date)
        action_fee = schedule.action_fees.get(projected_action, Decimal("0.00")).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        court_fee = self._quote_court_fee_resolved(invoice=invoice, outstanding=outstanding, on_date=on_date).quantize(
            TWOPLACES, rounding=ROUND_HALF_UP
        )
        time_cost = estimated_time_cost_gbp.quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        total_cost = (action_fee + court_fee + time_cost).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        ratio = Decimal("0.00")
        if outstanding > Decimal("0.00"):
            ratio = (total_cost / outstanding).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)

        blocked = normalized_status in {"INSOLVENT", "DISSOLVED", "IN_ADMINISTRATION", "CEASED"}
        disproportionate = (ratio >= Decimal("0.50")) or (total_cost >= outstanding)
        notice = None
        recommendation = "Proceed with standard resolution workflow."
        if blocked:
            recommendation = "Entity appears financially distressed. Transition to CLIENT_HANDOFF for specialist review."
        elif disproportionate:
            notice = f"Recovery costs and effort may be disproportionate to the amount outstanding (£{outstanding})."
            recommendation = "Prefer settlement-focused resolution or creditor review before escalation."

        return ViabilityAssessment(
            company_status=normalized_status,
            outstanding_amount_gbp=outstanding.quantize(TWOPLACES, rounding=ROUND_HALF_UP),
            projected_fcd_action_fee_gbp=action_fee,
            projected_court_fee_gbp=court_fee,
            estimated_time_cost_gbp=time_cost,
            projected_total_cost_gbp=total_cost,
            cost_ratio=ratio,
            disproportionate=disproportionate,
            notice=notice,
            recommendation=recommendation,
            blocked=blocked,
        )

    def _load_pricing_schedule_resolved(self, on_date: date) -> PricingSchedule:
        try:
            return self._fee_loader.load_pricing_schedule(on_date)
        except ValueError:
            return self._fee_loader.load_pricing_schedule(date(2100, 1, 1))

    def _quote_court_fee_resolved(self, *, invoice: Invoice, outstanding: Decimal, on_date: date) -> Decimal:
        try:
            return self._fee_loader.quote_court_fee(invoice.jurisdiction, outstanding, on_date)
        except ValueError:
            try:
                return self._fee_loader.quote_court_fee(invoice.jurisdiction, outstanding, date(2100, 1, 1))
            except ValueError:
                schedule = self._fee_loader.load_court_fee_schedule(invoice.jurisdiction, date(2100, 1, 1))
                return self._estimate_from_court_schedule(schedule=schedule, claim_value=outstanding)

    @staticmethod
    def _estimate_from_court_schedule(*, schedule: CourtFeeSchedule, claim_value: Decimal) -> Decimal:
        # Fallback for sparse fee bands: choose the nearest lower fixed fee band, or percentage if available.
        candidate: Decimal | None = None
        for band in schedule.fee_bands:
            if band.min_claim > claim_value:
                continue
            if band.fixed_fee is not None:
                candidate = band.fixed_fee
            elif band.percentage_rate is not None:
                candidate = (claim_value * band.percentage_rate).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        if candidate is not None:
            return candidate
        first = schedule.fee_bands[0]
        if first.fixed_fee is not None:
            return first.fixed_fee
        if first.percentage_rate is not None:
            return (claim_value * first.percentage_rate).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        return Decimal("0.00")
