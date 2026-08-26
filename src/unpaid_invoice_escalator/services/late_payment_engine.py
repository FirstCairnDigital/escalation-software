from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from unpaid_invoice_escalator.calculators.uk_late_payment import UKLatePaymentBreakdown, UKLatePaymentCalculator
from unpaid_invoice_escalator.models import Actor, DebtorType, Invoice
from unpaid_invoice_escalator.rulepacks import RulePackLoader
from unpaid_invoice_escalator.services.base_rate_provider import BoEBaseRateProvider
from unpaid_invoice_escalator.services.invoice_ledger import InvoiceLedger


@dataclass(frozen=True)
class LatePaymentCalculationResult:
    eligible: bool
    reason: str
    base_rate: Decimal | None
    annual_rate: Decimal | None
    overdue_days: int
    breakdown: UKLatePaymentBreakdown | None
    rule_version: str
    rule_id: str


class LatePaymentEngine:
    def __init__(
        self,
        *,
        ledger: InvoiceLedger,
        rule_pack_loader: RulePackLoader | None = None,
        base_rate_provider: BoEBaseRateProvider | None = None,
    ) -> None:
        self._ledger = ledger
        self._rule_pack_loader = rule_pack_loader or RulePackLoader()
        self._base_rate_provider = base_rate_provider or BoEBaseRateProvider()

    def calculate(
        self,
        *,
        invoice: Invoice,
        as_of_date: date,
        is_commercial_transaction: bool,
        contractual_rate: Decimal | None = None,
        base_rate_override: Decimal | None = None,
        outstanding_amount: Decimal | None = None,
    ) -> LatePaymentCalculationResult:
        pack = self._rule_pack_loader.load_for(invoice.jurisdiction, as_of_date)
        overdue_days = max((as_of_date - invoice.due_date).days, 0)

        if not is_commercial_transaction:
            result = LatePaymentCalculationResult(
                eligible=False,
                reason="Non-commercial transaction: statutory commercial late-payment remedies not applied.",
                base_rate=None,
                annual_rate=None,
                overdue_days=overdue_days,
                breakdown=None,
                rule_version=pack.rule_version,
                rule_id=pack.rule_id,
            )
            self._record(result=result, invoice=invoice, as_of_date=as_of_date, contractual_rate=contractual_rate)
            return result

        if invoice.debtor_type == DebtorType.CONSUMER_CREDIT:
            result = LatePaymentCalculationResult(
                eligible=False,
                reason="Regulated consumer credit is excluded.",
                base_rate=None,
                annual_rate=None,
                overdue_days=overdue_days,
                breakdown=None,
                rule_version=pack.rule_version,
                rule_id=pack.rule_id,
            )
            self._record(result=result, invoice=invoice, as_of_date=as_of_date, contractual_rate=contractual_rate)
            return result

        if overdue_days <= 0:
            result = LatePaymentCalculationResult(
                eligible=False,
                reason="Invoice is not overdue.",
                base_rate=None,
                annual_rate=None,
                overdue_days=overdue_days,
                breakdown=None,
                rule_version=pack.rule_version,
                rule_id=pack.rule_id,
            )
            self._record(result=result, invoice=invoice, as_of_date=as_of_date, contractual_rate=contractual_rate)
            return result

        base_rate = base_rate_override if base_rate_override is not None else self._base_rate_provider.rate_for(invoice.due_date)
        principal = invoice.principal_amount if outstanding_amount is None else outstanding_amount
        breakdown = UKLatePaymentCalculator.calculate(
            principal=principal,
            base_rate=base_rate,
            overdue_days=overdue_days,
            contractual_rate=contractual_rate,
        )
        result = LatePaymentCalculationResult(
            eligible=True,
            reason="Statutory late payment remedy calculation applied.",
            base_rate=base_rate,
            annual_rate=breakdown.annual_rate,
            overdue_days=overdue_days,
            breakdown=breakdown,
            rule_version=pack.rule_version,
            rule_id=pack.rule_id,
        )
        self._record(result=result, invoice=invoice, as_of_date=as_of_date, contractual_rate=contractual_rate)
        return result

    def _record(
        self,
        *,
        result: LatePaymentCalculationResult,
        invoice: Invoice,
        as_of_date: date,
        contractual_rate: Decimal | None,
    ) -> None:
        now = datetime.now(timezone.utc)
        payload: dict[str, object] = {
            "eligible": result.eligible,
            "reason": result.reason,
            "rule_id": result.rule_id,
            "rule_version": result.rule_version,
            "invoice_due_date": invoice.due_date.isoformat(),
            "as_of_date": as_of_date.isoformat(),
            "overdue_days": result.overdue_days,
            "contractual_rate": str(contractual_rate) if contractual_rate is not None else None,
            "base_rate": str(result.base_rate) if result.base_rate is not None else None,
            "annual_rate": str(result.annual_rate) if result.annual_rate is not None else None,
        }
        if result.breakdown is not None:
            payload.update(
                {
                    "daily_interest": str(result.breakdown.daily_interest),
                    "interest_amount": str(result.breakdown.interest_amount),
                    "fixed_compensation": str(result.breakdown.fixed_compensation),
                    "total_recovery": str(result.breakdown.total_recovery),
                }
            )
        self._ledger.append_event(
            invoice_id=invoice.invoice_id,
            actor=Actor.SYSTEM,
            event_type="LATE_PAYMENT_CALCULATION",
            data_payload=payload,
            timestamp=now,
        )
