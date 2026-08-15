from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DevilsAdvocateResult:
    blocked: bool
    reasons: tuple[str, ...]
    recommended_actions: tuple[str, ...]


class DevilsAdvocateEngine:
    def evaluate(
        self,
        *,
        active_dispute: bool,
        payment_or_credit_discrepancy: bool,
        delivery_evidence_unverified: bool,
        settlement_pending_and_not_due: bool,
        data_accuracy_challenge_pending: bool,
        insolvency_or_breathing_space_flag: bool,
    ) -> DevilsAdvocateResult:
        reasons: list[str] = []
        actions: list[str] = []
        if active_dispute:
            reasons.append("Active dispute detected.")
            actions.append("Resolve or document dispute outcome before escalation.")
        if payment_or_credit_discrepancy:
            reasons.append("Payment or credit discrepancy detected.")
            actions.append("Reconcile payments/credits and issue corrected statement.")
        if delivery_evidence_unverified:
            reasons.append("Delivery or acceptance evidence is unverified.")
            actions.append("Upload verifiable delivery/acceptance proof.")
        if settlement_pending_and_not_due:
            reasons.append("Settlement or promise-to-pay date has not yet matured.")
            actions.append("Wait for settlement due date or record default before escalation.")
        if data_accuracy_challenge_pending:
            reasons.append("Debtor data-accuracy challenge remains unresolved.")
            actions.append("Address the accuracy challenge and record resolution in compliance ledger.")
        if insolvency_or_breathing_space_flag:
            reasons.append("Insolvency or Breathing Space protection flag is active.")
            actions.append("Freeze automation and proceed via CLIENT_HANDOFF.")
        return DevilsAdvocateResult(
            blocked=bool(reasons),
            reasons=tuple(reasons),
            recommended_actions=tuple(actions),
        )
