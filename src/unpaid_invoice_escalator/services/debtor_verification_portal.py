from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import secrets

from unpaid_invoice_escalator.models import DebtorVerificationCase
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore


@dataclass(frozen=True)
class DebtorVerificationRegistration:
    case_id: str
    verification_code: str
    creditor_name: str
    invoice_reference: str
    created_at: datetime


@dataclass(frozen=True)
class DebtorVerificationResult:
    valid: bool
    message: str
    creditor_name: str | None = None
    invoice_reference: str | None = None
    case_id: str | None = None


class DebtorVerificationPortal:
    def __init__(self, *, store: SQLiteStore) -> None:
        self._store = store

    @staticmethod
    def _hash_code(*, case_id: str, code: str) -> str:
        payload = f"{case_id}:{code.strip().upper()}"
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def _generate_case_id(now: datetime) -> str:
        return f"FCD-R-{now.year}-{secrets.randbelow(1_000_000):06d}"

    @staticmethod
    def _generate_code() -> str:
        return "".join(secrets.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(8))

    def register_case(
        self,
        *,
        invoice_id: str,
        creditor_name: str,
        invoice_reference: str,
    ) -> DebtorVerificationRegistration:
        existing = self._store.debtor_verification_case_for_invoice(invoice_id)
        if existing is not None:
            raise ValueError("Debtor verification case already exists for this invoice.")

        now = datetime.now(timezone.utc)
        case_id = self._generate_case_id(now)
        while self._store.debtor_verification_case_by_case_id(case_id) is not None:
            case_id = self._generate_case_id(now)
        verification_code = self._generate_code()
        verification_code_hash = self._hash_code(case_id=case_id, code=verification_code)
        self._store.append_debtor_verification_case(
            DebtorVerificationCase(
                case_id=case_id,
                invoice_id=invoice_id,
                creditor_name=creditor_name.strip(),
                invoice_reference=invoice_reference.strip(),
                verification_code_hash=verification_code_hash,
                created_at=now,
            )
        )
        return DebtorVerificationRegistration(
            case_id=case_id,
            verification_code=verification_code,
            creditor_name=creditor_name.strip(),
            invoice_reference=invoice_reference.strip(),
            created_at=now,
        )

    def verify(self, *, case_id: str, verification_code: str) -> DebtorVerificationResult:
        record = self._store.debtor_verification_case_by_case_id(case_id.strip())
        if record is None:
            return DebtorVerificationResult(valid=False, message="Verification failed. Case details not recognized.")
        supplied_hash = self._hash_code(case_id=record.case_id, code=verification_code)
        if supplied_hash != record.verification_code_hash:
            return DebtorVerificationResult(valid=False, message="Verification failed. Case details not recognized.")
        return DebtorVerificationResult(
            valid=True,
            case_id=record.case_id,
            creditor_name=record.creditor_name,
            invoice_reference=record.invoice_reference,
            message=(
                "This is a genuine First Cairn Digital communication issued on behalf of "
                f"{record.creditor_name} regarding Invoice {record.invoice_reference}."
            ),
        )
