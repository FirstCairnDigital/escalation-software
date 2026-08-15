from __future__ import annotations

from datetime import date
from decimal import Decimal
import os
from pathlib import Path
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
    DebtorLedgerEntryType,
    DebtorType,
    Invoice,
    InvoiceState,
    Jurisdiction,
    RecoveryCostCategory,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.rulepacks import RulePackLoader, RulePackValidationError
from unpaid_invoice_escalator.services.dual_ledger_engine import DualLedgerEngine
from unpaid_invoice_escalator.services.escalation_runner import EscalationRunner
from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts
from unpaid_invoice_escalator.services.ledger_manifest_exporter import LedgerManifestExporter
from unpaid_invoice_escalator.services.late_payment_engine import LatePaymentEngine
from unpaid_invoice_escalator.services.pre_overdue_hygiene_engine import PreOverdueHygieneEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger
from unpaid_invoice_escalator.security import ApiSecurityController, ROLE_RANK
from unpaid_invoice_escalator.ui import render_home_html, render_invoice_workspace_html


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
    contract_jurisdiction: Jurisdiction | None = None
    creditor_country_code: str | None = None
    debtor_country_code: str | None = None
    place_of_supply_country_code: str | None = None


class BundleRequest(BaseModel):
    communications: list[str] = Field(default_factory=list)
    formal_notices: list[str] = Field(default_factory=list)
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
    artifacts_root = Path(artifacts_dir)
    bundles_root = Path(bundles_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    bundles_root.mkdir(parents=True, exist_ok=True)

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

        for check_name, directory in (("artifacts-directory-writable", artifacts_root), ("bundles-directory-writable", bundles_root)):
            probe_path = directory / ".readycheck.tmp"
            try:
                probe_path.write_text("ok", encoding="utf-8")
                probe_path.unlink()
                add_runtime_check(check_name, True, f"Directory writable: {directory}")
            except OSError as exc:
                add_runtime_check(check_name, False, f"Directory write failed for {directory}: {exc}")

        return checks

    def _startup_config_report() -> dict[str, object]:
        runtime_checks = _runtime_readiness_checks()
        combined_checks = [*startup_checks, *runtime_checks]
        errors = [check for check in combined_checks if (not bool(check["passed"])) and check["severity"] == "error"]
        warnings = [check for check in combined_checks if (not bool(check["passed"])) and check["severity"] == "warning"]
        return {
            "environment": effective_env,
            "auth_enabled": effective_auth_enabled,
            "manifest_key_id": manifest_key_id,
            "verification_key_ids": sorted(verification_keys.keys()),
            "rate_limit_per_minute": effective_rate_limit,
            "max_upload_bytes": effective_max_upload_bytes,
            "checks": combined_checks,
            "errors": errors,
            "warnings": warnings,
            "ready": len(errors) == 0,
        }

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

    @app.get("/deployment/startup-config-validation")
    def startup_config_validation() -> dict[str, object]:
        return _startup_config_report()

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
        balances = dual_ledger_engine.balances_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "entry_id": entry.entry_id,
            "amount_gbp": str(entry.amount_gbp),
            "debtor_ledger_balance_gbp": str(balances.debtor_ledger_balance),
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

        current_state = payload.current_state or store.infer_state(invoice_id)
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
        return {
            "invoice_id": invoice_id,
            "next_state": result.decision.next_state.value,
            "outreach_frozen": result.decision.outreach_frozen,
            "instructions": result.decision.instructions,
            "documents_to_generate": list(result.decision.documents_to_generate),
            "wait_until": result.decision.wait_until.isoformat() if result.decision.wait_until else None,
            "recorded_at": result.recorded_at.isoformat(),
            "chain_valid": store.verify_chain(invoice_id),
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
        output_name = f"{uuid4()}_{Path(file.filename or 'artifact.bin').name}"
        output_path = invoice_dir / output_name
        content = await file.read()
        if len(content) > effective_max_upload_bytes:
            raise HTTPException(
                status_code=413,
                detail=f"Uploaded file exceeds max allowed size ({effective_max_upload_bytes} bytes).",
            )
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
            formal_notices=payload.formal_notices,
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
