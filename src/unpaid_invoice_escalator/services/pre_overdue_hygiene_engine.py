from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from uuid import uuid4

from unpaid_invoice_escalator.models import PreOverdueHygieneRecord


@dataclass(frozen=True)
class PreOverdueHygieneAssessment:
    checklist_complete: bool
    missing_items: tuple[str, ...]
    warning_tier: str
    format_warnings: tuple[str, ...]
    suggested_clause_requires_legal_review: bool
    disclaimer: str | None


class PreOverdueHygieneEngine:
    LEGAL_REVIEW_DISCLAIMER = "Requires Client Independent Legal Review"
    _COMPANIES_HOUSE_RE = re.compile(r"^(?:\d{8}|[A-Z]{2}\d{6})$")
    _VAT_RE = re.compile(r"^(?:GB(?:\d{9}|\d{12}|GD\d{3}|HA\d{3})|\d{9})$")

    def assess(
        self,
        *,
        creditor_legal_entity_name: str,
        creditor_companies_house_number: str,
        creditor_vat_number: str,
        creditor_trading_address: str,
        debtor_legal_entity_name: str,
        debtor_companies_house_number: str,
        debtor_vat_number: str,
        debtor_trading_address: str,
        po_required: bool,
        po_reference: str | None,
        payment_terms_days: int,
        contractual_interest_clause_present: bool,
        contractual_recovery_clause_present: bool,
        proof_of_delivery_required: bool,
        suggested_clause_text: str | None,
    ) -> PreOverdueHygieneAssessment:
        missing_items: list[str] = []
        format_warnings: list[str] = []
        if not creditor_legal_entity_name.strip():
            missing_items.append("Creditor legal entity name")
        ch_number = creditor_companies_house_number.strip().upper()
        if not ch_number:
            missing_items.append("Creditor Companies House number")
        elif not self._COMPANIES_HOUSE_RE.match(ch_number):
            format_warnings.append(
                "Creditor Companies House number format is non-standard (expected 8 digits or 2 letters + 6 digits)."
            )
        vat_number = creditor_vat_number.strip().upper().replace(" ", "")
        if not vat_number:
            missing_items.append("Creditor VAT number")
        elif not self._VAT_RE.match(vat_number):
            format_warnings.append(
                "Creditor VAT number format is non-standard (expected GB prefix with valid UK pattern or 9 digits)."
            )
        if not creditor_trading_address.strip():
            missing_items.append("Creditor trading address")
        if not debtor_legal_entity_name.strip():
            missing_items.append("Debtor legal entity name")
        debtor_ch_number = debtor_companies_house_number.strip().upper()
        if not debtor_ch_number:
            missing_items.append("Debtor Companies House number")
        elif not self._COMPANIES_HOUSE_RE.match(debtor_ch_number):
            format_warnings.append(
                "Debtor Companies House number format is non-standard (expected 8 digits or 2 letters + 6 digits)."
            )
        debtor_vat = debtor_vat_number.strip().upper().replace(" ", "")
        if not debtor_vat:
            missing_items.append("Debtor VAT number")
        elif not self._VAT_RE.match(debtor_vat):
            format_warnings.append(
                "Debtor VAT number format is non-standard (expected GB prefix with valid UK pattern or 9 digits)."
            )
        if not debtor_trading_address.strip():
            missing_items.append("Debtor trading address")
        if po_required and not (po_reference or "").strip():
            missing_items.append("Purchase order reference")
        if payment_terms_days <= 0:
            missing_items.append("Payment terms (days)")
        if not contractual_interest_clause_present:
            missing_items.append("Contractual late-payment interest clause")
        if not contractual_recovery_clause_present:
            missing_items.append("Contractual recovery charges clause")
        if not proof_of_delivery_required:
            missing_items.append("Proof-of-delivery/acceptance requirement")

        requires_legal_review = bool((suggested_clause_text or "").strip())
        if len(format_warnings) >= 2:
            warning_tier = "HIGH"
        elif len(format_warnings) == 1:
            warning_tier = "MEDIUM"
        else:
            warning_tier = "NONE"
        return PreOverdueHygieneAssessment(
            checklist_complete=len(missing_items) == 0,
            missing_items=tuple(missing_items),
            warning_tier=warning_tier,
            format_warnings=tuple(format_warnings),
            suggested_clause_requires_legal_review=requires_legal_review,
            disclaimer=self.LEGAL_REVIEW_DISCLAIMER if requires_legal_review else None,
        )

    def build_record(
        self,
        *,
        invoice_id: str,
        creditor_legal_entity_name: str,
        creditor_companies_house_number: str,
        creditor_vat_number: str,
        creditor_trading_address: str,
        debtor_legal_entity_name: str,
        debtor_companies_house_number: str,
        debtor_vat_number: str,
        debtor_trading_address: str,
        po_required: bool,
        po_reference: str | None,
        payment_terms_days: int,
        contractual_interest_clause_present: bool,
        contractual_recovery_clause_present: bool,
        proof_of_delivery_required: bool,
        suggested_clause_text: str | None,
        notes: str,
    ) -> tuple[PreOverdueHygieneRecord, PreOverdueHygieneAssessment]:
        assessment = self.assess(
            creditor_legal_entity_name=creditor_legal_entity_name,
            creditor_companies_house_number=creditor_companies_house_number,
            creditor_vat_number=creditor_vat_number,
            creditor_trading_address=creditor_trading_address,
            debtor_legal_entity_name=debtor_legal_entity_name,
            debtor_companies_house_number=debtor_companies_house_number,
            debtor_vat_number=debtor_vat_number,
            debtor_trading_address=debtor_trading_address,
            po_required=po_required,
            po_reference=po_reference,
            payment_terms_days=payment_terms_days,
            contractual_interest_clause_present=contractual_interest_clause_present,
            contractual_recovery_clause_present=contractual_recovery_clause_present,
            proof_of_delivery_required=proof_of_delivery_required,
            suggested_clause_text=suggested_clause_text,
        )
        record = PreOverdueHygieneRecord(
            record_id=str(uuid4()),
            invoice_id=invoice_id,
            timestamp=datetime.now(timezone.utc),
            creditor_legal_entity_name=creditor_legal_entity_name.strip(),
            creditor_companies_house_number=creditor_companies_house_number.strip(),
            creditor_vat_number=creditor_vat_number.strip(),
            creditor_trading_address=creditor_trading_address.strip(),
            debtor_legal_entity_name=debtor_legal_entity_name.strip(),
            debtor_companies_house_number=debtor_companies_house_number.strip(),
            debtor_vat_number=debtor_vat_number.strip(),
            debtor_trading_address=debtor_trading_address.strip(),
            po_required=po_required,
            po_reference=(po_reference or "").strip() or None,
            payment_terms_days=payment_terms_days,
            contractual_interest_clause_present=contractual_interest_clause_present,
            contractual_recovery_clause_present=contractual_recovery_clause_present,
            proof_of_delivery_required=proof_of_delivery_required,
            suggested_clause_text=(suggested_clause_text or "").strip() or None,
            suggested_clause_requires_legal_review=assessment.suggested_clause_requires_legal_review,
            checklist_complete=assessment.checklist_complete,
            missing_items=assessment.missing_items,
            warning_tier=assessment.warning_tier,
            format_warnings=assessment.format_warnings,
            notes=notes.strip(),
        )
        return record, assessment
