from __future__ import annotations

from dataclasses import dataclass

from unpaid_invoice_escalator.models import RecoveryCostCategory


@dataclass(frozen=True)
class RecoveryCostEligibilityResult:
    category: RecoveryCostCategory
    ruleset: str
    rationale: str


class RecoveryCostEligibilityCalculator:
    @staticmethod
    def assess(
        *,
        has_contractual_recovery_clause: bool,
        is_official_court_fee: bool,
        statutory_reasonable_recovery_allowed: bool,
    ) -> RecoveryCostEligibilityResult:
        if is_official_court_fee:
            return RecoveryCostEligibilityResult(
                category=RecoveryCostCategory.OFFICIAL_COURT_FEE,
                ruleset="OFFICIAL_COURT_FEE",
                rationale="Cost is an official court filing fee under court fee schedule.",
            )
        if has_contractual_recovery_clause:
            return RecoveryCostEligibilityResult(
                category=RecoveryCostCategory.CONTRACTUAL_RECOVERY_COST,
                ruleset="CONTRACTUAL_RECOVERY_COST",
                rationale="Cost may be claimed under explicit contractual recovery clause.",
            )
        if statutory_reasonable_recovery_allowed:
            return RecoveryCostEligibilityResult(
                category=RecoveryCostCategory.STATUTORY_REASONABLE_RECOVERY_COST,
                ruleset="STATUTORY_REASONABLE_RECOVERY_COST",
                rationale="Cost may be claimed as reasonable recovery cost under statutory late payment rules.",
            )
        return RecoveryCostEligibilityResult(
            category=RecoveryCostCategory.CLIENT_COST_ONLY,
            ruleset="CLIENT_COST_ONLY",
            rationale="Cost remains a client-side platform expense and cannot be passed to debtor.",
        )

