from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
import json
import os
from pathlib import Path
import re
import sqlite3
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from unpaid_invoice_escalator.models import (
    Actor,
    ArtifactType,
    ClientFeeAction,
    CommunicationDeliveryState,
    ComplianceLedgerEntry,
    DebtorLedgerEntryType,
    DebtorType,
    EvidenceArtifact,
    Invoice,
    InvoiceState,
    Jurisdiction,
    RecoveryCostCategory,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.rulepacks import RulePackLoader, RulePackValidationError
from unpaid_invoice_escalator.services.dual_ledger_engine import DualLedgerEngine
from unpaid_invoice_escalator.services.case_health_check import CaseHealthCheck
from unpaid_invoice_escalator.services.communication_delivery_tracker import CommunicationDeliveryTracker
from unpaid_invoice_escalator.services.communication_severity_engine import CommunicationSeverityEngine
from unpaid_invoice_escalator.services.data_discrepancy_validator import DataDiscrepancyValidator
from unpaid_invoice_escalator.services.debtor_verification_portal import DebtorVerificationPortal
from unpaid_invoice_escalator.services.devils_advocate_engine import DevilsAdvocateEngine
from unpaid_invoice_escalator.services.escalation_runner import EscalationRunner
from unpaid_invoice_escalator.services.five_ledger_engine import FiveLedgerEngine
from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts
from unpaid_invoice_escalator.services.ledger_manifest_exporter import LedgerManifestExporter
from unpaid_invoice_escalator.services.late_payment_engine import LatePaymentEngine
from unpaid_invoice_escalator.services.legal_safety_gate_manager import LegalSafetyGateManager
from unpaid_invoice_escalator.services.pre_overdue_hygiene_engine import PreOverdueHygieneEngine
from unpaid_invoice_escalator.services.resolution_settlement_engine import ResolutionAndSettlementEngine
from unpaid_invoice_escalator.services.resolution_artifact_generator import ResolutionArtifactGenerator
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger
from unpaid_invoice_escalator.services.viability_proportionality_calculator import ViabilityProportionalityCalculator
from unpaid_invoice_escalator.security import ApiSecurityController, ROLE_RANK
from unpaid_invoice_escalator.ui import render_home_html, render_invoice_workspace_html

SAFE_UPLOAD_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class InvoiceCreateRequest(BaseModel):
    invoice_id: str
    currency: str = "GBP"
    principal_amount: Decimal
    issue_date: date
    due_date: date
    jurisdiction: Jurisdiction
    debtor_type: DebtorType

    model_config = ConfigDict(use_enum_values=False)


class EscalateRequest(BaseModel):
    today: date
    current_state: InvoiceState | None = None
    state_entered_on: date | None = None
    debtor_feedback: str | None = None
    system_flag: str | None = None
    insolvency_flag: bool = False
    payment_plan_proposed: bool = False
    partially_paid: bool = False
    regulated_debt_suspected: bool = False
    settlement_pending_and_not_due: bool = False
    delivery_evidence_unverified: bool = False
    company_status: str = "UNKNOWN"
    estimated_time_cost_gbp: Decimal = Decimal("0")
    projected_action: ClientFeeAction = ClientFeeAction.PRE_ACTION_PACK
    contract_jurisdiction: Jurisdiction | None = None
    creditor_country_code: str | None = None
    debtor_country_code: str | None = None
    place_of_supply_country_code: str | None = None


class BundleRequest(BaseModel):
    communications: list[str] = Field(default_factory=list)
    formal_notices: list[str] = Field(default_factory=list)
    include_resolution_artifacts: bool = True
    output_filename: str = "evidence_bundle.pdf"


class ManifestRequest(BaseModel):
    output_filename: str = "ledger_manifest.json"
    output_format: Literal["json", "pdf"] = "json"


class ManifestVerifyRequest(BaseModel):
    output_filename: str = "ledger_manifest.json"


class LatePaymentRequest(BaseModel):
    as_of_date: date
    is_commercial_transaction: bool = True
    contractual_rate: Decimal | None = None
    base_rate_override: Decimal | None = None


class ClientFeeActionRequest(BaseModel):
    case_id: str
    client_id: str
    action_selected: ClientFeeAction
    accepted_by_user: str


class DebtorLedgerEntryRequest(BaseModel):
    entry_type: DebtorLedgerEntryType
    amount_gbp: Decimal
    description: str
    recovery_cost_category: RecoveryCostCategory | None = None
    linked_client_fee_entry_id: str | None = None


class RecoveryCostAssessmentRequest(BaseModel):
    recovery_cost_gbp: Decimal
    has_contractual_recovery_clause: bool = False
    is_official_court_fee: bool = False
    statutory_reasonable_recovery_allowed: bool = False


class CourtFeeQuoteRequest(BaseModel):
    claim_value_gbp: Decimal


class PreOverdueHygieneRequest(BaseModel):
    creditor_legal_entity_name: str
    creditor_companies_house_number: str
    creditor_vat_number: str
    creditor_trading_address: str
    debtor_legal_entity_name: str
    debtor_companies_house_number: str
    debtor_vat_number: str
    debtor_trading_address: str
    po_required: bool = False
    po_reference: str | None = None
    payment_terms_days: int = 30
    contractual_interest_clause_present: bool = False
    contractual_recovery_clause_present: bool = False
    proof_of_delivery_required: bool = True
    suggested_clause_text: str | None = None
    notes: str = ""


class LegalSafetyGateConfirmRequest(BaseModel):
    user_id: str
    amount_claimed_gbp: Decimal
    payments_recorded_gbp: Decimal = Decimal("0")
    authorised_to_act: bool
    info_accurate: bool
    invoice_unpaid: bool
    payments_recorded_complete: bool
    genuine_supporting_docs: bool
    no_unresolved_dispute: bool
    commercial_not_excluded: bool


class DiscrepancyCheckRequest(BaseModel):
    claim_amount: Decimal
    evidence_document_amount: Decimal
    principal: Decimal
    payments_recorded: Decimal
    outstanding_entered: Decimal


class CaseHealthCheckRequest(BaseModel):
    user_id: str
    correct_customer_legal_entity: bool
    description_of_goods_or_services: bool
    invoice_number_and_date_verified: bool
    amount_matches_contract_or_quote: bool
    correct_billing_address: bool
    vat_numbers_checked: bool
    purchase_order_supplied_if_required: bool
    payment_terms_and_due_date_established: bool
    delivery_or_acceptance_proof_attached: bool
    no_unresolved_credit_notes: bool
    direct_payments_checked: bool
    no_known_dispute: bool
    creditor_authority_verified: bool
    limitation_period_checked: bool
    debtor_contact_details_verified: bool
    court_handoff_boundary_acknowledged: bool


class DevilsAdvocateCheckRequest(BaseModel):
    active_dispute: bool = False
    payment_or_credit_discrepancy: bool = False
    delivery_evidence_unverified: bool = False
    settlement_pending_and_not_due: bool = False
    data_accuracy_challenge_pending: bool = False
    insolvency_or_breathing_space_flag: bool = False


class DebtorVerificationRegisterRequest(BaseModel):
    creditor_name: str
    invoice_reference: str | None = None


class DataAccuracyChallengeRequest(BaseModel):
    debtor_identifier: str
    challenge_reason: str
    challenge_details: str


class ResolveDataAccuracyChallengeRequest(BaseModel):
    creditor_user_id: str
    resolution_notes: str


class PaymentPlanProposalRequest(BaseModel):
    proposed_by: str
    installment_amount_gbp: Decimal
    installment_count: int
    first_due_date: date
    frequency_days: int = 30
    notes: str = ""


class PaymentPlanPaymentRequest(BaseModel):
    installment_id: str
    amount_gbp: Decimal
    recorded_by: str


class SettlementOfferRequest(BaseModel):
    offered_by: str
    offered_amount_gbp: Decimal
    expiry_date: date
    notes: str = ""


class SettlementAcceptanceRequest(BaseModel):
    accepted_by: str
    accepter_role: Literal["DEBTOR", "CREDITOR"]


class DisputeCarveOutRequest(BaseModel):
    disputed_amount_gbp: Decimal
    reason: str
    created_by: str


class ViabilityAssessmentRequest(BaseModel):
    on_date: date
    projected_action: ClientFeeAction = ClientFeeAction.PRE_ACTION_PACK
    estimated_time_cost_gbp: Decimal = Decimal("0")
    company_status: str = "UNKNOWN"


class PromiseToPayArtifactRequest(BaseModel):
    plan_id: str
    output_filename: str = "promise_to_pay.pdf"


class SettlementAgreementArtifactRequest(BaseModel):
    offer_id: str
    output_filename: str = "full_final_settlement.pdf"


class CommunicationCreateRequest(BaseModel):
    channel: str
    recipient: str
    subject: str
    body_summary: str
    automated: bool = True


class CommunicationDeliveryUpdateRequest(BaseModel):
    state: CommunicationDeliveryState
    note: str = ""


def _parse_api_keys(raw: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError("FCD_API_KEYS entries must use format key:role")
        key, role = token.split(":", 1)
        normalized_role = role.strip().lower()
        if normalized_role not in ROLE_RANK:
            raise ValueError(f"Unsupported API role: {normalized_role}")
        keys[key.strip()] = normalized_role
    return keys


def _parse_key_map(raw: str, *, field_name: str) -> dict[str, str]:
    keys: dict[str, str] = {}
    for item in raw.split(","):
        token = item.strip()
        if not token:
            continue
        if ":" not in token:
            raise ValueError(f"{field_name} entries must use format key_id:key_material")
        key_id, key_value = token.split(":", 1)
        normalized_key_id = key_id.strip()
        normalized_key = key_value.strip()
        if not normalized_key_id or not normalized_key:
            raise ValueError(f"{field_name} entries must include non-empty key_id and key material")
        keys[normalized_key_id] = normalized_key
    return keys


def _parse_csv_tokens(raw: str) -> tuple[str, ...]:
    return tuple(token.strip() for token in raw.split(",") if token.strip())


def create_app(
    *,
    db_path: str = "data/escalator.db",
    artifacts_dir: str = "data/artifacts",
    bundles_dir: str = "data/bundles",
    manifest_signing_key: str = "dev-only-signing-key",
    manifest_key_id: str = "fcd-local-key",
    app_env: str | None = None,
    auth_enabled: bool | None = None,
    api_keys: dict[str, str] | None = None,
    rate_limit_per_minute: int | None = None,
    manifest_verification_keys: dict[str, str] | None = None,
    auth_failure_alert_threshold: int | None = None,
    rate_limit_alert_threshold: int | None = None,
    server_error_alert_threshold: int | None = None,
    max_upload_bytes: int | None = None,
    allowed_upload_content_types: tuple[str, ...] | None = None,
    allowed_upload_extensions: tuple[str, ...] | None = None,
    quarantine_dir: str | None = None,
) -> FastAPI:
    effective_env = (app_env or os.getenv("FCD_APP_ENV", "development")).strip().lower()
    if manifest_signing_key == "dev-only-signing-key":
        manifest_signing_key = os.getenv("FCD_MANIFEST_SIGNING_KEY", manifest_signing_key)
    manifest_key_id = os.getenv("FCD_MANIFEST_KEY_ID", manifest_key_id)
    if effective_env == "production" and manifest_signing_key == "dev-only-signing-key":
        raise ValueError("Production mode requires FCD_MANIFEST_SIGNING_KEY or explicit manifest_signing_key.")

    effective_auth_enabled = auth_enabled if auth_enabled is not None else effective_env == "production"
    configured_keys = api_keys
    if configured_keys is None:
        raw_api_keys = os.getenv("FCD_API_KEYS", "")
        configured_keys = _parse_api_keys(raw_api_keys) if raw_api_keys.strip() else {}
    if effective_auth_enabled and not configured_keys:
        raise ValueError("Authentication is enabled but no API keys were configured.")

    effective_rate_limit = rate_limit_per_minute
    if effective_rate_limit is None:
        effective_rate_limit = int(os.getenv("FCD_RATE_LIMIT_PER_MINUTE", "120"))
    verification_keys = dict(manifest_verification_keys or {})
    if not verification_keys:
        raw_verification_keys = os.getenv("FCD_MANIFEST_VERIFY_KEYS", "")
        if raw_verification_keys.strip():
            verification_keys = _parse_key_map(raw_verification_keys, field_name="FCD_MANIFEST_VERIFY_KEYS")
    verification_keys.setdefault(manifest_key_id, manifest_signing_key)

    effective_auth_failure_threshold = auth_failure_alert_threshold
    if effective_auth_failure_threshold is None:
        effective_auth_failure_threshold = int(os.getenv("FCD_AUTH_FAILURE_ALERT_THRESHOLD", "10"))
    effective_rate_limit_threshold = rate_limit_alert_threshold
    if effective_rate_limit_threshold is None:
        effective_rate_limit_threshold = int(os.getenv("FCD_RATE_LIMIT_ALERT_THRESHOLD", "10"))
    effective_server_error_threshold = server_error_alert_threshold
    if effective_server_error_threshold is None:
        effective_server_error_threshold = int(os.getenv("FCD_SERVER_ERROR_ALERT_THRESHOLD", "5"))
    effective_max_upload_bytes = max_upload_bytes
    if effective_max_upload_bytes is None:
        effective_max_upload_bytes = int(os.getenv("FCD_MAX_UPLOAD_BYTES", "5242880"))
    effective_allowed_upload_content_types = allowed_upload_content_types
    if effective_allowed_upload_content_types is None:
        raw_upload_types = os.getenv(
            "FCD_ALLOWED_UPLOAD_CONTENT_TYPES",
            "application/pdf,text/plain,image/png,image/jpeg",
        )
        effective_allowed_upload_content_types = _parse_csv_tokens(raw_upload_types)
    allowed_upload_content_type_set = {item.lower() for item in effective_allowed_upload_content_types}
    effective_allowed_upload_extensions = allowed_upload_extensions
    if effective_allowed_upload_extensions is None:
        raw_upload_extensions = os.getenv("FCD_ALLOWED_UPLOAD_EXTENSIONS", ".pdf,.txt,.png,.jpg,.jpeg")
        effective_allowed_upload_extensions = tuple(token.lower() for token in _parse_csv_tokens(raw_upload_extensions))
    allowed_upload_extension_set = {token.lower() for token in effective_allowed_upload_extensions}
    effective_quarantine_dir = quarantine_dir or os.getenv("FCD_QUARANTINE_DIR", "data/quarantine")

    app = FastAPI(title="Unpaid Invoice Escalator API")
    security = ApiSecurityController(
        enabled=effective_auth_enabled,
        api_keys=configured_keys,
        rate_limit_per_minute=effective_rate_limit,
        auth_failure_alert_threshold=effective_auth_failure_threshold,
        rate_limit_alert_threshold=effective_rate_limit_threshold,
        server_error_alert_threshold=effective_server_error_threshold,
    )
    store = SQLiteStore(db_path)
    ledger = SQLiteInvoiceLedger(store)
    runner = EscalationRunner(ledger=ledger)
    late_payment_engine = LatePaymentEngine(ledger=ledger)
    manifest_exporter = LedgerManifestExporter(
        store=store,
        signing_key=manifest_signing_key,
        key_id=manifest_key_id,
        verification_keys=verification_keys,
    )
    rule_pack_loader = RulePackLoader()
    dual_ledger_engine = DualLedgerEngine(store=store, event_ledger=ledger)
    hygiene_engine = PreOverdueHygieneEngine()
    discrepancy_validator = DataDiscrepancyValidator()
    legal_safety_gate_manager = LegalSafetyGateManager(store=store, event_ledger=ledger)
    five_ledger_engine = FiveLedgerEngine(store=store)
    case_health_check = CaseHealthCheck()
    devils_advocate_engine = DevilsAdvocateEngine()
    debtor_verification_portal = DebtorVerificationPortal(store=store)
    resolution_engine = ResolutionAndSettlementEngine(store=store, event_ledger=ledger)
    communication_severity_engine = CommunicationSeverityEngine(rule_pack_loader=rule_pack_loader)
    communication_delivery_tracker = CommunicationDeliveryTracker(store=store, event_ledger=ledger)
    viability_calculator = ViabilityProportionalityCalculator(store=store)
    resolution_artifact_generator = ResolutionArtifactGenerator()
    artifacts_root = Path(artifacts_dir)
    bundles_root = Path(bundles_dir)
    quarantine_root = Path(effective_quarantine_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    bundles_root.mkdir(parents=True, exist_ok=True)
    quarantine_root.mkdir(parents=True, exist_ok=True)

    startup_checks: list[dict[str, str | bool]] = []

    def _append_check(name: str, passed: bool, severity: str, detail: str) -> None:
        startup_checks.append(
            {
                "check": name,
                "passed": passed,
                "severity": severity,
                "detail": detail,
            }
        )

    _append_check(
        "manifest-signing-key",
        manifest_signing_key != "dev-only-signing-key",
        "error" if effective_env == "production" else "warning",
        (
            "Strong manifest signing key configured."
            if manifest_signing_key != "dev-only-signing-key"
            else "Default development signing key is in use."
        ),
    )
    _append_check(
        "auth-enabled-in-production",
        not (effective_env == "production" and not effective_auth_enabled),
        "error",
        (
            "Authentication enabled for production."
            if not (effective_env == "production" and not effective_auth_enabled)
            else "Production environment must enable authentication."
        ),
    )
    _append_check(
        "api-keys-configured",
        (not effective_auth_enabled) or bool(configured_keys),
        "error",
        "API keys configured for secured mode." if configured_keys else "No API keys configured.",
    )
    _append_check(
        "manifest-verification-keys",
        bool(verification_keys),
        "error",
        "Manifest verification keys configured."
        if verification_keys
        else "No manifest verification keys configured.",
    )
    _append_check(
        "max-upload-bytes",
        effective_max_upload_bytes > 0,
        "error",
        f"Max upload bytes set to {effective_max_upload_bytes}.",
    )
    _append_check(
        "allowed-upload-content-types",
        len(effective_allowed_upload_content_types) > 0,
        "error",
        (
            "Allowed upload content types configured: "
            + ", ".join(effective_allowed_upload_content_types)
            if effective_allowed_upload_content_types
            else "No allowed upload content types configured."
        ),
    )
    _append_check(
        "allowed-upload-extensions",
        len(effective_allowed_upload_extensions) > 0,
        "error",
        (
            "Allowed upload extensions configured: " + ", ".join(effective_allowed_upload_extensions)
            if effective_allowed_upload_extensions
            else "No allowed upload extensions configured."
        ),
    )
    _append_check(
        "upload-filename-policy",
        True,
        "warning",
        "Strict filename policy enforces alphanumeric/._- names and max length 128.",
    )
    _append_check(
        "rate-limit-per-minute",
        effective_rate_limit > 0,
        "error",
        f"Rate limit per minute set to {effective_rate_limit}.",
    )
    _append_check(
        "alert-thresholds",
        effective_auth_failure_threshold > 0
        and effective_rate_limit_threshold > 0
        and effective_server_error_threshold > 0,
        "warning",
        (
            "Alert thresholds configured."
            if (
                effective_auth_failure_threshold > 0
                and effective_rate_limit_threshold > 0
                and effective_server_error_threshold > 0
            )
            else "One or more alert thresholds are non-positive."
        ),
    )
    _append_check(
        "manifest-key-id",
        bool(manifest_key_id.strip()),
        "error",
        "Manifest key ID configured." if manifest_key_id.strip() else "Manifest key ID is empty.",
    )

    def _runtime_readiness_checks() -> list[dict[str, str | bool]]:
        checks: list[dict[str, str | bool]] = []

        def add_runtime_check(name: str, passed: bool, detail: str) -> None:
            checks.append({"check": name, "passed": passed, "severity": "error", "detail": detail})

        try:
            conn = sqlite3.connect(db_path)
            try:
                conn.execute("SELECT 1").fetchone()
            finally:
                conn.close()
            add_runtime_check("database-connectivity", True, "SQLite connection successful.")
        except sqlite3.Error as exc:
            add_runtime_check("database-connectivity", False, f"SQLite connectivity failed: {exc}")

        for check_name, directory in (
            ("artifacts-directory-writable", artifacts_root),
            ("bundles-directory-writable", bundles_root),
            ("quarantine-directory-writable", quarantine_root),
        ):
            probe_path = directory / ".readycheck.tmp"
            try:
                probe_path.write_text("ok", encoding="utf-8")
                probe_path.unlink()
                add_runtime_check(check_name, True, f"Directory writable: {directory}")
            except OSError as exc:
                add_runtime_check(check_name, False, f"Directory write failed for {directory}: {exc}")

        required_append_only_triggers = (
            "trg_ledger_events_no_update",
            "trg_ledger_events_no_delete",
            "trg_evidence_artifacts_no_update",
            "trg_evidence_artifacts_no_delete",
            "trg_debtor_ledger_no_update",
            "trg_debtor_ledger_no_delete",
            "trg_client_fee_no_update",
            "trg_client_fee_no_delete",
            "trg_hygiene_records_no_update",
            "trg_hygiene_records_no_delete",
            "trg_compliance_ledger_no_update",
            "trg_compliance_ledger_no_delete",
            "trg_debtor_verification_no_update",
            "trg_debtor_verification_no_delete",
            "trg_payment_plan_agreements_no_update",
            "trg_payment_plan_agreements_no_delete",
            "trg_payment_plan_installments_no_update",
            "trg_payment_plan_installments_no_delete",
            "trg_payment_plan_payments_no_update",
            "trg_payment_plan_payments_no_delete",
            "trg_settlement_offers_no_update",
            "trg_settlement_offers_no_delete",
            "trg_settlement_acceptances_no_update",
            "trg_settlement_acceptances_no_delete",
            "trg_dispute_carve_outs_no_update",
            "trg_dispute_carve_outs_no_delete",
            "trg_communications_no_update",
            "trg_communications_no_delete",
            "trg_communication_delivery_events_no_update",
            "trg_communication_delivery_events_no_delete",
        )
        try:
            conn = sqlite3.connect(db_path)
            try:
                rows = conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'trigger' AND name LIKE 'trg_%'"
                ).fetchall()
            finally:
                conn.close()
            trigger_names = {str(row[0]) for row in rows}
            missing_triggers = sorted(name for name in required_append_only_triggers if name not in trigger_names)
            if missing_triggers:
                add_runtime_check(
                    "append-only-triggers",
                    False,
                    "Missing append-only triggers: " + ", ".join(missing_triggers),
                )
            else:
                add_runtime_check("append-only-triggers", True, "Append-only triggers detected for protected tables.")
        except sqlite3.Error as exc:
            add_runtime_check("append-only-triggers", False, f"Trigger verification failed: {exc}")

        return checks

    def _startup_config_report() -> dict[str, object]:
        runtime_checks = _runtime_readiness_checks()
        combined_checks = [*startup_checks, *runtime_checks]
        errors = [check for check in combined_checks if (not bool(check["passed"])) and check["severity"] == "error"]
        warnings = [check for check in combined_checks if (not bool(check["passed"])) and check["severity"] == "warning"]
        passed_count = sum(1 for check in combined_checks if bool(check["passed"]))
        failed_count = len(combined_checks) - passed_count
        return {
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "environment": effective_env,
            "auth_enabled": effective_auth_enabled,
            "manifest_key_id": manifest_key_id,
            "verification_key_ids": sorted(verification_keys.keys()),
            "rate_limit_per_minute": effective_rate_limit,
            "max_upload_bytes": effective_max_upload_bytes,
            "allowed_upload_content_types": list(effective_allowed_upload_content_types),
            "allowed_upload_extensions": list(effective_allowed_upload_extensions),
            "quarantine_dir": str(quarantine_root),
            "checks": combined_checks,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "total_checks": len(combined_checks),
                "passed_checks": passed_count,
                "failed_checks": failed_count,
                "error_count": len(errors),
                "warning_count": len(warnings),
            },
            "ready": len(errors) == 0,
        }

    def _deployment_runbook_report() -> dict[str, object]:
        report = _startup_config_report()
        check_map = {str(item["check"]): bool(item["passed"]) for item in report["checks"]}
        steps = [
            {
                "step": 1,
                "title": "Validate signing and verification keys",
                "completed": check_map.get("manifest-signing-key", False) and check_map.get(
                    "manifest-verification-keys", False
                ),
                "detail": "Ensure active signing key and verification key ring are configured.",
            },
            {
                "step": 2,
                "title": "Validate auth and RBAC configuration",
                "completed": check_map.get("auth-enabled-in-production", False)
                and check_map.get("api-keys-configured", False),
                "detail": "Ensure API keys are present and role model is enforceable.",
            },
            {
                "step": 3,
                "title": "Validate runtime dependencies",
                "completed": check_map.get("database-connectivity", False)
                and check_map.get("artifacts-directory-writable", False)
                and check_map.get("bundles-directory-writable", False)
                and check_map.get("quarantine-directory-writable", False),
                "detail": "Confirm DB access and writable storage locations.",
            },
            {
                "step": 4,
                "title": "Validate operational guardrails",
                "completed": check_map.get("max-upload-bytes", False)
                and check_map.get("allowed-upload-content-types", False)
                and check_map.get("allowed-upload-extensions", False),
                "detail": "Confirm upload size limits and request controls are active.",
            },
        ]
        return {
            "environment": report["environment"],
            "ready": report["ready"],
            "pending_errors": report["errors"],
            "pending_warnings": report["warnings"],
            "steps": steps,
        }

    def _latest_case_health_confidence(invoice_id: str) -> str | None:
        entries = store.compliance_entries_for_invoice(invoice_id)
        for entry in reversed(entries):
            if entry.event_type == "CASE_HEALTH_CHECK":
                confidence = str(entry.details.get("case_confidence", "")).strip().upper()
                return confidence or None
        return None

    def _data_accuracy_challenge_is_open(invoice_id: str) -> bool:
        entries = store.compliance_entries_for_invoice(invoice_id)
        for entry in reversed(entries):
            if entry.event_type == "DATA_ACCURACY_CHALLENGE_RESOLVED":
                return False
            if entry.event_type == "DATA_ACCURACY_CHALLENGE_OPEN":
                return True
        return False

    def _latest_discrepancy_invalid(invoice_id: str) -> bool:
        entries = store.compliance_entries_for_invoice(invoice_id)
        for entry in reversed(entries):
            if entry.event_type == "DISCREPANCY_VALIDATION":
                return not bool(entry.details.get("valid", False))
        return False

    def _active_or_defaulted_payment_plan(invoice_id: str, as_of_date: date) -> tuple[str | None, str | None]:
        plans = store.payment_plan_agreements_for_invoice(invoice_id)
        for plan in reversed(plans):
            status = resolution_engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=as_of_date)
            if status.status in {"ACTIVE", "DEFAULTED"}:
                return plan.plan_id, status.status
        return None, None

    def _has_unresolved_delivery_failure(invoice_id: str) -> bool:
        failed_states = {
            CommunicationDeliveryState.BOUNCED,
            CommunicationDeliveryState.REJECTED,
            CommunicationDeliveryState.RETURNED,
        }
        snapshots = communication_delivery_tracker.snapshots_for_invoice(invoice_id)
        return any(snapshot.latest_state in failed_states for snapshot in snapshots)

    def _effective_outstanding_amount(invoice: Invoice) -> Decimal:
        entries = store.debtor_ledger_entries_for_invoice(invoice.invoice_id)
        if not entries:
            return invoice.principal_amount
        return store.debtor_ledger_balance_for_invoice(invoice.invoice_id)

    def _assert_pre_send_balance_lock(invoice: Invoice) -> Decimal:
        outstanding = _effective_outstanding_amount(invoice)
        if outstanding <= Decimal("0.00"):
            raise HTTPException(
                status_code=409,
                detail="Pre-send balance lock failed: no positive outstanding balance available for communication.",
            )
        return outstanding

    def _generate_promise_to_pay_artifact(invoice_id: str, plan_id: str, output_filename: str) -> EvidenceArtifact:
        agreements = store.payment_plan_agreements_for_invoice(invoice_id)
        agreement = next((item for item in agreements if item.plan_id == plan_id), None)
        if agreement is None:
            raise HTTPException(status_code=404, detail="Payment plan not found for invoice.")
        installments = store.payment_plan_installments_for_plan(plan_id)
        payments = store.payment_plan_payments_for_plan(plan_id)
        output_path = bundles_root / invoice_id / "resolution" / output_filename
        generated_path = resolution_artifact_generator.generate_promise_to_pay(
            agreement=agreement,
            installments=installments,
            payments=payments,
            output_path=str(output_path),
        )
        artifact = ledger.record_evidence_artifact(
            invoice_id=invoice_id,
            file_path=generated_path,
            user_id="SYSTEM",
            artifact_type=ArtifactType.PROMISE_TO_PAY,
            actor=Actor.SYSTEM,
        )
        return artifact

    def _generate_settlement_artifact(invoice_id: str, offer_id: str, output_filename: str) -> EvidenceArtifact:
        offer = store.settlement_offer_by_id(offer_id)
        if offer is None or offer.invoice_id != invoice_id:
            raise HTTPException(status_code=404, detail="Settlement offer not found for invoice.")
        acceptances = store.settlement_acceptances_for_offer(offer_id)
        accepted_roles = {item.accepter_role for item in acceptances}
        if accepted_roles != {"DEBTOR", "CREDITOR"}:
            raise HTTPException(status_code=409, detail="Settlement artifact requires bilateral acceptance.")
        output_path = bundles_root / invoice_id / "resolution" / output_filename
        generated_path = resolution_artifact_generator.generate_settlement_agreement(
            offer=offer,
            acceptances=acceptances,
            output_path=str(output_path),
        )
        artifact = ledger.record_evidence_artifact(
            invoice_id=invoice_id,
            file_path=generated_path,
            user_id="SYSTEM",
            artifact_type=ArtifactType.FULL_AND_FINAL_SETTLEMENT,
            actor=Actor.SYSTEM,
        )
        return artifact

    @app.middleware("http")
    async def security_middleware(request: Request, call_next):  # type: ignore[no-untyped-def]
        request_id = request.headers.get("x-request-id") or str(uuid4())

        def _harden_response(response):  # type: ignore[no-untyped-def]
            response.headers["x-request-id"] = request_id
            response.headers["x-content-type-options"] = "nosniff"
            response.headers["x-frame-options"] = "DENY"
            response.headers["referrer-policy"] = "no-referrer"
            response.headers["cache-control"] = "no-store"
            return response

        decision = security.evaluate_request(
            method=request.method,
            path=request.url.path,
            api_key=request.headers.get("x-api-key"),
            client_host=request.client.host if request.client else None,
        )
        if not decision.allowed:
            security.record_response(decision.status_code or 500)
            return _harden_response(
                JSONResponse(status_code=decision.status_code or 500, content={"detail": decision.detail})
            )

        if not security.is_public_path(request.url.path):
            limit_decision = security.check_rate_limit(decision.identity)
            if not limit_decision.allowed:
                security.record_response(limit_decision.status_code or 500)
                return _harden_response(
                    JSONResponse(
                        status_code=limit_decision.status_code or 500,
                        content={"detail": limit_decision.detail},
                        headers={"Retry-After": "60"},
                    )
                )

        response = await call_next(request)
        security.record_response(response.status_code)
        return _harden_response(response)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> JSONResponse:
        report = _startup_config_report()
        if bool(report["ready"]):
            return JSONResponse(status_code=200, content={"status": "ready", **report})
        return JSONResponse(status_code=503, content={"status": "not_ready", **report})

    @app.get("/metrics")
    def metrics() -> dict[str, object]:
        return security.metrics_snapshot()

    @app.get("/verify")
    def verify_case(case: str, code: str) -> dict[str, object]:
        result = debtor_verification_portal.verify(case_id=case, verification_code=code)
        if not result.valid:
            raise HTTPException(status_code=404, detail=result.message)
        return {"valid": True, "message": result.message}

    @app.get("/portal")
    def debtor_portal(case: str, code: str) -> dict[str, object]:
        result = debtor_verification_portal.verify(case_id=case, verification_code=code)
        if not result.valid:
            raise HTTPException(status_code=404, detail=result.message)
        creditor_name = result.creditor_name or "the creditor"
        return {
            "valid": True,
            "case_id": result.case_id,
            "message": result.message,
            "source_of_data_notice": (
                "First Cairn Digital holds your contact details as a Data Processor on behalf of "
                f"{creditor_name} (Data Controller) for the sole purpose of invoice administration. "
                "You may obtain independent legal or professional advice at any time from Citizens Advice, "
                "Business Debtline, or a solicitor."
            ),
            "resolution_options": [
                "Pay Full Balance Now",
                "Confirm Payment Date",
                "I Have Already Paid",
                "Propose Payment Plan / Settlement",
                "Ask Question About Invoice",
                "Dispute All or Part of Amount",
                "Correct Inaccurate Information",
                "View Independent Legal Advice Links",
            ],
        }

    @app.get("/deployment/startup-config-validation")
    def startup_config_validation() -> dict[str, object]:
        return _startup_config_report()

    @app.get("/deployment/startup-config-validation/report")
    def startup_config_validation_report() -> dict[str, object]:
        report = _startup_config_report()
        runbook = _deployment_runbook_report()
        return {
            **report,
            "runbook": {
                "ready": runbook["ready"],
                "steps": runbook["steps"],
                "pending_errors": runbook["pending_errors"],
                "pending_warnings": runbook["pending_warnings"],
            },
        }

    @app.get("/deployment/runbook")
    def deployment_runbook() -> dict[str, object]:
        return _deployment_runbook_report()

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return render_home_html()

    @app.get("/ui/invoices/{invoice_id}", response_class=HTMLResponse)
    def invoice_workspace(invoice_id: str) -> str:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        return render_invoice_workspace_html(invoice_id)

    @app.get("/rule-packs/{jurisdiction}/active")
    def get_active_rule_pack(jurisdiction: Jurisdiction, on_date: date | None = None) -> dict[str, object]:
        target_date = on_date or date.today()
        try:
            return rule_pack_loader.describe_active(jurisdiction, target_date)
        except (ValueError, RulePackValidationError) as exc:
            raise HTTPException(status_code=400, detail=str(exc))

    @app.post("/invoices")
    def create_invoice(payload: InvoiceCreateRequest) -> dict[str, str]:
        if payload.debtor_type == DebtorType.CONSUMER_CREDIT:
            raise HTTPException(status_code=400, detail="CONSUMER_CREDIT invoices are out of scope.")
        existing = store.get_invoice(payload.invoice_id)
        if existing is not None:
            raise HTTPException(status_code=409, detail="Invoice already exists.")

        invoice = Invoice(
            invoice_id=payload.invoice_id,
            currency=payload.currency,
            principal_amount=payload.principal_amount,
            issue_date=payload.issue_date,
            due_date=payload.due_date,
            jurisdiction=payload.jurisdiction,
            debtor_type=payload.debtor_type,
        )
        store.create_invoice(invoice)
        ledger.append_event(
            invoice_id=invoice.invoice_id,
            actor=Actor.CLIENT,
            event_type="INVOICE_CREATED",
            data_payload={
                "currency": invoice.currency,
                "principal_amount": str(invoice.principal_amount),
                "issue_date": invoice.issue_date.isoformat(),
                "due_date": invoice.due_date.isoformat(),
                "jurisdiction": invoice.jurisdiction.value,
                "debtor_type": invoice.debtor_type.value,
            },
        )
        return {"invoice_id": invoice.invoice_id, "status": "created"}

    @app.get("/invoices/{invoice_id}")
    def get_invoice(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        current_state = store.infer_state(invoice_id)
        return {
            "invoice_id": invoice.invoice_id,
            "currency": invoice.currency,
            "principal_amount": str(invoice.principal_amount),
            "issue_date": invoice.issue_date.isoformat(),
            "due_date": invoice.due_date.isoformat(),
            "jurisdiction": invoice.jurisdiction.value,
            "debtor_type": invoice.debtor_type.value,
            "current_state": current_state.value,
            "chain_valid": store.verify_chain(invoice_id),
        }

    @app.get("/invoices/{invoice_id}/communication-preview")
    def get_communication_preview(
        invoice_id: str, state: InvoiceState | None = None, on_date: date | None = None
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        preview = communication_severity_engine.preview_for_state(
            invoice=invoice,
            state=state or store.infer_state(invoice_id),
            on_date=on_date or date.today(),
            instructions="Procedural communication preview.",
            wait_until=None,
        )
        return {
            "invoice_id": invoice_id,
            "level": preview.level,
            "stage_name": preview.stage_name,
            "template_version": preview.template_version,
            "message": preview.message,
            "guardrail_flags": list(preview.guardrail_flags),
        }

    @app.post("/invoices/{invoice_id}/communications")
    def create_communication(invoice_id: str, payload: CommunicationCreateRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        locked_outstanding = _assert_pre_send_balance_lock(invoice) if payload.automated else _effective_outstanding_amount(invoice)
        snapshot = communication_delivery_tracker.create_communication(
            invoice_id=invoice_id,
            channel=payload.channel,
            recipient=payload.recipient,
            subject=payload.subject,
            body_summary=payload.body_summary,
            automated=payload.automated,
        )
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=snapshot.communication.created_at,
                event_type="COMMUNICATION_CREATED",
                details={
                    "communication_id": snapshot.communication.communication_id,
                    "channel": snapshot.communication.channel,
                    "recipient": snapshot.communication.recipient,
                    "automated": snapshot.communication.automated,
                    "delivery_state": snapshot.latest_state.value,
                    "locked_outstanding_balance_gbp": str(locked_outstanding),
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "communication_id": snapshot.communication.communication_id,
            "delivery_state": snapshot.latest_state.value,
            "automated": snapshot.communication.automated,
            "locked_outstanding_balance_gbp": str(locked_outstanding),
            "created_at": snapshot.communication.created_at.isoformat(),
        }

    @app.post("/invoices/{invoice_id}/communications/{communication_id}/delivery-events")
    def update_communication_delivery(
        invoice_id: str, communication_id: str, payload: CommunicationDeliveryUpdateRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        communication = store.communication_for_id(communication_id)
        if communication is None or communication.invoice_id != invoice_id:
            raise HTTPException(status_code=404, detail="Communication not found for invoice.")
        locked_outstanding: Decimal | None = None
        if payload.state == CommunicationDeliveryState.SENT and communication.automated:
            locked_outstanding = _assert_pre_send_balance_lock(invoice)
        try:
            snapshot = communication_delivery_tracker.record_delivery_event(
                invoice_id=invoice_id,
                communication_id=communication_id,
                next_state=payload.state,
                note=payload.note,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        latest_event = snapshot.events[-1]
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=latest_event.timestamp,
                event_type="COMMUNICATION_DELIVERY_STATE_UPDATED",
                details={
                    "communication_id": communication_id,
                    "state": latest_event.state.value,
                    "note": latest_event.note,
                    "locked_outstanding_balance_gbp": (
                        None if locked_outstanding is None else str(locked_outstanding)
                    ),
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "communication_id": communication_id,
            "delivery_state": latest_event.state.value,
            "locked_outstanding_balance_gbp": None if locked_outstanding is None else str(locked_outstanding),
            "recorded_at": latest_event.timestamp.isoformat(),
        }

    @app.get("/invoices/{invoice_id}/communications")
    def list_communications(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        snapshots = communication_delivery_tracker.snapshots_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "communications": [
                {
                    "communication_id": item.communication.communication_id,
                    "channel": item.communication.channel,
                    "recipient": item.communication.recipient,
                    "subject": item.communication.subject,
                    "body_summary": item.communication.body_summary,
                    "automated": item.communication.automated,
                    "created_at": item.communication.created_at.isoformat(),
                    "latest_state": item.latest_state.value,
                    "events": [
                        {
                            "event_id": evt.event_id,
                            "state": evt.state.value,
                            "timestamp": evt.timestamp.isoformat(),
                            "note": evt.note,
                        }
                        for evt in item.events
                    ],
                }
                for item in snapshots
            ],
        }

    @app.post("/invoices/{invoice_id}/case-health-check")
    def run_case_health_check(invoice_id: str, payload: CaseHealthCheckRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        criteria = {
            "correct_customer_legal_entity": payload.correct_customer_legal_entity,
            "description_of_goods_or_services": payload.description_of_goods_or_services,
            "invoice_number_and_date_verified": payload.invoice_number_and_date_verified,
            "amount_matches_contract_or_quote": payload.amount_matches_contract_or_quote,
            "correct_billing_address": payload.correct_billing_address,
            "vat_numbers_checked": payload.vat_numbers_checked,
            "purchase_order_supplied_if_required": payload.purchase_order_supplied_if_required,
            "payment_terms_and_due_date_established": payload.payment_terms_and_due_date_established,
            "delivery_or_acceptance_proof_attached": payload.delivery_or_acceptance_proof_attached,
            "no_unresolved_credit_notes": payload.no_unresolved_credit_notes,
            "direct_payments_checked": payload.direct_payments_checked,
            "no_known_dispute": payload.no_known_dispute,
            "creditor_authority_verified": payload.creditor_authority_verified,
            "limitation_period_checked": payload.limitation_period_checked,
            "debtor_contact_details_verified": payload.debtor_contact_details_verified,
            "court_handoff_boundary_acknowledged": payload.court_handoff_boundary_acknowledged,
        }
        result = case_health_check.evaluate(criteria=criteria)
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="CASE_HEALTH_CHECK",
                details={
                    "case_confidence": result.confidence,
                    "user_id": payload.user_id,
                    "passed_count": result.passed_count,
                    "total_count": result.total_count,
                    "failed_criteria": list(result.failed_criteria),
                    "criteria": result.criteria,
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="CASE_HEALTH_CHECK",
            timestamp=now,
            data_payload={
                "case_confidence": result.confidence,
                "passed_count": result.passed_count,
                "total_count": result.total_count,
                "failed_criteria": list(result.failed_criteria),
            },
        )
        return {
            "invoice_id": invoice_id,
            "case_confidence": result.confidence,
            "passed_count": result.passed_count,
            "total_count": result.total_count,
            "failed_criteria": list(result.failed_criteria),
            "chain_valid": store.verify_chain(invoice_id),
        }

    @app.post("/invoices/{invoice_id}/devils-advocate-check")
    def run_devils_advocate_check(invoice_id: str, payload: DevilsAdvocateCheckRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        result = devils_advocate_engine.evaluate(
            active_dispute=payload.active_dispute,
            payment_or_credit_discrepancy=payload.payment_or_credit_discrepancy,
            delivery_evidence_unverified=payload.delivery_evidence_unverified,
            settlement_pending_and_not_due=payload.settlement_pending_and_not_due,
            data_accuracy_challenge_pending=payload.data_accuracy_challenge_pending,
            insolvency_or_breathing_space_flag=payload.insolvency_or_breathing_space_flag,
        )
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="DEVILS_ADVOCATE_REVIEW",
                details={
                    "blocked": result.blocked,
                    "reasons": list(result.reasons),
                    "recommended_actions": list(result.recommended_actions),
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="DEVILS_ADVOCATE_REVIEW",
            timestamp=now,
            data_payload={
                "blocked": result.blocked,
                "reasons": list(result.reasons),
            },
        )
        return {
            "invoice_id": invoice_id,
            "blocked": result.blocked,
            "reasons": list(result.reasons),
            "recommended_actions": list(result.recommended_actions),
            "chain_valid": store.verify_chain(invoice_id),
        }

    @app.get("/invoices/{invoice_id}/five-ledger-summary")
    def get_five_ledger_summary(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        summary = five_ledger_engine.summarize(invoice_id=invoice_id)
        return {
            "invoice_id": invoice_id,
            "financial_ledger_balance_gbp": str(summary.financial_balance_gbp),
            "evidence_ledger_artifacts_count": summary.evidence_artifacts_count,
            "event_audit_ledger_events_count": summary.event_audit_events_count,
            "compliance_ledger_events_count": summary.compliance_events_count,
            "fcd_billing_ledger_balance_gbp": str(summary.fcd_billing_balance_gbp),
        }

    @app.post("/invoices/{invoice_id}/legal-safety-gate/confirm")
    def confirm_legal_safety_gate(invoice_id: str, payload: LegalSafetyGateConfirmRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        declarations = {
            "authorised_to_act": payload.authorised_to_act,
            "info_accurate": payload.info_accurate,
            "invoice_unpaid": payload.invoice_unpaid,
            "payments_recorded_complete": payload.payments_recorded_complete,
            "genuine_supporting_docs": payload.genuine_supporting_docs,
            "no_unresolved_dispute": payload.no_unresolved_dispute,
            "commercial_not_excluded": payload.commercial_not_excluded,
        }
        missing = [key for key, value in declarations.items() if not value]
        if missing:
            raise HTTPException(
                status_code=400,
                detail="All legal safety declarations must be accepted before formal escalation.",
            )
        result = legal_safety_gate_manager.confirm(
            invoice=invoice,
            user_id=payload.user_id,
            amount_claimed_gbp=payload.amount_claimed_gbp,
            payments_recorded_gbp=payload.payments_recorded_gbp,
            declarations=declarations,
        )
        return {
            "invoice_id": invoice_id,
            "accepted": result.accepted,
            "declaration_version": result.declaration_version,
            "disclaimer_text": result.disclaimer_text,
            "compliance_entry_id": result.compliance_entry_id,
            "recorded_at": result.recorded_at.isoformat(),
            "chain_valid": store.verify_chain(invoice_id),
        }

    @app.post("/invoices/{invoice_id}/discrepancy-check")
    def discrepancy_check(invoice_id: str, payload: DiscrepancyCheckRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        result = discrepancy_validator.validate(
            claim_amount=payload.claim_amount,
            evidence_document_amount=payload.evidence_document_amount,
            principal=payload.principal,
            payments_recorded=payload.payments_recorded,
            outstanding_entered=payload.outstanding_entered,
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="DISCREPANCY_VALIDATION",
            data_payload={
                "valid": result.valid,
                "status": result.status,
                "reasons": list(result.reasons),
                "circuit_breaker_triggered": result.circuit_breaker_triggered,
                "suggested_state": result.suggested_state,
            },
        )
        store.append_compliance_entry(
            entry=ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=datetime.now(timezone.utc),
                event_type="DISCREPANCY_VALIDATION",
                details={
                    "valid": result.valid,
                    "status": result.status,
                    "reasons": list(result.reasons),
                    "circuit_breaker_triggered": result.circuit_breaker_triggered,
                    "suggested_state": result.suggested_state,
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "valid": result.valid,
            "status": result.status,
            "reasons": list(result.reasons),
            "circuit_breaker_triggered": result.circuit_breaker_triggered,
            "suggested_state": result.suggested_state,
            "chain_valid": store.verify_chain(invoice_id),
        }

    @app.post("/invoices/{invoice_id}/debtor-verification/register")
    def register_debtor_verification(
        invoice_id: str, payload: DebtorVerificationRegisterRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        invoice_reference = payload.invoice_reference or invoice.invoice_id
        try:
            registration = debtor_verification_portal.register_case(
                invoice_id=invoice_id,
                creditor_name=payload.creditor_name,
                invoice_reference=invoice_reference,
            )
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc))
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="DEBTOR_VERIFICATION_REGISTERED",
            data_payload={
                "case_id": registration.case_id,
                "creditor_name": registration.creditor_name,
                "invoice_reference": registration.invoice_reference,
            },
        )
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=registration.created_at,
                event_type="DEBTOR_VERIFICATION_REGISTERED",
                details={
                    "case_id": registration.case_id,
                    "creditor_name": registration.creditor_name,
                    "invoice_reference": registration.invoice_reference,
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "case_id": registration.case_id,
            "verification_code": registration.verification_code,
            "verify_url": f"/verify?case={registration.case_id}",
        }

    @app.post("/invoices/{invoice_id}/debtor-actions/data-accuracy-challenge")
    def submit_data_accuracy_challenge(invoice_id: str, payload: DataAccuracyChallengeRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="DATA_ACCURACY_CHALLENGE_OPEN",
                details={
                    "recovery_restricted": True,
                    "debtor_identifier": payload.debtor_identifier,
                    "challenge_reason": payload.challenge_reason,
                    "challenge_details": payload.challenge_details,
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.DEBTOR,
            event_type="DATA_ACCURACY_CHALLENGE_OPEN",
            timestamp=now,
            data_payload={"recovery_restricted": True, "challenge_reason": payload.challenge_reason},
        )
        return {
            "invoice_id": invoice_id,
            "recovery_restricted": True,
            "status": "RECOVERY_RESTRICTED",
            "message": "Automation frozen pending creditor data verification or correction.",
        }

    @app.post("/invoices/{invoice_id}/debtor-actions/data-accuracy-challenge/resolve")
    def resolve_data_accuracy_challenge(
        invoice_id: str, payload: ResolveDataAccuracyChallengeRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if not _data_accuracy_challenge_is_open(invoice_id):
            raise HTTPException(status_code=409, detail="No open data-accuracy challenge to resolve.")
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="DATA_ACCURACY_CHALLENGE_RESOLVED",
                details={
                    "recovery_restricted": False,
                    "creditor_user_id": payload.creditor_user_id,
                    "resolution_notes": payload.resolution_notes,
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="DATA_ACCURACY_CHALLENGE_RESOLVED",
            timestamp=now,
            data_payload={"recovery_restricted": False, "creditor_user_id": payload.creditor_user_id},
        )
        return {
            "invoice_id": invoice_id,
            "recovery_restricted": False,
            "status": "RECOVERY_RESTORED",
        }

    @app.get("/invoices/{invoice_id}/evidence-artifacts")
    def list_evidence_artifacts(
        invoice_id: str,
        artifact_type: ArtifactType | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 1000.")
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be >= 0.")

        artifacts = store.artifacts_for_invoice(invoice_id)
        if artifact_type is not None:
            artifacts = tuple(artifact for artifact in artifacts if artifact.artifact_type == artifact_type)
        total_count = len(artifacts)
        selected = artifacts[offset : offset + limit]
        return {
            "invoice_id": invoice_id,
            "count": len(selected),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "artifacts": [
                {
                    "document_id": artifact.document_id,
                    "artifact_type": artifact.artifact_type.value,
                    "file_hash": artifact.file_hash,
                    "file_path": artifact.file_path,
                    "upload_timestamp": artifact.upload_timestamp.isoformat(),
                    "user_id": artifact.user_id,
                }
                for artifact in selected
            ],
        }

    @app.get("/invoices/{invoice_id}/ledger-events")
    def list_ledger_events(
        invoice_id: str,
        limit: int = 100,
        offset: int = 0,
        event_type: str | None = None,
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 1000.")
        if offset < 0:
            raise HTTPException(status_code=400, detail="offset must be >= 0.")

        events = store.events_for_invoice(invoice_id)
        if event_type is not None:
            events = tuple(event for event in events if event.event_type == event_type)
        total_count = len(events)
        selected = events[offset : offset + limit]
        return {
            "invoice_id": invoice_id,
            "count": len(selected),
            "total_count": total_count,
            "offset": offset,
            "limit": limit,
            "chain_valid": store.verify_chain(invoice_id),
            "events": [
                {
                    "event_id": event.event_id,
                    "timestamp": event.timestamp.isoformat(),
                    "actor": event.actor.value,
                    "event_type": event.event_type,
                    "data_payload": event.data_payload,
                    "previous_hash": event.previous_hash,
                    "hash": event.hash,
                }
                for event in selected
            ],
        }

    @app.get("/invoices/{invoice_id}/compliance-ledger")
    def list_compliance_entries(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        entries = store.compliance_entries_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "count": len(entries),
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "event_type": entry.event_type,
                    "details": entry.details,
                }
                for entry in entries
            ],
        }

    @app.post("/invoices/{invoice_id}/resolution/payment-plans")
    def propose_payment_plan(invoice_id: str, payload: PaymentPlanProposalRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        try:
            plan, installments = resolution_engine.propose_payment_plan(
                invoice_id=invoice_id,
                proposed_by=payload.proposed_by,
                installment_amount_gbp=payload.installment_amount_gbp,
                installment_count=payload.installment_count,
                first_due_date=payload.first_due_date,
                frequency_days=payload.frequency_days,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=plan.created_at,
                event_type="PAYMENT_PLAN_PROPOSED",
                details={
                    "plan_id": plan.plan_id,
                    "proposed_by": plan.proposed_by,
                    "installment_amount_gbp": str(plan.installment_amount_gbp),
                    "installment_count": plan.installment_count,
                    "first_due_date": plan.first_due_date.isoformat(),
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "plan_id": plan.plan_id,
            "installment_count": len(installments),
            "installments": [
                {
                    "installment_id": item.installment_id,
                    "sequence_number": item.sequence_number,
                    "due_date": item.due_date.isoformat(),
                    "amount_gbp": str(item.amount_gbp),
                }
                for item in installments
            ],
            "status": "ACTIVE",
            "chasers_paused": True,
        }

    @app.get("/invoices/{invoice_id}/resolution/payment-plans")
    def list_payment_plans(invoice_id: str, as_of_date: date | None = None) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        target_date = as_of_date or date.today()
        plans = store.payment_plan_agreements_for_invoice(invoice_id)
        result: list[dict[str, object]] = []
        for plan in plans:
            status = resolution_engine.payment_plan_status(plan_id=plan.plan_id, as_of_date=target_date)
            installments = store.payment_plan_installments_for_plan(plan.plan_id)
            result.append(
                {
                    "plan_id": plan.plan_id,
                    "created_at": plan.created_at.isoformat(),
                    "proposed_by": plan.proposed_by,
                    "installment_amount_gbp": str(plan.installment_amount_gbp),
                    "installment_count": plan.installment_count,
                    "first_due_date": plan.first_due_date.isoformat(),
                    "frequency_days": plan.frequency_days,
                    "notes": plan.notes,
                    "status": status.status,
                    "remaining_amount_gbp": str(status.remaining_amount_gbp),
                    "missed_installment_count": status.missed_installment_count,
                    "installments": [
                        {
                            "installment_id": inst.installment_id,
                            "sequence_number": inst.sequence_number,
                            "due_date": inst.due_date.isoformat(),
                            "amount_gbp": str(inst.amount_gbp),
                        }
                        for inst in installments
                    ],
                }
            )
        return {"invoice_id": invoice_id, "as_of_date": target_date.isoformat(), "plans": result}

    @app.post("/invoices/{invoice_id}/resolution/payment-plans/{plan_id}/payments")
    def record_payment_plan_payment(
        invoice_id: str, plan_id: str, payload: PaymentPlanPaymentRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        installments = store.payment_plan_installments_for_plan(plan_id)
        if not any(item.installment_id == payload.installment_id and item.invoice_id == invoice_id for item in installments):
            raise HTTPException(status_code=404, detail="Installment not found for invoice payment plan.")
        try:
            payment = resolution_engine.record_installment_payment(
                invoice_id=invoice_id,
                plan_id=plan_id,
                installment_id=payload.installment_id,
                amount_gbp=payload.amount_gbp,
                recorded_by=payload.recorded_by,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=payment.paid_at,
                event_type="PAYMENT_PLAN_PAYMENT_RECORDED",
                details={
                    "plan_id": payment.plan_id,
                    "installment_id": payment.installment_id,
                    "amount_gbp": str(payment.amount_gbp),
                    "recorded_by": payment.recorded_by,
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "plan_id": plan_id,
            "payment_id": payment.payment_id,
            "amount_gbp": str(payment.amount_gbp),
            "recorded_at": payment.paid_at.isoformat(),
            "chasers_paused": True,
        }

    @app.post("/invoices/{invoice_id}/resolution/settlement-offers")
    def propose_settlement_offer(invoice_id: str, payload: SettlementOfferRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        try:
            offer = resolution_engine.propose_settlement_offer(
                invoice_id=invoice_id,
                offered_by=payload.offered_by,
                offered_amount_gbp=payload.offered_amount_gbp,
                expiry_date=payload.expiry_date,
                notes=payload.notes,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=offer.offered_at,
                event_type="SETTLEMENT_OFFER_PROPOSED",
                details={
                    "offer_id": offer.offer_id,
                    "offered_by": offer.offered_by,
                    "offered_amount_gbp": str(offer.offered_amount_gbp),
                    "expiry_date": offer.expiry_date.isoformat(),
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "offer_id": offer.offer_id,
            "offered_amount_gbp": str(offer.offered_amount_gbp),
            "expiry_date": offer.expiry_date.isoformat(),
            "status": "OPEN",
        }

    @app.post("/invoices/{invoice_id}/resolution/settlement-offers/{offer_id}/accept")
    def accept_settlement_offer(
        invoice_id: str, offer_id: str, payload: SettlementAcceptanceRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        offer = store.settlement_offer_by_id(offer_id)
        if offer is None or offer.invoice_id != invoice_id:
            raise HTTPException(status_code=404, detail="Settlement offer not found.")
        try:
            acceptance, finalized = resolution_engine.accept_settlement_offer(
                offer_id=offer_id,
                accepted_by=payload.accepted_by,
                accepter_role=payload.accepter_role,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=acceptance.accepted_at,
                event_type="SETTLEMENT_OFFER_ACCEPTED",
                details={
                    "offer_id": offer_id,
                    "accepted_by": acceptance.accepted_by,
                    "accepter_role": acceptance.accepter_role,
                    "finalized": finalized,
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "offer_id": offer_id,
            "acceptance_id": acceptance.acceptance_id,
            "accepter_role": acceptance.accepter_role,
            "finalized": finalized,
        }

    @app.get("/invoices/{invoice_id}/resolution/settlement-offers")
    def list_settlement_offers(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        offers = store.settlement_offers_for_invoice(invoice_id)
        rows: list[dict[str, object]] = []
        for offer in offers:
            acceptances = store.settlement_acceptances_for_offer(offer.offer_id)
            roles = {item.accepter_role for item in acceptances}
            rows.append(
                {
                    "offer_id": offer.offer_id,
                    "offered_at": offer.offered_at.isoformat(),
                    "offered_by": offer.offered_by,
                    "offered_amount_gbp": str(offer.offered_amount_gbp),
                    "expiry_date": offer.expiry_date.isoformat(),
                    "notes": offer.notes,
                    "accepted_roles": sorted(roles),
                    "status": "FINALIZED" if roles == {"DEBTOR", "CREDITOR"} else "OPEN",
                }
            )
        return {"invoice_id": invoice_id, "offers": rows}

    @app.post("/invoices/{invoice_id}/resolution/dispute-carve-outs")
    def create_dispute_carve_out(invoice_id: str, payload: DisputeCarveOutRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        try:
            carve_out = resolution_engine.create_dispute_carve_out(
                invoice_id=invoice_id,
                disputed_amount_gbp=payload.disputed_amount_gbp,
                reason=payload.reason,
                created_by=payload.created_by,
            )
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc))
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=carve_out.created_at,
                event_type="DISPUTE_CARVE_OUT_CREATED",
                details={
                    "carve_out_id": carve_out.carve_out_id,
                    "disputed_amount_gbp": str(carve_out.disputed_amount_gbp),
                    "undisputed_amount_gbp": str(carve_out.undisputed_amount_gbp),
                    "reason": carve_out.reason,
                },
            )
        )
        return {
            "invoice_id": invoice_id,
            "carve_out_id": carve_out.carve_out_id,
            "disputed_amount_gbp": str(carve_out.disputed_amount_gbp),
            "undisputed_amount_gbp": str(carve_out.undisputed_amount_gbp),
            "suggested_state": "DISPUTE_REVIEW",
        }

    @app.get("/invoices/{invoice_id}/resolution/dispute-carve-outs")
    def list_dispute_carve_outs(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        carve_outs = store.dispute_carve_outs_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "carve_outs": [
                {
                    "carve_out_id": item.carve_out_id,
                    "created_at": item.created_at.isoformat(),
                    "disputed_amount_gbp": str(item.disputed_amount_gbp),
                    "undisputed_amount_gbp": str(item.undisputed_amount_gbp),
                    "reason": item.reason,
                    "created_by": item.created_by,
                }
                for item in carve_outs
            ],
        }

    @app.post("/invoices/{invoice_id}/resolution/artifacts/promise-to-pay")
    def generate_promise_to_pay_artifact(
        invoice_id: str, payload: PromiseToPayArtifactRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        generated_artifact = _generate_promise_to_pay_artifact(
            invoice_id=invoice_id,
            plan_id=payload.plan_id,
            output_filename=payload.output_filename,
        )
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="PROMISE_TO_PAY_ARTIFACT_GENERATED",
                details={
                    "plan_id": payload.plan_id,
                    "artifact_path": generated_artifact.file_path,
                    "document_id": generated_artifact.document_id,
                    "file_hash": generated_artifact.file_hash,
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="PROMISE_TO_PAY_ARTIFACT_GENERATED",
            timestamp=now,
            data_payload={
                "plan_id": payload.plan_id,
                "artifact_path": generated_artifact.file_path,
                "document_id": generated_artifact.document_id,
                "file_hash": generated_artifact.file_hash,
            },
        )
        return {
            "invoice_id": invoice_id,
            "plan_id": payload.plan_id,
            "artifact_path": generated_artifact.file_path,
            "document_id": generated_artifact.document_id,
            "file_hash": generated_artifact.file_hash,
            "artifact_type": generated_artifact.artifact_type.value,
        }

    @app.post("/invoices/{invoice_id}/resolution/artifacts/settlement-agreement")
    def generate_settlement_agreement_artifact(
        invoice_id: str, payload: SettlementAgreementArtifactRequest
    ) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        generated_artifact = _generate_settlement_artifact(
            invoice_id=invoice_id,
            offer_id=payload.offer_id,
            output_filename=payload.output_filename,
        )
        now = datetime.now(timezone.utc)
        store.append_compliance_entry(
            ComplianceLedgerEntry(
                entry_id=str(uuid4()),
                invoice_id=invoice_id,
                timestamp=now,
                event_type="SETTLEMENT_AGREEMENT_ARTIFACT_GENERATED",
                details={
                    "offer_id": payload.offer_id,
                    "artifact_path": generated_artifact.file_path,
                    "document_id": generated_artifact.document_id,
                    "file_hash": generated_artifact.file_hash,
                },
            )
        )
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.SYSTEM,
            event_type="SETTLEMENT_AGREEMENT_ARTIFACT_GENERATED",
            timestamp=now,
            data_payload={
                "offer_id": payload.offer_id,
                "artifact_path": generated_artifact.file_path,
                "document_id": generated_artifact.document_id,
                "file_hash": generated_artifact.file_hash,
            },
        )
        return {
            "invoice_id": invoice_id,
            "offer_id": payload.offer_id,
            "artifact_path": generated_artifact.file_path,
            "document_id": generated_artifact.document_id,
            "file_hash": generated_artifact.file_hash,
            "artifact_type": generated_artifact.artifact_type.value,
        }

    @app.get("/invoices/{invoice_id}/debtor-ledger")
    def get_debtor_ledger(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        entries = store.debtor_ledger_entries_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "balance_gbp": str(store.debtor_ledger_balance_for_invoice(invoice_id)),
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "entry_type": entry.entry_type.value,
                    "amount_gbp": str(entry.amount_gbp),
                    "description": entry.description,
                    "recovery_cost_category": (
                        None if entry.recovery_cost_category is None else entry.recovery_cost_category.value
                    ),
                    "linked_client_fee_entry_id": entry.linked_client_fee_entry_id,
                }
                for entry in entries
            ],
        }

    @app.get("/invoices/{invoice_id}/client-fee-ledger")
    def get_client_fee_ledger(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        entries = store.client_fee_entries_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "balance_gbp": str(store.client_fee_balance_for_invoice(invoice_id)),
            "entries": [
                {
                    "entry_id": entry.entry_id,
                    "case_id": entry.case_id,
                    "client_id": entry.client_id,
                    "timestamp": entry.timestamp.isoformat(),
                    "pricing_schedule_version": entry.pricing_schedule_version,
                    "action_selected": entry.action_selected.value,
                    "fee_amount_gbp": str(entry.fee_amount_gbp),
                    "vat_gbp": str(entry.vat_gbp),
                    "accepted_by_user": entry.accepted_by_user,
                    "external_fee": entry.external_fee,
                }
                for entry in entries
            ],
        }

    @app.post("/invoices/{invoice_id}/client-fee-ledger/actions")
    def add_client_fee_action(invoice_id: str, payload: ClientFeeActionRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        entry = dual_ledger_engine.add_client_action_fee(
            case_id=payload.case_id,
            client_id=payload.client_id,
            invoice_id=invoice_id,
            action_selected=payload.action_selected,
            accepted_by_user=payload.accepted_by_user,
        )
        balances = dual_ledger_engine.balances_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "entry_id": entry.entry_id,
            "pricing_schedule_version": entry.pricing_schedule_version,
            "fee_amount_gbp": str(entry.fee_amount_gbp),
            "vat_gbp": str(entry.vat_gbp),
            "client_fee_balance_gbp": str(balances.client_fee_balance),
            "disclosure": "FCD client fee recorded in Ledger B only. No automatic cross-posting to debtor ledger.",
        }

    @app.post("/invoices/{invoice_id}/debtor-ledger/entries")
    def add_debtor_ledger_entry(invoice_id: str, payload: DebtorLedgerEntryRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        entry = dual_ledger_engine.add_debtor_entry(
            invoice_id=invoice_id,
            entry_type=payload.entry_type,
            amount_gbp=payload.amount_gbp,
            description=payload.description,
            recovery_cost_category=payload.recovery_cost_category,
            linked_client_fee_entry_id=payload.linked_client_fee_entry_id,
        )
        cancelled_communications: list[str] = []
        if payload.entry_type in {DebtorLedgerEntryType.PAYMENT_RECEIVED, DebtorLedgerEntryType.CREDIT_NOTE}:
            for snapshot in communication_delivery_tracker.snapshots_for_invoice(invoice_id):
                if not snapshot.communication.automated:
                    continue
                if snapshot.latest_state not in {CommunicationDeliveryState.CREATED, CommunicationDeliveryState.QUEUED}:
                    continue
                try:
                    communication_delivery_tracker.record_delivery_event(
                        invoice_id=invoice_id,
                        communication_id=snapshot.communication.communication_id,
                        next_state=CommunicationDeliveryState.CANCELLED,
                        note="Cancelled automatically due to payment/credit ledger entry.",
                    )
                    cancelled_communications.append(snapshot.communication.communication_id)
                except ValueError:
                    continue
            if cancelled_communications:
                now = datetime.now(timezone.utc)
                store.append_compliance_entry(
                    ComplianceLedgerEntry(
                        entry_id=str(uuid4()),
                        invoice_id=invoice_id,
                        timestamp=now,
                        event_type="PENDING_COMMUNICATIONS_CANCELLED_ON_PAYMENT_OR_CREDIT",
                        details={
                            "entry_type": payload.entry_type.value,
                            "cancelled_communication_ids": cancelled_communications,
                        },
                    )
                )
                ledger.append_event(
                    invoice_id=invoice_id,
                    actor=Actor.SYSTEM,
                    event_type="PENDING_COMMUNICATIONS_CANCELLED_ON_PAYMENT_OR_CREDIT",
                    timestamp=now,
                    data_payload={
                        "entry_type": payload.entry_type.value,
                        "cancelled_communication_ids": cancelled_communications,
                    },
                )
        balances = dual_ledger_engine.balances_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "entry_id": entry.entry_id,
            "amount_gbp": str(entry.amount_gbp),
            "debtor_ledger_balance_gbp": str(balances.debtor_ledger_balance),
            "cancelled_pending_communication_ids": cancelled_communications,
        }

    @app.post("/invoices/{invoice_id}/recovery-cost-assessments")
    def assess_recovery_cost(invoice_id: str, payload: RecoveryCostAssessmentRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        result = dual_ledger_engine.assess_recovery_cost_eligibility(
            invoice_id=invoice_id,
            recovery_cost_gbp=payload.recovery_cost_gbp,
            has_contractual_recovery_clause=payload.has_contractual_recovery_clause,
            is_official_court_fee=payload.is_official_court_fee,
            statutory_reasonable_recovery_allowed=payload.statutory_reasonable_recovery_allowed,
        )
        disclosure = (
            f"£{payload.recovery_cost_gbp} recovery cost incurred. Eligibility to add this to the amount claimed has "
            f"been assessed under ruleset {result.ruleset}."
        )
        return {
            "invoice_id": invoice_id,
            "category": result.category.value,
            "ruleset": result.ruleset,
            "rationale": result.rationale,
            "disclosure": disclosure,
        }

    @app.post("/invoices/{invoice_id}/court-fee-quotes")
    def quote_court_fee(invoice_id: str, payload: CourtFeeQuoteRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        fee = dual_ledger_engine.quote_official_court_fee(invoice=invoice, claim_value_gbp=payload.claim_value_gbp)
        return {
            "invoice_id": invoice_id,
            "jurisdiction": invoice.jurisdiction.value,
            "claim_value_gbp": str(payload.claim_value_gbp),
            "official_court_fee_gbp": str(fee),
            "external_fee_notice": "Official court fee payable to court authority, not FCD revenue.",
        }

    @app.post("/invoices/{invoice_id}/viability-proportionality-assessments")
    def assess_viability_proportionality(invoice_id: str, payload: ViabilityAssessmentRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        assessment = viability_calculator.assess(
            invoice=invoice,
            on_date=payload.on_date,
            projected_action=payload.projected_action,
            estimated_time_cost_gbp=payload.estimated_time_cost_gbp,
            company_status=payload.company_status,
        )
        return {
            "invoice_id": invoice_id,
            "company_status": assessment.company_status,
            "outstanding_amount_gbp": str(assessment.outstanding_amount_gbp),
            "projected_fcd_action_fee_gbp": str(assessment.projected_fcd_action_fee_gbp),
            "projected_court_fee_gbp": str(assessment.projected_court_fee_gbp),
            "estimated_time_cost_gbp": str(assessment.estimated_time_cost_gbp),
            "projected_total_cost_gbp": str(assessment.projected_total_cost_gbp),
            "cost_ratio": str(assessment.cost_ratio),
            "disproportionate": assessment.disproportionate,
            "blocked": assessment.blocked,
            "notice": assessment.notice,
            "recommendation": assessment.recommendation,
        }

    @app.post("/invoices/{invoice_id}/pre-overdue-hygiene")
    def record_pre_overdue_hygiene(invoice_id: str, payload: PreOverdueHygieneRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        record, assessment = hygiene_engine.build_record(
            invoice_id=invoice_id,
            creditor_legal_entity_name=payload.creditor_legal_entity_name,
            creditor_companies_house_number=payload.creditor_companies_house_number,
            creditor_vat_number=payload.creditor_vat_number,
            creditor_trading_address=payload.creditor_trading_address,
            debtor_legal_entity_name=payload.debtor_legal_entity_name,
            debtor_companies_house_number=payload.debtor_companies_house_number,
            debtor_vat_number=payload.debtor_vat_number,
            debtor_trading_address=payload.debtor_trading_address,
            po_required=payload.po_required,
            po_reference=payload.po_reference,
            payment_terms_days=payload.payment_terms_days,
            contractual_interest_clause_present=payload.contractual_interest_clause_present,
            contractual_recovery_clause_present=payload.contractual_recovery_clause_present,
            proof_of_delivery_required=payload.proof_of_delivery_required,
            suggested_clause_text=payload.suggested_clause_text,
            notes=payload.notes,
        )
        store.append_pre_overdue_hygiene_record(record)
        ledger.append_event(
            invoice_id=invoice_id,
            actor=Actor.CLIENT,
            event_type="PRE_OVERDUE_HYGIENE_RECORDED",
            data_payload={
                "record_id": record.record_id,
                "checklist_complete": assessment.checklist_complete,
                "missing_items": list(assessment.missing_items),
                "warning_tier": assessment.warning_tier,
                "format_warnings": list(assessment.format_warnings),
                "suggested_clause_requires_legal_review": assessment.suggested_clause_requires_legal_review,
                "disclaimer": assessment.disclaimer,
            },
            timestamp=record.timestamp,
        )
        return {
            "invoice_id": invoice_id,
            "record_id": record.record_id,
            "checklist_complete": assessment.checklist_complete,
            "missing_items": list(assessment.missing_items),
            "warning_tier": assessment.warning_tier,
            "format_warnings": list(assessment.format_warnings),
            "suggested_clause_requires_legal_review": assessment.suggested_clause_requires_legal_review,
            "disclaimer": assessment.disclaimer,
        }

    @app.get("/invoices/{invoice_id}/pre-overdue-hygiene")
    def list_pre_overdue_hygiene_records(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        records = store.pre_overdue_hygiene_records_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "count": len(records),
            "records": [
                {
                    "record_id": record.record_id,
                    "timestamp": record.timestamp.isoformat(),
                    "creditor_legal_entity_name": record.creditor_legal_entity_name,
                    "creditor_companies_house_number": record.creditor_companies_house_number,
                    "creditor_vat_number": record.creditor_vat_number,
                    "creditor_trading_address": record.creditor_trading_address,
                    "debtor_legal_entity_name": record.debtor_legal_entity_name,
                    "debtor_companies_house_number": record.debtor_companies_house_number,
                    "debtor_vat_number": record.debtor_vat_number,
                    "debtor_trading_address": record.debtor_trading_address,
                    "po_required": record.po_required,
                    "po_reference": record.po_reference,
                    "payment_terms_days": record.payment_terms_days,
                    "contractual_interest_clause_present": record.contractual_interest_clause_present,
                    "contractual_recovery_clause_present": record.contractual_recovery_clause_present,
                    "proof_of_delivery_required": record.proof_of_delivery_required,
                    "suggested_clause_text": record.suggested_clause_text,
                    "suggested_clause_requires_legal_review": record.suggested_clause_requires_legal_review,
                    "checklist_complete": record.checklist_complete,
                    "missing_items": list(record.missing_items),
                    "warning_tier": record.warning_tier,
                    "format_warnings": list(record.format_warnings),
                    "notes": record.notes,
                }
                for record in records
            ],
        }

    @app.post("/invoices/{invoice_id}/escalate")
    def escalate_invoice(invoice_id: str, payload: EscalateRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")

        case_health_confidence = _latest_case_health_confidence(invoice_id)
        if case_health_confidence is None:
            raise HTTPException(
                status_code=409,
                detail="Pre-escalation case health check is required before escalation can proceed.",
            )
        if case_health_confidence != "READY":
            raise HTTPException(
                status_code=409,
                detail=f"Escalation blocked by case health confidence: {case_health_confidence}.",
            )
        if _latest_discrepancy_invalid(invoice_id):
            raise HTTPException(
                status_code=409,
                detail="Escalation blocked by unresolved discrepancy validation failure.",
            )
        if _data_accuracy_challenge_is_open(invoice_id):
            raise HTTPException(
                status_code=409,
                detail="Escalation blocked while debtor data-accuracy challenge is open.",
            )
        if _has_unresolved_delivery_failure(invoice_id):
            raise HTTPException(
                status_code=409,
                detail="Escalation blocked due to communication delivery failure. Verify debtor contact details first.",
            )
        viability = viability_calculator.assess(
            invoice=invoice,
            on_date=payload.today,
            projected_action=payload.projected_action,
            estimated_time_cost_gbp=payload.estimated_time_cost_gbp,
            company_status=payload.company_status,
        )
        if viability.blocked:
            now = datetime.now(timezone.utc)
            store.append_compliance_entry(
                ComplianceLedgerEntry(
                    entry_id=str(uuid4()),
                    invoice_id=invoice_id,
                    timestamp=now,
                    event_type="VIABILITY_BLOCK",
                    details={
                        "company_status": viability.company_status,
                        "recommendation": viability.recommendation,
                    },
                )
            )
            ledger.append_event(
                invoice_id=invoice_id,
                actor=Actor.SYSTEM,
                event_type="VIABILITY_BLOCK",
                timestamp=now,
                data_payload={"company_status": viability.company_status, "recommendation": viability.recommendation},
            )
            raise HTTPException(
                status_code=409,
                detail="Escalation blocked by viability review: financial distress indicator present.",
            )
        forced_current_state: InvoiceState | None = None
        active_plan_id, active_plan_status = _active_or_defaulted_payment_plan(invoice_id, payload.today)
        if active_plan_status == "ACTIVE":
            raise HTTPException(
                status_code=409,
                detail=f"Escalation blocked: payment plan {active_plan_id} is active and chasers remain paused.",
            )
        if active_plan_status == "DEFAULTED":
            forced_current_state = InvoiceState.OVERDUE_CHASER
            now = datetime.now(timezone.utc)
            store.append_compliance_entry(
                ComplianceLedgerEntry(
                    entry_id=str(uuid4()),
                    invoice_id=invoice_id,
                    timestamp=now,
                    event_type="PAYMENT_PLAN_DEFAULTED_RESUME",
                    details={"plan_id": active_plan_id, "resume_state": InvoiceState.OVERDUE_CHASER.value},
                )
            )
            ledger.append_event(
                invoice_id=invoice_id,
                actor=Actor.SYSTEM,
                event_type="PAYMENT_PLAN_DEFAULTED_RESUME",
                timestamp=now,
                data_payload={"plan_id": active_plan_id, "resume_state": InvoiceState.OVERDUE_CHASER.value},
            )

        devils_advocate_result = devils_advocate_engine.evaluate(
            active_dispute=payload.debtor_feedback == "DISPUTE",
            payment_or_credit_discrepancy=_latest_discrepancy_invalid(invoice_id),
            delivery_evidence_unverified=payload.delivery_evidence_unverified,
            settlement_pending_and_not_due=payload.settlement_pending_and_not_due,
            data_accuracy_challenge_pending=_data_accuracy_challenge_is_open(invoice_id),
            insolvency_or_breathing_space_flag=(
                payload.system_flag in {"BREATHING_SPACE", "INSOLVENCY"} or payload.insolvency_flag
            ),
        )
        if devils_advocate_result.blocked:
            now = datetime.now(timezone.utc)
            store.append_compliance_entry(
                ComplianceLedgerEntry(
                    entry_id=str(uuid4()),
                    invoice_id=invoice_id,
                    timestamp=now,
                    event_type="DEVILS_ADVOCATE_BLOCK",
                    details={
                        "reasons": list(devils_advocate_result.reasons),
                        "recommended_actions": list(devils_advocate_result.recommended_actions),
                    },
                )
            )
            ledger.append_event(
                invoice_id=invoice_id,
                actor=Actor.SYSTEM,
                event_type="DEVILS_ADVOCATE_BLOCK",
                timestamp=now,
                data_payload={"reasons": list(devils_advocate_result.reasons)},
            )
            raise HTTPException(
                status_code=409,
                detail="Escalation blocked by devil's advocate verification checks.",
            )

        current_state = forced_current_state or payload.current_state or store.infer_state(invoice_id)
        state_entered_on = payload.state_entered_on or store.infer_state_entered_on(invoice_id, current_state)
        result = runner.run_step(
            invoice=invoice,
            current_state=current_state,
            today=payload.today,
            state_entered_on=state_entered_on,
            debtor_feedback=payload.debtor_feedback,
            system_flag=payload.system_flag,
            insolvency_flag=payload.insolvency_flag,
            payment_plan_proposed=payload.payment_plan_proposed,
            partially_paid=payload.partially_paid,
            regulated_debt_suspected=payload.regulated_debt_suspected,
            jurisdiction_facts=JurisdictionFacts(
                creditor_country_code=payload.creditor_country_code,
                debtor_country_code=payload.debtor_country_code,
                contract_jurisdiction=payload.contract_jurisdiction,
                place_of_supply_country_code=payload.place_of_supply_country_code,
            ),
        )
        preview = communication_severity_engine.preview_for_state(
            invoice=invoice,
            state=result.decision.next_state,
            on_date=payload.today,
            instructions=result.decision.instructions,
            wait_until=result.decision.wait_until,
        )
        return {
            "invoice_id": invoice_id,
            "next_state": result.decision.next_state.value,
            "outreach_frozen": result.decision.outreach_frozen,
            "instructions": result.decision.instructions,
            "documents_to_generate": list(result.decision.documents_to_generate),
            "wait_until": result.decision.wait_until.isoformat() if result.decision.wait_until else None,
            "recorded_at": result.recorded_at.isoformat(),
            "chain_valid": store.verify_chain(invoice_id),
            "viability_assessment": {
                "company_status": viability.company_status,
                "outstanding_amount_gbp": str(viability.outstanding_amount_gbp),
                "projected_total_cost_gbp": str(viability.projected_total_cost_gbp),
                "cost_ratio": str(viability.cost_ratio),
                "disproportionate": viability.disproportionate,
                "notice": viability.notice,
                "recommendation": viability.recommendation,
            },
            "communication_preview": {
                "level": preview.level,
                "stage_name": preview.stage_name,
                "template_version": preview.template_version,
                "message": preview.message,
                "guardrail_flags": list(preview.guardrail_flags),
            },
        }

    @app.post("/invoices/{invoice_id}/evidence-artifacts")
    async def upload_evidence(
        invoice_id: str,
        user_id: str = Form(...),
        artifact_type: ArtifactType = Form(ArtifactType.OTHER),
        file: UploadFile = File(...),
    ) -> dict[str, str]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        invoice_dir = artifacts_root / invoice_id
        invoice_dir.mkdir(parents=True, exist_ok=True)
        original_filename = Path(file.filename or "").name
        content = await file.read()

        def quarantine_and_raise(*, status_code: int, reason: str) -> None:
            quarantine_id = str(uuid4())
            quarantine_invoice_dir = quarantine_root / invoice_id
            quarantine_invoice_dir.mkdir(parents=True, exist_ok=True)
            fallback_name = "unknown.bin" if not original_filename else original_filename
            quarantine_name = f"{quarantine_id}_{Path(fallback_name).name}"
            quarantine_path = quarantine_invoice_dir / quarantine_name
            metadata_path = quarantine_invoice_dir / f"{quarantine_id}.json"
            try:
                quarantine_path.write_bytes(content)
                metadata_path.write_text(
                    json.dumps(
                        {
                            "quarantine_id": quarantine_id,
                            "invoice_id": invoice_id,
                            "reason": reason,
                            "filename": fallback_name,
                            "content_type": (file.content_type or "").strip(),
                            "size_bytes": len(content),
                        },
                        ensure_ascii=True,
                    ),
                    encoding="utf-8",
                )
                ledger.append_event(
                    invoice_id=invoice_id,
                    actor=Actor.SYSTEM,
                    event_type="EVIDENCE_UPLOAD_QUARANTINED",
                    data_payload={
                        "quarantine_id": quarantine_id,
                        "reason": reason,
                        "filename": fallback_name,
                        "content_type": (file.content_type or "").strip(),
                        "size_bytes": len(content),
                        "quarantine_path": str(quarantine_path),
                    },
                )
                security.record_upload_rejection(reason=reason, quarantined=True)
                raise HTTPException(
                    status_code=status_code,
                    detail=f"{reason} Quarantine reference: {quarantine_id}",
                )
            except OSError as exc:
                security.record_upload_rejection(reason=reason, quarantined=False)
                ledger.append_event(
                    invoice_id=invoice_id,
                    actor=Actor.SYSTEM,
                    event_type="EVIDENCE_UPLOAD_REJECTED",
                    data_payload={
                        "reason": reason,
                        "filename": fallback_name,
                        "content_type": (file.content_type or "").strip(),
                        "size_bytes": len(content),
                        "quarantine_error": str(exc),
                    },
                )
                raise HTTPException(
                    status_code=status_code,
                    detail=f"{reason} Upload rejected and quarantine storage failed.",
                )

        if not original_filename or not SAFE_UPLOAD_FILENAME_RE.match(original_filename):
            quarantine_and_raise(status_code=400, reason="Filename violates upload naming policy.")

        extension = Path(original_filename).suffix.lower()
        if extension not in allowed_upload_extension_set:
            quarantine_and_raise(
                status_code=415,
                reason=("Unsupported file extension. Allowed extensions: " + ", ".join(effective_allowed_upload_extensions)),
            )

        if len(content) > effective_max_upload_bytes:
            quarantine_and_raise(
                status_code=413,
                reason=f"Uploaded file exceeds max allowed size ({effective_max_upload_bytes} bytes).",
            )
        content_type = (file.content_type or "").strip().lower()
        if content_type not in allowed_upload_content_type_set:
            quarantine_and_raise(
                status_code=415,
                reason=("Unsupported file content type. Allowed types: " + ", ".join(effective_allowed_upload_content_types)),
            )
        output_name = f"{uuid4()}_{original_filename}"
        output_path = invoice_dir / output_name
        output_path.write_bytes(content)
        artifact = ledger.record_evidence_artifact(
            invoice_id=invoice_id,
            file_path=str(output_path),
            user_id=user_id,
            artifact_type=artifact_type,
        )
        return {
            "invoice_id": artifact.invoice_id,
            "document_id": artifact.document_id,
            "artifact_type": artifact.artifact_type.value,
            "file_hash": artifact.file_hash,
            "file_path": artifact.file_path,
        }

    @app.post("/invoices/{invoice_id}/evidence-bundles")
    def generate_bundle(invoice_id: str, payload: BundleRequest) -> dict[str, str]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        artifacts = store.artifacts_for_invoice(invoice_id)
        compliance_entries = store.compliance_entries_for_invoice(invoice_id)
        ledger_events = store.events_for_invoice(invoice_id)
        delivery_timeline = [
            (
                f"{event.timestamp.isoformat()} | Comm={event.communication_id} | "
                f"State={event.state.value} | Note={event.note or '-'}"
            )
            for event in store.communication_delivery_events_for_invoice(invoice_id)
        ]
        correction_notice_events = {
            "ERROR_CORRECTED",
            "COMMUNICATION_WITHDRAWN",
            "DATA_ACCURACY_CHALLENGE_OPEN",
            "DATA_ACCURACY_CHALLENGE_RESOLVED",
        }
        correction_notices = [
            f"{entry.timestamp.isoformat()} | {entry.event_type} | {entry.details}"
            for entry in compliance_entries
            if entry.event_type in correction_notice_events
        ]
        artifact_inventory = [
            (
                f"{artifact.upload_timestamp.isoformat()} | {artifact.artifact_type.value} | "
                f"Doc={artifact.document_id} | Hash={artifact.file_hash} | Path={artifact.file_path}"
            )
            for artifact in artifacts
        ]

        def _latest_compliance_entry(event_type: str) -> str:
            for entry in reversed(compliance_entries):
                if entry.event_type == event_type:
                    return f"{entry.timestamp.isoformat()} | {event_type} | {entry.details}"
            return f"{event_type} | NOT_RECORDED"

        compliance_snapshot = [
            _latest_compliance_entry("LEGAL_SAFETY_GATE_ACCEPTED"),
            _latest_compliance_entry("CASE_HEALTH_CHECK"),
            _latest_compliance_entry("DISCREPANCY_VALIDATION"),
            _latest_compliance_entry("DATA_ACCURACY_CHALLENGE_OPEN"),
            _latest_compliance_entry("DATA_ACCURACY_CHALLENGE_RESOLVED"),
        ]
        latest_hash = ledger_events[-1].hash if ledger_events else "GENESIS"
        event_chain_attestation = [
            f"Chain Valid: {store.verify_chain(invoice_id)}",
            f"Events Count: {len(ledger_events)}",
            f"Latest Event Hash: {latest_hash}",
        ]

        resolution_artifact_paths: list[str] = []
        if payload.include_resolution_artifacts:
            for plan in store.payment_plan_agreements_for_invoice(invoice_id):
                generated_artifact = _generate_promise_to_pay_artifact(
                    invoice_id=invoice_id,
                    plan_id=plan.plan_id,
                    output_filename=f"promise_to_pay_{plan.plan_id}.pdf",
                )
                resolution_artifact_paths.append(generated_artifact.file_path)
            for offer in store.settlement_offers_for_invoice(invoice_id):
                acceptances = store.settlement_acceptances_for_offer(offer.offer_id)
                if {item.accepter_role for item in acceptances} != {"DEBTOR", "CREDITOR"}:
                    continue
                generated_artifact = _generate_settlement_artifact(
                    invoice_id=invoice_id,
                    offer_id=offer.offer_id,
                    output_filename=f"full_final_settlement_{offer.offer_id}.pdf",
                )
                resolution_artifact_paths.append(generated_artifact.file_path)
        pre_action_notice_paths = [
            artifact.file_path for artifact in artifacts if artifact.artifact_type == ArtifactType.PRE_ACTION_NOTICE
        ]
        output_path = bundles_root / invoice_id / payload.output_filename
        output_path.parent.mkdir(parents=True, exist_ok=True)
        generated_path = runner.compile_evidence_bundle(
            invoice=invoice,
            output_path=str(output_path),
            communications=payload.communications,
            contract_paths=[artifact.file_path for artifact in artifacts if artifact.artifact_type == ArtifactType.CONTRACT],
            proof_of_supply_paths=[
                artifact.file_path
                for artifact in artifacts
                if artifact.artifact_type in (ArtifactType.PROOF_OF_DELIVERY, ArtifactType.OTHER)
            ],
            formal_notices=[*payload.formal_notices, *pre_action_notice_paths],
            debtor_ledger_breakdown=[
                f"{entry.timestamp.date().isoformat()} | {entry.entry_type.value} | GBP {entry.amount_gbp} | {entry.description}"
                for entry in store.debtor_ledger_entries_for_invoice(invoice_id)
            ],
            client_fee_ledger_breakdown=[
                (
                    f"{entry.timestamp.date().isoformat()} | {entry.action_selected.value} | "
                    f"Fee GBP {entry.fee_amount_gbp} + VAT GBP {entry.vat_gbp} | v{entry.pricing_schedule_version}"
                )
                for entry in store.client_fee_entries_for_invoice(invoice_id)
            ],
            resolution_artifact_paths=resolution_artifact_paths,
            communication_delivery_timeline=delivery_timeline,
            correction_withdrawal_notices=correction_notices,
            evidence_artifact_inventory=artifact_inventory,
            compliance_snapshot=compliance_snapshot,
            event_chain_attestation=event_chain_attestation,
        )
        return {"invoice_id": invoice_id, "bundle_path": generated_path}

    @app.post("/invoices/{invoice_id}/ledger-manifests")
    def generate_ledger_manifest(invoice_id: str, payload: ManifestRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        output_path = bundles_root / invoice_id / payload.output_filename
        if payload.output_format == "pdf":
            manifest = manifest_exporter.export_invoice_manifest_pdf(invoice_id=invoice_id, output_path=str(output_path))
        else:
            manifest = manifest_exporter.export_invoice_manifest(invoice_id=invoice_id, output_path=str(output_path))
        return {
            "invoice_id": invoice_id,
            "manifest_path": str(output_path),
            "manifest_format": payload.output_format,
            "chain_valid": manifest["chain_valid"],
            "root_hash": manifest["root_hash"],
            "events_count": manifest["events_count"],
            "signature": manifest["signature"],
        }

    @app.post("/invoices/{invoice_id}/ledger-manifests/verify")
    def verify_ledger_manifest(invoice_id: str, payload: ManifestVerifyRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        manifest_path = bundles_root / invoice_id / payload.output_filename
        if not manifest_path.exists():
            raise HTTPException(status_code=404, detail="Manifest file not found.")
        verification = manifest_exporter.verify_invoice_manifest(
            invoice_id=invoice_id,
            manifest_path=str(manifest_path),
        )
        return {"invoice_id": invoice_id, "manifest_path": str(manifest_path), **verification}

    @app.post("/invoices/{invoice_id}/late-payment-calculations")
    def calculate_late_payment(invoice_id: str, payload: LatePaymentRequest) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        result = late_payment_engine.calculate(
            invoice=invoice,
            as_of_date=payload.as_of_date,
            is_commercial_transaction=payload.is_commercial_transaction,
            contractual_rate=payload.contractual_rate,
            base_rate_override=payload.base_rate_override,
        )
        breakdown = None
        if result.breakdown is not None:
            breakdown = {
                "daily_interest": str(result.breakdown.daily_interest),
                "interest_amount": str(result.breakdown.interest_amount),
                "fixed_compensation": str(result.breakdown.fixed_compensation),
                "total_recovery": str(result.breakdown.total_recovery),
            }
        return {
            "invoice_id": invoice_id,
            "eligible": result.eligible,
            "reason": result.reason,
            "rule_id": result.rule_id,
            "rule_version": result.rule_version,
            "base_rate": str(result.base_rate) if result.base_rate is not None else None,
            "annual_rate": str(result.annual_rate) if result.annual_rate is not None else None,
            "overdue_days": result.overdue_days,
            "breakdown": breakdown,
            "chain_valid": store.verify_chain(invoice_id),
        }

    return app


app = create_app()


def main() -> None:
    import uvicorn

    uvicorn.run("unpaid_invoice_escalator.api:app", host="127.0.0.1", port=8000, reload=False)
