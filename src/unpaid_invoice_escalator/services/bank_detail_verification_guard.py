from __future__ import annotations

from dataclasses import dataclass
import re

from unpaid_invoice_escalator.models import BankDetailVerificationState, ConfirmationOfPayeeResult


@dataclass(frozen=True)
class BankDetailVerificationDecision:
    allowed: bool
    reason: str | None = None


class BankDetailVerificationGuard:
    def authorize_update(
        self,
        *,
        updated_by: str,
        mfa_reauthenticated: bool,
        dual_control_approved_by: str | None,
        dual_control_approval_reference: str | None,
    ) -> BankDetailVerificationDecision:
        if mfa_reauthenticated:
            return BankDetailVerificationDecision(allowed=True)
        approver = (dual_control_approved_by or "").strip()
        reference = (dual_control_approval_reference or "").strip()
        if not approver or not reference:
            return BankDetailVerificationDecision(
                allowed=False,
                reason="Bank detail update requires MFA re-authentication or dual-control approval.",
            )
        if approver == updated_by.strip():
            return BankDetailVerificationDecision(
                allowed=False,
                reason="Dual-control approver must be different from the user requesting update.",
            )
        return BankDetailVerificationDecision(allowed=True)

    def evaluate_cop(
        self, *, expected_payee_name: str | None, account_holder_name: str
    ) -> tuple[ConfirmationOfPayeeResult | None, BankDetailVerificationState]:
        expected = self._normalize_name(expected_payee_name or "")
        holder = self._normalize_name(account_holder_name)
        if not expected:
            return (None, BankDetailVerificationState.COP_UNVERIFIED)
        if holder == expected:
            return (ConfirmationOfPayeeResult.EXACT_MATCH, BankDetailVerificationState.COP_EXACT_MATCH)
        if holder and (holder in expected or expected in holder):
            return (ConfirmationOfPayeeResult.CLOSE_MATCH, BankDetailVerificationState.COP_CLOSE_MATCH)
        return (ConfirmationOfPayeeResult.NO_MATCH, BankDetailVerificationState.COP_FAILED)

    @staticmethod
    def _normalize_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9 ]+", " ", value).upper()
        return " ".join(cleaned.split())
