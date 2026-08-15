from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CaseHealthCheckResult:
    confidence: str
    passed_count: int
    total_count: int
    failed_criteria: tuple[str, ...]
    criteria: dict[str, bool]


class CaseHealthCheck:
    _CRITERIA_ORDER = (
        "correct_customer_legal_entity",
        "description_of_goods_or_services",
        "invoice_number_and_date_verified",
        "amount_matches_contract_or_quote",
        "correct_billing_address",
        "vat_numbers_checked",
        "purchase_order_supplied_if_required",
        "payment_terms_and_due_date_established",
        "delivery_or_acceptance_proof_attached",
        "no_unresolved_credit_notes",
        "direct_payments_checked",
        "no_known_dispute",
        "creditor_authority_verified",
        "limitation_period_checked",
        "debtor_contact_details_verified",
        "court_handoff_boundary_acknowledged",
    )
    _STOP_CRITERIA = frozenset(
        (
            "correct_customer_legal_entity",
            "invoice_number_and_date_verified",
            "amount_matches_contract_or_quote",
            "creditor_authority_verified",
            "limitation_period_checked",
            "no_known_dispute",
        )
    )

    def evaluate(self, *, criteria: dict[str, bool]) -> CaseHealthCheckResult:
        normalized = {name: bool(criteria.get(name, False)) for name in self._CRITERIA_ORDER}
        failed = tuple(name for name, passed in normalized.items() if not passed)
        if any(name in self._STOP_CRITERIA for name in failed):
            confidence = "STOP"
        elif failed:
            confidence = "REVIEW"
        else:
            confidence = "READY"
        return CaseHealthCheckResult(
            confidence=confidence,
            passed_count=len(self._CRITERIA_ORDER) - len(failed),
            total_count=len(self._CRITERIA_ORDER),
            failed_criteria=failed,
            criteria=normalized,
        )
