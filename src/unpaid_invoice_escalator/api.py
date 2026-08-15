from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, ConfigDict, Field

from unpaid_invoice_escalator.models import Actor, ArtifactType, DebtorType, Invoice, InvoiceState, Jurisdiction
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.rulepacks import RulePackLoader, RulePackValidationError
from unpaid_invoice_escalator.services.escalation_runner import EscalationRunner
from unpaid_invoice_escalator.services.jurisdiction_engine import JurisdictionFacts
from unpaid_invoice_escalator.services.ledger_manifest_exporter import LedgerManifestExporter
from unpaid_invoice_escalator.services.late_payment_engine import LatePaymentEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger
from unpaid_invoice_escalator.ui import render_home_html


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


def create_app(
    *,
    db_path: str = "data/escalator.db",
    artifacts_dir: str = "data/artifacts",
    bundles_dir: str = "data/bundles",
    manifest_signing_key: str = "dev-only-signing-key",
    manifest_key_id: str = "fcd-local-key",
) -> FastAPI:
    app = FastAPI(title="Unpaid Invoice Escalator API")
    store = SQLiteStore(db_path)
    ledger = SQLiteInvoiceLedger(store)
    runner = EscalationRunner(ledger=ledger)
    late_payment_engine = LatePaymentEngine(ledger=ledger)
    manifest_exporter = LedgerManifestExporter(
        store=store,
        signing_key=manifest_signing_key,
        key_id=manifest_key_id,
    )
    rule_pack_loader = RulePackLoader()
    artifacts_root = Path(artifacts_dir)
    bundles_root = Path(bundles_dir)
    artifacts_root.mkdir(parents=True, exist_ok=True)
    bundles_root.mkdir(parents=True, exist_ok=True)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return render_home_html()

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
    def list_evidence_artifacts(invoice_id: str) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        artifacts = store.artifacts_for_invoice(invoice_id)
        return {
            "invoice_id": invoice_id,
            "count": len(artifacts),
            "artifacts": [
                {
                    "document_id": artifact.document_id,
                    "artifact_type": artifact.artifact_type.value,
                    "file_hash": artifact.file_hash,
                    "file_path": artifact.file_path,
                    "upload_timestamp": artifact.upload_timestamp.isoformat(),
                    "user_id": artifact.user_id,
                }
                for artifact in artifacts
            ],
        }

    @app.get("/invoices/{invoice_id}/ledger-events")
    def list_ledger_events(invoice_id: str, limit: int = 100) -> dict[str, object]:
        invoice = store.get_invoice(invoice_id)
        if invoice is None:
            raise HTTPException(status_code=404, detail="Invoice not found.")
        if limit < 1 or limit > 1000:
            raise HTTPException(status_code=400, detail="limit must be between 1 and 1000.")

        events = store.events_for_invoice(invoice_id)
        selected = events[-limit:]
        return {
            "invoice_id": invoice_id,
            "count": len(selected),
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
