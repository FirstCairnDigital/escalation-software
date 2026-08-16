from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from unpaid_invoice_escalator.models import LegalHoldType, RetentionVariant


class LegalHoldTaxonomy:
    RETENTION_VARIANTS: dict[str, int] = {
        RetentionVariant.STANDARD_COMMERCIAL.value: 2190,
        RetentionVariant.SCOTTISH_SIMPLE_PROCEDURE.value: 1825,
        RetentionVariant.VAT_TAX_AUDIT.value: 3650,
        RetentionVariant.LEGAL_HOLD_ACTIVE.value: 0,
    }

    ALLOWED_HOLD_TYPES = {member.value for member in LegalHoldType} | {"GENERAL", "LITIGATION_REVIEW", "LEGAL_HOLD_ACTIVE"}

    @classmethod
    def resolve_variant(cls, variant: str | None) -> str:
        candidate = (variant or RetentionVariant.STANDARD_COMMERCIAL.value).upper()
        if candidate in cls.RETENTION_VARIANTS:
            return candidate
        if candidate == RetentionVariant.LEGAL_HOLD_ACTIVE.value:
            return RetentionVariant.LEGAL_HOLD_ACTIVE.value
        raise ValueError(f"Unsupported retention variant '{variant}'.")

    @classmethod
    def validate_hold_record(cls, *, hold_payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(hold_payload, dict):
            raise ValueError("Legal hold payload must be a dictionary.")

        hold_type = str(hold_payload.get("holdType") or hold_payload.get("hold_type") or "").strip()
        if hold_type in {"GENERAL", "LITIGATION_REVIEW"}:
            hold_type = LegalHoldType.LITIGATION_PENDING.value
        if hold_type not in cls.ALLOWED_HOLD_TYPES:
            raise ValueError(
                "Legal hold requires a valid holdType from "
                f"{sorted(cls.ALLOWED_HOLD_TYPES)}. Received: {hold_type or 'missing'}"
            )

        applied_by = hold_payload.get("appliedBy") or hold_payload.get("applied_by")
        if not applied_by:
            raise ValueError("Legal hold requires appliedBy with user/system identifier and timestamp.")

        applied_at = hold_payload.get("appliedAt") or hold_payload.get("timestamp")
        if applied_at is None:
            if not isinstance(applied_by, dict):
                raise ValueError("Legal hold requires appliedAt or timestamp metadata.")
            applied_at = applied_by.get("timestamp")
        if applied_at is None:
            applied_at = datetime.now(timezone.utc).isoformat()

        reason_code = str(hold_payload.get("reasonCode") or hold_payload.get("reason_code") or "").strip()
        if not reason_code:
            raise ValueError("Legal hold requires a non-empty reasonCode.")

        version = hold_payload.get("version")
        if version is None:
            version = 1
        try:
            version = int(version)
        except (TypeError, ValueError):
            raise ValueError("Legal hold version must be an integer.") from None
        if version < 1:
            raise ValueError("Legal hold version must be >= 1.")

        retention_variant = cls.resolve_variant(hold_payload.get("retentionVariant") or hold_payload.get("retention_variant"))

        record = {
            "holdType": hold_type,
            "appliedBy": applied_by,
            "appliedAt": applied_at,
            "reasonCode": reason_code,
            "version": version,
            "retentionVariant": retention_variant,
            "status": RetentionVariant.LEGAL_HOLD_ACTIVE.value,
            "isActive": True,
        }
        return record

    @classmethod
    def audit_warning(cls, *, invoice_id: str, hold_record: dict[str, Any]) -> dict[str, Any]:
        return {
            "invoice_id": invoice_id,
            "warning": "LEGAL_HOLD_ACTIVE prevents deletion and triggers an audit warning.",
            "hold_type": hold_record.get("holdType"),
            "status": hold_record.get("status"),
            "retention_variant": hold_record.get("retentionVariant"),
            "reason_code": hold_record.get("reasonCode"),
            "version": hold_record.get("version"),
        }
