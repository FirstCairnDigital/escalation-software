from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


@dataclass(frozen=True)
class DiscrepancyValidationResult:
    valid: bool
    status: str
    reasons: tuple[str, ...]
    circuit_breaker_triggered: bool
    suggested_state: str | None


class DataDiscrepancyValidator:
    def validate(
        self,
        *,
        claim_amount: Decimal,
        evidence_document_amount: Decimal,
        principal: Decimal,
        payments_recorded: Decimal,
        outstanding_entered: Decimal,
    ) -> DiscrepancyValidationResult:
        reasons: list[str] = []
        if claim_amount != evidence_document_amount:
            reasons.append("Invoice discrepancy: claim amount does not match evidence document amount.")
        if (principal - payments_recorded) != outstanding_entered:
            reasons.append("Payment math discrepancy: principal - payments does not match outstanding entered.")

        if reasons:
            return DiscrepancyValidationResult(
                valid=False,
                status="AUTOMATION_STOPPED_DISCREPANCY",
                reasons=tuple(reasons),
                circuit_breaker_triggered=True,
                suggested_state="CLIENT_HANDOFF",
            )
        return DiscrepancyValidationResult(
            valid=True,
            status="VALIDATED",
            reasons=(),
            circuit_breaker_triggered=False,
            suggested_state=None,
        )
