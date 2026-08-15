from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP


TWOPLACES = Decimal("0.01")


@dataclass(frozen=True)
class UKLatePaymentBreakdown:
    annual_rate: Decimal
    daily_interest: Decimal
    overdue_days: int
    interest_amount: Decimal
    fixed_compensation: Decimal
    total_recovery: Decimal


class UKLatePaymentCalculator:
    @staticmethod
    def annual_rate(base_rate: Decimal, contractual_rate: Decimal | None = None) -> Decimal:
        if contractual_rate is not None:
            return contractual_rate
        return base_rate + Decimal("0.08")

    @staticmethod
    def daily_interest(principal: Decimal, annual_rate: Decimal) -> Decimal:
        value = (principal * annual_rate) / Decimal("365")
        return value.quantize(TWOPLACES, rounding=ROUND_HALF_UP)

    @staticmethod
    def fixed_compensation(principal: Decimal) -> Decimal:
        if principal < Decimal("1000"):
            return Decimal("40")
        if principal < Decimal("10000"):
            return Decimal("70")
        return Decimal("100")

    @classmethod
    def calculate(
        cls,
        principal: Decimal,
        base_rate: Decimal,
        overdue_days: int,
        contractual_rate: Decimal | None = None,
    ) -> UKLatePaymentBreakdown:
        if overdue_days < 0:
            raise ValueError("overdue_days must be >= 0")

        annual = cls.annual_rate(base_rate=base_rate, contractual_rate=contractual_rate)
        daily = cls.daily_interest(principal=principal, annual_rate=annual)
        interest_amount = (daily * Decimal(overdue_days)).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
        compensation = cls.fixed_compensation(principal=principal)
        total = (interest_amount + compensation).quantize(TWOPLACES, rounding=ROUND_HALF_UP)

        return UKLatePaymentBreakdown(
            annual_rate=annual,
            daily_interest=daily,
            overdue_days=overdue_days,
            interest_amount=interest_amount,
            fixed_compensation=compensation,
            total_recovery=total,
        )

