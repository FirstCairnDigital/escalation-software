from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterator

from unpaid_invoice_escalator.models import (
    Actor,
    ArtifactType,
    AuditTrailEntry,
    BankDetailVerificationState,
    ClientFeeAction,
    ClientFeeEntry,
    CommunicationDeliveryEvent,
    CommunicationDeliveryState,
    CommunicationRecord,
    ComplianceLedgerEntry,
    CompanyStatusCheck,
    ConfirmationOfPayeeResult,
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    DebtorVerificationCase,
    DisputeCarveOut,
    EvidenceArtifact,
    Invoice,
    InvoiceState,
    Jurisdiction,
    LedgerEvent,
    PaymentPlanAgreement,
    PaymentPlanDecision,
    PaymentPlanDecisionStatus,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    PreOverdueHygieneRecord,
    RecoveryCostCategory,
    ReportedPayment,
    ReportedPaymentDecision,
    ReportedPaymentEvidenceLink,
    ReportedPaymentStatus,
    RestrictedCaseNote,
    SettlementAcceptance,
    SettlementBankDetailRecord,
    SettlementOffer,
    SettlementOfferFinalization,
    DebtorType,
)
from unpaid_invoice_escalator.persistence.migrations.postgresql.postgresql_migrations import PostgreSQLMigrationRunner
from unpaid_invoice_escalator.persistence.postgresql_connection import postgresql_connection
from unpaid_invoice_escalator.tenant_context import current_client_id, current_role


class PostgreSQLStore:
    def __init__(self, database_url: str, *, migration_dir: str | Path | None = None) -> None:
        self._database_url = database_url
        self.migration_dir = Path(migration_dir) if migration_dir else Path(__file__).resolve().parent / "migrations" / "postgresql"

    @property
    def database_url(self) -> str:
        return self._database_url

    def _has_invoice_access(self, invoice_client_id: str) -> bool:
        role = current_role.get()
        if role == "admin":
            return True
        return invoice_client_id == current_client_id.get()

    @staticmethod
    def _decimal(value: Any) -> Decimal:
        return Decimal(str(value)) if value is not None else Decimal("0")

    @staticmethod
    def _jsonb(value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, (dict, list, tuple)):
            return value
        return json.loads(value) if isinstance(value, str) else value

    @staticmethod
    def _json_dumps(value: Any) -> Any:
        if value is None:
            return {}
        if isinstance(value, (dict, list, tuple)):
            return value
        return json.loads(value) if isinstance(value, str) else value

    def run_migrations(self) -> list[str]:
        runner = PostgreSQLMigrationRunner(self._database_url, migration_dir=self.migration_dir)
        return runner.apply()

    @contextmanager
    def connection(self) -> Iterator[Any]:
        with postgresql_connection(self._database_url) as conn:
            yield conn

    def create_invoice(self, invoice: Invoice) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO invoices (
                        invoice_id, currency, principal_amount, issue_date, due_date,
                        jurisdiction, debtor_type, client_id, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        invoice.invoice_id,
                        invoice.currency,
                        invoice.principal_amount,
                        invoice.issue_date,
                        invoice.due_date,
                        invoice.jurisdiction.value,
                        invoice.debtor_type.value,
                        invoice.client_id,
                        datetime.now(timezone.utc),
                    ),
                )
                conn.execute(
                    """
                    INSERT INTO debtor_ledger_entries (
                        entry_id, invoice_id, timestamp, entry_type, amount_gbp, description,
                        recovery_cost_category, linked_client_fee_entry_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        f"{invoice.invoice_id}-principal",
                        invoice.invoice_id,
                        datetime.now(timezone.utc),
                        DebtorLedgerEntryType.ORIGINAL_PRINCIPAL.value,
                        invoice.principal_amount,
                        "Original invoice principal recorded at invoice creation.",
                        None,
                        None,
                    ),
                )

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type, client_id
                FROM invoices
                WHERE invoice_id = %s
                """,
                (invoice_id,),
            ).fetchone()
        if row is None:
            return None
        if not self._has_invoice_access(str(row["client_id"])):
            return None
        return Invoice(
            invoice_id=row["invoice_id"],
            currency=row["currency"],
            principal_amount=self._decimal(row["principal_amount"]),
            issue_date=row["issue_date"],
            due_date=row["due_date"],
            jurisdiction=Jurisdiction(row["jurisdiction"]),
            debtor_type=DebtorType(row["debtor_type"]),
            client_id=row["client_id"],
        )

    def list_invoices(self) -> tuple[dict[str, Any], ...]:
        with self.connection() as conn:
            if current_role.get() == "admin":
                rows = conn.execute(
                    """
                    SELECT invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type, client_id, created_at
                    FROM invoices
                    ORDER BY created_at DESC, invoice_id ASC
                    """
                ).fetchall()
            else:
                rows = conn.execute(
                    """
                    SELECT invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type, client_id, created_at
                    FROM invoices
                    WHERE client_id = %s
                    ORDER BY created_at DESC, invoice_id ASC
                    """,
                    (current_client_id.get(),),
                ).fetchall()
        return tuple(
            {
                "invoice_id": row["invoice_id"],
                "currency": row["currency"],
                "principal_amount": self._decimal(row["principal_amount"]),
                "issue_date": row["issue_date"],
                "due_date": row["due_date"],
                "jurisdiction": Jurisdiction(row["jurisdiction"]),
                "debtor_type": DebtorType(row["debtor_type"]),
                "client_id": row["client_id"],
                "created_at": row["created_at"],
            }
            for row in rows
        )

    def append_ledger_event(self, event: LedgerEvent) -> None:
        with self.connection() as conn:
            with conn.transaction():
                latest = conn.execute(
                    "SELECT hash FROM ledger_events WHERE invoice_id = %s ORDER BY event_seq DESC LIMIT 1",
                    (event.invoice_id,),
                ).fetchone()
                expected_previous_hash = latest["hash"] if latest is not None else "GENESIS"
                if event.previous_hash != expected_previous_hash:
                    raise ValueError(
                        f"Concurrent ledger mutation detected for invoice {event.invoice_id}: "
                        f"expected previous hash {expected_previous_hash!r}, got {event.previous_hash!r}."
                    )
                conn.execute(
                    """
                    INSERT INTO ledger_events (
                        event_id, invoice_id, timestamp, actor, event_type,
                        data_payload, previous_hash, hash
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.event_id,
                        event.invoice_id,
                        event.timestamp,
                        event.actor.value,
                        event.event_type,
                        event.data_payload,
                        event.previous_hash,
                        event.hash,
                    ),
                )

    def events_for_invoice(self, invoice_id: str) -> tuple[LedgerEvent, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, invoice_id, timestamp, actor, event_type, data_payload, previous_hash, hash
                FROM ledger_events
                WHERE invoice_id = %s
                ORDER BY event_seq ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            LedgerEvent(
                event_id=row["event_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                actor=Actor(row["actor"]),
                event_type=row["event_type"],
                data_payload=self._jsonb(row["data_payload"]),
                previous_hash=row["previous_hash"],
                hash=row["hash"],
            )
            for row in rows
        )

    def save_evidence_artifact(self, artifact: EvidenceArtifact) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO evidence_artifacts (
                        document_id, invoice_id, artifact_type, file_hash, file_path, upload_timestamp, user_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        artifact.document_id,
                        artifact.invoice_id,
                        artifact.artifact_type.value,
                        artifact.file_hash,
                        artifact.file_path,
                        artifact.upload_timestamp,
                        artifact.user_id,
                    ),
                )

    def artifacts_for_invoice(self, invoice_id: str) -> tuple[EvidenceArtifact, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT document_id, invoice_id, artifact_type, file_hash, file_path, upload_timestamp, user_id
                FROM evidence_artifacts
                WHERE invoice_id = %s
                ORDER BY upload_timestamp ASC, document_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            EvidenceArtifact(
                document_id=row["document_id"],
                invoice_id=row["invoice_id"],
                artifact_type=ArtifactType(row["artifact_type"]),
                file_hash=row["file_hash"],
                file_path=row["file_path"],
                upload_timestamp=row["upload_timestamp"],
                user_id=row["user_id"],
            )
            for row in rows
        )

    def infer_state(self, invoice_id: str) -> InvoiceState:
        events = self.events_for_invoice(invoice_id)
        for event in reversed(events):
            if event.event_type == "STATE_TRANSITION":
                to_state = event.data_payload.get("to_state")
                if isinstance(to_state, str):
                    return InvoiceState(to_state)
        return InvoiceState.ISSUED

    def infer_state_entered_on(self, invoice_id: str, current_state: InvoiceState) -> date | None:
        events = self.events_for_invoice(invoice_id)
        for event in reversed(events):
            if event.event_type != "STATE_TRANSITION":
                continue
            to_state = event.data_payload.get("to_state")
            if to_state == current_state.value:
                return event.timestamp.date()
        return None

    def verify_chain(self, invoice_id: str) -> bool:
        events = self.events_for_invoice(invoice_id)
        previous = "GENESIS"
        for event in events:
            stable_payload = json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str)
            payload = "|".join(
                [
                    event.event_id,
                    event.invoice_id,
                    event.timestamp.isoformat(),
                    event.actor.value,
                    event.event_type,
                    stable_payload,
                    previous,
                ]
            )
            expected_hash = __import__("hashlib").sha256(payload.encode("utf-8")).hexdigest()
            if event.previous_hash != previous or event.hash != expected_hash:
                return False
            previous = event.hash
        return True

    def append_debtor_ledger_entry(self, entry: DebtorLedgerEntry) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO debtor_ledger_entries (
                        entry_id, invoice_id, timestamp, entry_type, amount_gbp, description,
                        recovery_cost_category, linked_client_fee_entry_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry.entry_id,
                        entry.invoice_id,
                        entry.timestamp,
                        entry.entry_type.value,
                        entry.amount_gbp,
                        entry.description,
                        None if entry.recovery_cost_category is None else entry.recovery_cost_category.value,
                        entry.linked_client_fee_entry_id,
                    ),
                )

    def append_client_fee_entry(self, entry: ClientFeeEntry) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO client_fee_entries (
                        entry_id, case_id, client_id, invoice_id, timestamp, pricing_schedule_version,
                        action_selected, fee_amount_gbp, vat_gbp, accepted_by_user, external_fee
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry.entry_id,
                        entry.case_id,
                        entry.client_id,
                        entry.invoice_id,
                        entry.timestamp,
                        entry.pricing_schedule_version,
                        entry.action_selected.value,
                        entry.fee_amount_gbp,
                        entry.vat_gbp,
                        entry.accepted_by_user,
                        entry.external_fee,
                    ),
                )

    def debtor_ledger_entries_for_invoice(self, invoice_id: str) -> tuple[DebtorLedgerEntry, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, invoice_id, timestamp, entry_type, amount_gbp, description,
                       recovery_cost_category, linked_client_fee_entry_id
                FROM debtor_ledger_entries
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, entry_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            DebtorLedgerEntry(
                entry_id=row["entry_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                entry_type=DebtorLedgerEntryType(row["entry_type"]),
                amount_gbp=self._decimal(row["amount_gbp"]),
                description=row["description"],
                recovery_cost_category=(
                    None if row["recovery_cost_category"] is None else RecoveryCostCategory(row["recovery_cost_category"])
                ),
                linked_client_fee_entry_id=row["linked_client_fee_entry_id"],
            )
            for row in rows
        )

    def client_fee_entries_for_invoice(self, invoice_id: str) -> tuple[ClientFeeEntry, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, case_id, client_id, invoice_id, timestamp, pricing_schedule_version,
                       action_selected, fee_amount_gbp, vat_gbp, accepted_by_user, external_fee
                FROM client_fee_entries
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, entry_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            ClientFeeEntry(
                entry_id=row["entry_id"],
                case_id=row["case_id"],
                client_id=row["client_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                pricing_schedule_version=row["pricing_schedule_version"],
                action_selected=ClientFeeAction(row["action_selected"]),
                fee_amount_gbp=self._decimal(row["fee_amount_gbp"]),
                vat_gbp=self._decimal(row["vat_gbp"]),
                accepted_by_user=row["accepted_by_user"],
                external_fee=bool(row["external_fee"]),
            )
            for row in rows
        )

    def debtor_ledger_balance_for_invoice(self, invoice_id: str) -> Decimal:
        entries = self.debtor_ledger_entries_for_invoice(invoice_id)
        return sum((entry.amount_gbp for entry in entries), start=Decimal("0.00"))

    def client_fee_balance_for_invoice(self, invoice_id: str) -> Decimal:
        entries = self.client_fee_entries_for_invoice(invoice_id)
        return sum((entry.fee_amount_gbp + entry.vat_gbp for entry in entries), start=Decimal("0.00"))

    def append_pre_overdue_hygiene_record(self, record: PreOverdueHygieneRecord) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO pre_overdue_hygiene_records (
                        record_id, invoice_id, timestamp, creditor_legal_entity_name, creditor_companies_house_number,
                        creditor_vat_number, creditor_trading_address, debtor_legal_entity_name,
                        debtor_companies_house_number, debtor_vat_number, debtor_trading_address, po_required, po_reference,
                        payment_terms_days, contractual_interest_clause_present,
                        contractual_recovery_clause_present, proof_of_delivery_required, suggested_clause_text,
                        suggested_clause_requires_legal_review, checklist_complete, missing_items_json,
                        warning_tier, format_warnings_json, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.record_id,
                        record.invoice_id,
                        record.timestamp,
                        record.creditor_legal_entity_name,
                        record.creditor_companies_house_number,
                        record.creditor_vat_number,
                        record.creditor_trading_address,
                        record.debtor_legal_entity_name,
                        record.debtor_companies_house_number,
                        record.debtor_vat_number,
                        record.debtor_trading_address,
                        record.po_required,
                        record.po_reference,
                        record.payment_terms_days,
                        record.contractual_interest_clause_present,
                        record.contractual_recovery_clause_present,
                        record.proof_of_delivery_required,
                        record.suggested_clause_text,
                        record.suggested_clause_requires_legal_review,
                        record.checklist_complete,
                        list(record.missing_items),
                        record.warning_tier,
                        list(record.format_warnings),
                        record.notes,
                    ),
                )

    def pre_overdue_hygiene_records_for_invoice(self, invoice_id: str) -> tuple[PreOverdueHygieneRecord, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT record_id, invoice_id, timestamp, creditor_legal_entity_name, creditor_companies_house_number,
                       creditor_vat_number, creditor_trading_address, debtor_legal_entity_name,
                       debtor_companies_house_number, debtor_vat_number, debtor_trading_address,
                       po_required, po_reference, payment_terms_days, contractual_interest_clause_present,
                       contractual_recovery_clause_present, proof_of_delivery_required, suggested_clause_text,
                       suggested_clause_requires_legal_review, checklist_complete, missing_items_json,
                       warning_tier, format_warnings_json, notes
                FROM pre_overdue_hygiene_records
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, record_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            PreOverdueHygieneRecord(
                record_id=row["record_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                creditor_legal_entity_name=row["creditor_legal_entity_name"],
                creditor_companies_house_number=row["creditor_companies_house_number"],
                creditor_vat_number=row["creditor_vat_number"],
                creditor_trading_address=row["creditor_trading_address"],
                debtor_legal_entity_name=row["debtor_legal_entity_name"],
                debtor_companies_house_number=row["debtor_companies_house_number"],
                debtor_vat_number=row["debtor_vat_number"],
                debtor_trading_address=row["debtor_trading_address"],
                po_required=bool(row["po_required"]),
                po_reference=row["po_reference"],
                payment_terms_days=int(row["payment_terms_days"]),
                contractual_interest_clause_present=bool(row["contractual_interest_clause_present"]),
                contractual_recovery_clause_present=bool(row["contractual_recovery_clause_present"]),
                proof_of_delivery_required=bool(row["proof_of_delivery_required"]),
                suggested_clause_text=row["suggested_clause_text"],
                suggested_clause_requires_legal_review=bool(row["suggested_clause_requires_legal_review"]),
                checklist_complete=bool(row["checklist_complete"]),
                missing_items=tuple(self._jsonb(row["missing_items_json"])),
                warning_tier=row["warning_tier"],
                format_warnings=tuple(self._jsonb(row["format_warnings_json"])),
                notes=row["notes"],
            )
            for row in rows
        )

    def append_compliance_entry(self, entry: ComplianceLedgerEntry) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO compliance_ledger_entries (entry_id, invoice_id, timestamp, event_type, details_json)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (
                        entry.entry_id,
                        entry.invoice_id,
                        entry.timestamp,
                        entry.event_type,
                        entry.details,
                    ),
                )

    def append_audit_trail_entry(self, entry: AuditTrailEntry) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO audit_trail_entries (entry_id, invoice_id, timestamp, category, action, actor, details_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        entry.entry_id,
                        entry.invoice_id,
                        entry.timestamp,
                        entry.category,
                        entry.action,
                        entry.actor,
                        entry.details,
                    ),
                )

    def compliance_entries_for_invoice(self, invoice_id: str) -> tuple[ComplianceLedgerEntry, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, invoice_id, timestamp, event_type, details_json
                FROM compliance_ledger_entries
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, entry_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            ComplianceLedgerEntry(
                entry_id=row["entry_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                event_type=row["event_type"],
                details=self._jsonb(row["details_json"]),
            )
            for row in rows
        )

    def audit_trail_entries_for_invoice(self, invoice_id: str) -> tuple[AuditTrailEntry, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, invoice_id, timestamp, category, action, actor, details_json
                FROM audit_trail_entries
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, entry_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            AuditTrailEntry(
                entry_id=row["entry_id"],
                invoice_id=row["invoice_id"],
                timestamp=row["timestamp"],
                category=row["category"],
                action=row["action"],
                actor=row["actor"],
                details=self._jsonb(row["details_json"]),
            )
            for row in rows
        )

    def append_debtor_verification_case(self, record: DebtorVerificationCase) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO debtor_verification_cases (
                        case_id, invoice_id, creditor_name, invoice_reference, verification_code_hash, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.case_id,
                        record.invoice_id,
                        record.creditor_name,
                        record.invoice_reference,
                        record.verification_code_hash,
                        record.created_at,
                    ),
                )

    def debtor_verification_case_for_invoice(self, invoice_id: str) -> DebtorVerificationCase | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT case_id, invoice_id, creditor_name, invoice_reference, verification_code_hash, created_at
                FROM debtor_verification_cases
                WHERE invoice_id = %s
                """,
                (invoice_id,),
            ).fetchone()
        if row is None:
            return None
        return DebtorVerificationCase(
            case_id=row["case_id"],
            invoice_id=row["invoice_id"],
            creditor_name=row["creditor_name"],
            invoice_reference=row["invoice_reference"],
            verification_code_hash=row["verification_code_hash"],
            created_at=row["created_at"],
        )

    def debtor_verification_case_by_case_id(self, case_id: str) -> DebtorVerificationCase | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT d.case_id, d.invoice_id, d.creditor_name, d.invoice_reference, d.verification_code_hash, d.created_at
                FROM debtor_verification_cases d
                JOIN invoices i ON i.invoice_id = d.invoice_id
                WHERE d.case_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (case_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return DebtorVerificationCase(
            case_id=row["case_id"],
            invoice_id=row["invoice_id"],
            creditor_name=row["creditor_name"],
            invoice_reference=row["invoice_reference"],
            verification_code_hash=row["verification_code_hash"],
            created_at=row["created_at"],
        )

    def append_communication(self, record: CommunicationRecord) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO communications (
                        communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.communication_id,
                        record.invoice_id,
                        record.channel,
                        record.recipient,
                        record.subject,
                        record.body_summary,
                        record.automated,
                        record.created_at,
                    ),
                )

    def append_reported_payment(self, report: ReportedPayment) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO reported_payments (
                        report_id, invoice_id, case_id, debtor_identifier, reported_at,
                        amount_gbp, payment_reference, payment_date, details, plan_id, installment_id, settlement_offer_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        report.report_id,
                        report.invoice_id,
                        report.case_id,
                        report.debtor_identifier,
                        report.reported_at,
                        report.amount_gbp,
                        report.payment_reference,
                        report.payment_date,
                        report.details,
                        report.plan_id,
                        report.installment_id,
                        report.settlement_offer_id,
                    ),
                )

    def reported_payment_by_id(self, report_id: str) -> ReportedPayment | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT r.report_id, r.invoice_id, r.case_id, r.debtor_identifier, r.reported_at,
                       r.amount_gbp, r.payment_reference, r.payment_date, r.details, r.plan_id, r.installment_id, r.settlement_offer_id
                FROM reported_payments r
                JOIN invoices i ON i.invoice_id = r.invoice_id
                WHERE r.report_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (report_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return ReportedPayment(
            report_id=row["report_id"],
            invoice_id=row["invoice_id"],
            case_id=row["case_id"],
            debtor_identifier=row["debtor_identifier"],
            reported_at=row["reported_at"],
            amount_gbp=self._decimal(row["amount_gbp"]),
            payment_reference=row["payment_reference"],
            payment_date=None if row["payment_date"] is None else row["payment_date"],
            details=row["details"],
            plan_id=row["plan_id"],
            installment_id=row["installment_id"],
            settlement_offer_id=row["settlement_offer_id"],
        )

    def reported_payments_for_invoice(self, invoice_id: str) -> tuple[ReportedPayment, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT report_id, invoice_id, case_id, debtor_identifier, reported_at,
                       amount_gbp, payment_reference, payment_date, details, plan_id, installment_id, settlement_offer_id
                FROM reported_payments
                WHERE invoice_id = %s
                ORDER BY reported_at ASC, report_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            ReportedPayment(
                report_id=row["report_id"],
                invoice_id=row["invoice_id"],
                case_id=row["case_id"],
                debtor_identifier=row["debtor_identifier"],
                reported_at=row["reported_at"],
                amount_gbp=self._decimal(row["amount_gbp"]),
                payment_reference=row["payment_reference"],
                payment_date=None if row["payment_date"] is None else row["payment_date"],
                details=row["details"],
                plan_id=row["plan_id"],
                installment_id=row["installment_id"],
                settlement_offer_id=row["settlement_offer_id"],
            )
            for row in rows
        )

    def append_reported_payment_decision(self, decision: ReportedPaymentDecision) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO reported_payment_decisions (
                        decision_id, report_id, invoice_id, decided_at, decided_by, status,
                        reason, notes, confirmed_amount_gbp, linked_debtor_entry_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        decision.decision_id,
                        decision.report_id,
                        decision.invoice_id,
                        decision.decided_at,
                        decision.decided_by,
                        decision.status.value,
                        decision.reason,
                        decision.notes,
                        decision.confirmed_amount_gbp,
                        decision.linked_debtor_entry_id,
                    ),
                )

    def reported_payment_decisions_for_report(self, report_id: str) -> tuple[ReportedPaymentDecision, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT decision_id, report_id, invoice_id, decided_at, decided_by, status,
                       reason, notes, confirmed_amount_gbp, linked_debtor_entry_id
                FROM reported_payment_decisions
                WHERE report_id = %s
                ORDER BY decided_at ASC, decision_id ASC
                """,
                (report_id,),
            ).fetchall()
        return tuple(
            ReportedPaymentDecision(
                decision_id=row["decision_id"],
                report_id=row["report_id"],
                invoice_id=row["invoice_id"],
                decided_at=row["decided_at"],
                decided_by=row["decided_by"],
                status=ReportedPaymentStatus(row["status"]),
                reason=row["reason"],
                notes=row["notes"],
                confirmed_amount_gbp=(None if row["confirmed_amount_gbp"] is None else self._decimal(row["confirmed_amount_gbp"])),
                linked_debtor_entry_id=row["linked_debtor_entry_id"],
            )
            for row in rows
        )

    def append_reported_payment_evidence_link(self, link: ReportedPaymentEvidenceLink) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO reported_payment_evidence_links (
                        link_id, report_id, invoice_id, document_id, linked_at, linked_by
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        link.link_id,
                        link.report_id,
                        link.invoice_id,
                        link.document_id,
                        link.linked_at,
                        link.linked_by,
                    ),
                )

    def reported_payment_evidence_links_for_report(self, report_id: str) -> tuple[ReportedPaymentEvidenceLink, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT link_id, report_id, invoice_id, document_id, linked_at, linked_by
                FROM reported_payment_evidence_links
                WHERE report_id = %s
                ORDER BY linked_at ASC, link_id ASC
                """,
                (report_id,),
            ).fetchall()
        return tuple(
            ReportedPaymentEvidenceLink(
                link_id=row["link_id"],
                report_id=row["report_id"],
                invoice_id=row["invoice_id"],
                document_id=row["document_id"],
                linked_at=row["linked_at"],
                linked_by=row["linked_by"],
            )
            for row in rows
        )

    def communication_for_id(self, communication_id: str) -> CommunicationRecord | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT c.communication_id, c.invoice_id, c.channel, c.recipient, c.subject, c.body_summary, c.automated, c.created_at
                FROM communications c
                JOIN invoices i ON i.invoice_id = c.invoice_id
                WHERE c.communication_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (communication_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return CommunicationRecord(
            communication_id=row["communication_id"],
            invoice_id=row["invoice_id"],
            channel=row["channel"],
            recipient=row["recipient"],
            subject=row["subject"],
            body_summary=row["body_summary"],
            automated=bool(row["automated"]),
            created_at=row["created_at"],
        )

    def communications_for_invoice(self, invoice_id: str) -> tuple[CommunicationRecord, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at
                FROM communications
                WHERE invoice_id = %s
                ORDER BY created_at ASC, communication_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            CommunicationRecord(
                communication_id=row["communication_id"],
                invoice_id=row["invoice_id"],
                channel=row["channel"],
                recipient=row["recipient"],
                subject=row["subject"],
                body_summary=row["body_summary"],
                automated=bool(row["automated"]),
                created_at=row["created_at"],
            )
            for row in rows
        )

    def append_communication_delivery_event(self, event: CommunicationDeliveryEvent) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO communication_delivery_events (
                        event_id, communication_id, invoice_id, state, timestamp, note
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        event.event_id,
                        event.communication_id,
                        event.invoice_id,
                        event.state.value,
                        event.timestamp,
                        event.note,
                    ),
                )

    def communication_delivery_events_for_communication(
        self, communication_id: str
    ) -> tuple[CommunicationDeliveryEvent, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, communication_id, invoice_id, state, timestamp, note
                FROM communication_delivery_events
                WHERE communication_id = %s
                ORDER BY timestamp ASC, event_id ASC
                """,
                (communication_id,),
            ).fetchall()
        return tuple(
            CommunicationDeliveryEvent(
                event_id=row["event_id"],
                communication_id=row["communication_id"],
                invoice_id=row["invoice_id"],
                state=CommunicationDeliveryState(row["state"]),
                timestamp=row["timestamp"],
                note=row["note"],
            )
            for row in rows
        )

    def communication_delivery_events_for_invoice(self, invoice_id: str) -> tuple[CommunicationDeliveryEvent, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, communication_id, invoice_id, state, timestamp, note
                FROM communication_delivery_events
                WHERE invoice_id = %s
                ORDER BY timestamp ASC, event_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            CommunicationDeliveryEvent(
                event_id=row["event_id"],
                communication_id=row["communication_id"],
                invoice_id=row["invoice_id"],
                state=CommunicationDeliveryState(row["state"]),
                timestamp=row["timestamp"],
                note=row["note"],
            )
            for row in rows
        )

    def append_payment_plan_agreement(self, agreement: PaymentPlanAgreement) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO payment_plan_agreements (
                        plan_id, invoice_id, created_at, proposed_by, installment_amount_gbp,
                        installment_count, first_due_date, frequency_days, notes, proposer_role, parent_plan_id, version_number
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        agreement.plan_id,
                        agreement.invoice_id,
                        agreement.created_at,
                        agreement.proposed_by,
                        agreement.installment_amount_gbp,
                        agreement.installment_count,
                        agreement.first_due_date,
                        agreement.frequency_days,
                        agreement.notes,
                        agreement.proposer_role,
                        agreement.parent_plan_id,
                        agreement.version_number,
                    ),
                )

    def payment_plan_agreement_by_id(self, plan_id: str) -> PaymentPlanAgreement | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT p.plan_id, p.invoice_id, p.created_at, p.proposed_by, p.installment_amount_gbp,
                       p.installment_count, p.first_due_date, p.frequency_days, p.notes, p.proposer_role, p.parent_plan_id,
                       p.version_number
                FROM payment_plan_agreements p
                JOIN invoices i ON i.invoice_id = p.invoice_id
                WHERE p.plan_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (plan_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return PaymentPlanAgreement(
            plan_id=row["plan_id"],
            invoice_id=row["invoice_id"],
            created_at=row["created_at"],
            proposed_by=row["proposed_by"],
            installment_amount_gbp=self._decimal(row["installment_amount_gbp"]),
            installment_count=int(row["installment_count"]),
            first_due_date=row["first_due_date"],
            frequency_days=int(row["frequency_days"]),
            notes=row["notes"],
            proposer_role=row["proposer_role"],
            parent_plan_id=row["parent_plan_id"],
            version_number=int(row["version_number"]),
        )

    def append_payment_plan_installments(self, installments: tuple[PaymentPlanInstallment, ...]) -> None:
        if not installments:
            return
        with self.connection() as conn:
            with conn.transaction():
                conn.executemany(
                    """
                    INSERT INTO payment_plan_installments (
                        installment_id, plan_id, invoice_id, due_date, amount_gbp, sequence_number
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            item.installment_id,
                            item.plan_id,
                            item.invoice_id,
                            item.due_date,
                            item.amount_gbp,
                            item.sequence_number,
                        )
                        for item in installments
                    ],
                )

    def payment_plan_agreements_for_invoice(self, invoice_id: str) -> tuple[PaymentPlanAgreement, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT plan_id, invoice_id, created_at, proposed_by, installment_amount_gbp,
                       installment_count, first_due_date, frequency_days, notes, proposer_role, parent_plan_id, version_number
                FROM payment_plan_agreements
                WHERE invoice_id = %s
                ORDER BY created_at ASC, plan_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            PaymentPlanAgreement(
                plan_id=row["plan_id"],
                invoice_id=row["invoice_id"],
                created_at=row["created_at"],
                proposed_by=row["proposed_by"],
                installment_amount_gbp=self._decimal(row["installment_amount_gbp"]),
                installment_count=int(row["installment_count"]),
                first_due_date=row["first_due_date"],
                frequency_days=int(row["frequency_days"]),
                notes=row["notes"],
                proposer_role=row["proposer_role"],
                parent_plan_id=row["parent_plan_id"],
                version_number=int(row["version_number"]),
            )
            for row in rows
        )

    def payment_plan_installments_for_plan(self, plan_id: str) -> tuple[PaymentPlanInstallment, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT installment_id, plan_id, invoice_id, due_date, amount_gbp, sequence_number
                FROM payment_plan_installments
                WHERE plan_id = %s
                ORDER BY sequence_number ASC, installment_id ASC
                """,
                (plan_id,),
            ).fetchall()
        return tuple(
            PaymentPlanInstallment(
                installment_id=row["installment_id"],
                plan_id=row["plan_id"],
                invoice_id=row["invoice_id"],
                due_date=row["due_date"],
                amount_gbp=self._decimal(row["amount_gbp"]),
                sequence_number=int(row["sequence_number"]),
            )
            for row in rows
        )

    def append_payment_plan_payment(self, payment: PaymentPlanPayment) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO payment_plan_payments (
                        payment_id, plan_id, installment_id, invoice_id, paid_at, amount_gbp, recorded_by, reported_payment_id
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        payment.payment_id,
                        payment.plan_id,
                        payment.installment_id,
                        payment.invoice_id,
                        payment.paid_at,
                        payment.amount_gbp,
                        payment.recorded_by,
                        payment.reported_payment_id,
                    ),
                )

    def payment_plan_payments_for_plan(self, plan_id: str) -> tuple[PaymentPlanPayment, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT payment_id, plan_id, installment_id, invoice_id, paid_at, amount_gbp, recorded_by, reported_payment_id
                FROM payment_plan_payments
                WHERE plan_id = %s
                ORDER BY paid_at ASC, payment_id ASC
                """,
                (plan_id,),
            ).fetchall()
        return tuple(
            PaymentPlanPayment(
                payment_id=row["payment_id"],
                plan_id=row["plan_id"],
                installment_id=row["installment_id"],
                invoice_id=row["invoice_id"],
                paid_at=row["paid_at"],
                amount_gbp=self._decimal(row["amount_gbp"]),
                recorded_by=row["recorded_by"],
                reported_payment_id=row["reported_payment_id"],
            )
            for row in rows
        )

    def append_payment_plan_decision(self, decision: PaymentPlanDecision) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO payment_plan_decisions (
                        decision_id, plan_id, invoice_id, decided_at, decided_by, actor_role, status, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        decision.decision_id,
                        decision.plan_id,
                        decision.invoice_id,
                        decision.decided_at,
                        decision.decided_by,
                        decision.actor_role,
                        decision.status.value,
                        decision.notes,
                    ),
                )

    def payment_plan_decisions_for_plan(self, plan_id: str) -> tuple[PaymentPlanDecision, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT decision_id, plan_id, invoice_id, decided_at, decided_by, actor_role, status, notes
                FROM payment_plan_decisions
                WHERE plan_id = %s
                ORDER BY decided_at ASC, decision_id ASC
                """,
                (plan_id,),
            ).fetchall()
        return tuple(
            PaymentPlanDecision(
                decision_id=row["decision_id"],
                plan_id=row["plan_id"],
                invoice_id=row["invoice_id"],
                decided_at=row["decided_at"],
                decided_by=row["decided_by"],
                actor_role=row["actor_role"],
                status=PaymentPlanDecisionStatus(row["status"]),
                notes=row["notes"],
            )
            for row in rows
        )

    def append_settlement_offer(self, offer: SettlementOffer) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO settlement_offers (
                        offer_id, invoice_id, offered_at, offered_by, offered_amount_gbp, expiry_date, notes
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        offer.offer_id,
                        offer.invoice_id,
                        offer.offered_at,
                        offer.offered_by,
                        offer.offered_amount_gbp,
                        offer.expiry_date,
                        offer.notes,
                    ),
                )

    def settlement_offers_for_invoice(self, invoice_id: str) -> tuple[SettlementOffer, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT offer_id, invoice_id, offered_at, offered_by, offered_amount_gbp, expiry_date, notes
                FROM settlement_offers
                WHERE invoice_id = %s
                ORDER BY offered_at ASC, offer_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            SettlementOffer(
                offer_id=row["offer_id"],
                invoice_id=row["invoice_id"],
                offered_at=row["offered_at"],
                offered_by=row["offered_by"],
                offered_amount_gbp=self._decimal(row["offered_amount_gbp"]),
                expiry_date=row["expiry_date"],
                notes=row["notes"],
            )
            for row in rows
        )

    def settlement_offer_by_id(self, offer_id: str) -> SettlementOffer | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT s.offer_id, s.invoice_id, s.offered_at, s.offered_by, s.offered_amount_gbp, s.expiry_date, s.notes
                FROM settlement_offers s
                JOIN invoices i ON i.invoice_id = s.invoice_id
                WHERE s.offer_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (offer_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return SettlementOffer(
            offer_id=row["offer_id"],
            invoice_id=row["invoice_id"],
            offered_at=row["offered_at"],
            offered_by=row["offered_by"],
            offered_amount_gbp=self._decimal(row["offered_amount_gbp"]),
            expiry_date=row["expiry_date"],
            notes=row["notes"],
        )

    def append_settlement_acceptance(self, acceptance: SettlementAcceptance) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO settlement_acceptances (
                        acceptance_id, offer_id, invoice_id, accepted_at, accepted_by, accepter_role
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                    """,
                    (
                        acceptance.acceptance_id,
                        acceptance.offer_id,
                        acceptance.invoice_id,
                        acceptance.accepted_at,
                        acceptance.accepted_by,
                        acceptance.accepter_role,
                    ),
                )

    def settlement_acceptances_for_offer(self, offer_id: str) -> tuple[SettlementAcceptance, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT acceptance_id, offer_id, invoice_id, accepted_at, accepted_by, accepter_role
                FROM settlement_acceptances
                WHERE offer_id = %s
                ORDER BY accepted_at ASC, acceptance_id ASC
                """,
                (offer_id,),
            ).fetchall()
        return tuple(
            SettlementAcceptance(
                acceptance_id=row["acceptance_id"],
                offer_id=row["offer_id"],
                invoice_id=row["invoice_id"],
                accepted_at=row["accepted_at"],
                accepted_by=row["accepted_by"],
                accepter_role=row["accepter_role"],
            )
            for row in rows
        )

    def append_settlement_offer_finalization(self, finalization: SettlementOfferFinalization) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO settlement_offer_finalizations (
                        finalization_id, offer_id, invoice_id, finalized_at, finalized_by,
                        triggering_report_id, confirmed_payment_total_gbp, outstanding_before_gbp,
                        settlement_discount_applied_gbp
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        finalization.finalization_id,
                        finalization.offer_id,
                        finalization.invoice_id,
                        finalization.finalized_at,
                        finalization.finalized_by,
                        finalization.triggering_report_id,
                        finalization.confirmed_payment_total_gbp,
                        finalization.outstanding_before_gbp,
                        finalization.settlement_discount_applied_gbp,
                    ),
                )

    def settlement_offer_finalization_by_offer_id(self, offer_id: str) -> SettlementOfferFinalization | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT finalization_id, offer_id, invoice_id, finalized_at, finalized_by,
                       triggering_report_id, confirmed_payment_total_gbp, outstanding_before_gbp,
                       settlement_discount_applied_gbp
                FROM settlement_offer_finalizations
                WHERE offer_id = %s
                ORDER BY finalized_at DESC, finalization_id DESC
                LIMIT 1
                """,
                (offer_id,),
            ).fetchone()
        if row is None:
            return None
        return SettlementOfferFinalization(
            finalization_id=row["finalization_id"],
            offer_id=row["offer_id"],
            invoice_id=row["invoice_id"],
            finalized_at=row["finalized_at"],
            finalized_by=row["finalized_by"],
            triggering_report_id=row["triggering_report_id"],
            confirmed_payment_total_gbp=self._decimal(row["confirmed_payment_total_gbp"]),
            outstanding_before_gbp=self._decimal(row["outstanding_before_gbp"]),
            settlement_discount_applied_gbp=self._decimal(row["settlement_discount_applied_gbp"]),
        )

    def append_dispute_carve_out(self, carve_out: DisputeCarveOut) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO dispute_carve_outs (
                        carve_out_id, invoice_id, created_at, disputed_amount_gbp, undisputed_amount_gbp, reason, created_by
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        carve_out.carve_out_id,
                        carve_out.invoice_id,
                        carve_out.created_at,
                        carve_out.disputed_amount_gbp,
                        carve_out.undisputed_amount_gbp,
                        carve_out.reason,
                        carve_out.created_by,
                    ),
                )

    def dispute_carve_outs_for_invoice(self, invoice_id: str) -> tuple[DisputeCarveOut, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT carve_out_id, invoice_id, created_at, disputed_amount_gbp, undisputed_amount_gbp, reason, created_by
                FROM dispute_carve_outs
                WHERE invoice_id = %s
                ORDER BY created_at ASC, carve_out_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            DisputeCarveOut(
                carve_out_id=row["carve_out_id"],
                invoice_id=row["invoice_id"],
                created_at=row["created_at"],
                disputed_amount_gbp=self._decimal(row["disputed_amount_gbp"]),
                undisputed_amount_gbp=self._decimal(row["undisputed_amount_gbp"]),
                reason=row["reason"],
                created_by=row["created_by"],
            )
            for row in rows
        )

    def append_settlement_bank_detail_record(self, record: SettlementBankDetailRecord) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO settlement_bank_detail_records (
                        record_id, invoice_id, created_at, updated_by, account_holder_name, sort_code,
                        account_number_last4, iban_last4, cop_state, cop_result, expected_payee_name,
                        dual_control_approved_by, mfa_reauthenticated
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        record.record_id,
                        record.invoice_id,
                        record.created_at,
                        record.updated_by,
                        record.account_holder_name,
                        record.sort_code,
                        record.account_number_last4,
                        record.iban_last4,
                        record.cop_state.value,
                        None if record.cop_result is None else record.cop_result.value,
                        record.expected_payee_name,
                        record.dual_control_approved_by,
                        record.mfa_reauthenticated,
                    ),
                )

    def settlement_bank_detail_records_for_invoice(self, invoice_id: str) -> tuple[SettlementBankDetailRecord, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT record_id, invoice_id, created_at, updated_by, account_holder_name, sort_code,
                       account_number_last4, iban_last4, cop_state, cop_result, expected_payee_name,
                       dual_control_approved_by, mfa_reauthenticated
                FROM settlement_bank_detail_records
                WHERE invoice_id = %s
                ORDER BY created_at ASC, record_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            SettlementBankDetailRecord(
                record_id=row["record_id"],
                invoice_id=row["invoice_id"],
                created_at=row["created_at"],
                updated_by=row["updated_by"],
                account_holder_name=row["account_holder_name"],
                sort_code=row["sort_code"],
                account_number_last4=row["account_number_last4"],
                iban_last4=row["iban_last4"],
                cop_state=BankDetailVerificationState(row["cop_state"]),
                cop_result=None if row["cop_result"] is None else ConfirmationOfPayeeResult(row["cop_result"]),
                expected_payee_name=row["expected_payee_name"],
                dual_control_approved_by=row["dual_control_approved_by"],
                mfa_reauthenticated=bool(row["mfa_reauthenticated"]),
            )
            for row in rows
        )

    def latest_settlement_bank_detail_for_invoice(self, invoice_id: str) -> SettlementBankDetailRecord | None:
        records = self.settlement_bank_detail_records_for_invoice(invoice_id)
        if not records:
            return None
        return records[-1]

    def append_company_status_check(self, check: CompanyStatusCheck) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO company_status_checks (
                        check_id, invoice_id, checked_at, checked_by, company_status, source,
                        evidence_summary, company_number, official_register_url, review_due_date,
                        notes, restrictions_recommended_json
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        check.check_id,
                        check.invoice_id,
                        check.checked_at,
                        check.checked_by,
                        check.company_status,
                        check.source,
                        check.evidence_summary,
                        check.company_number,
                        check.official_register_url,
                        check.review_due_date,
                        check.notes,
                        list(check.restrictions_recommended),
                    ),
                )

    def company_status_checks_for_invoice(self, invoice_id: str) -> tuple[CompanyStatusCheck, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT check_id, invoice_id, checked_at, checked_by, company_status, source,
                       evidence_summary, company_number, official_register_url, review_due_date,
                       notes, restrictions_recommended_json
                FROM company_status_checks
                WHERE invoice_id = %s
                ORDER BY checked_at ASC, check_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            CompanyStatusCheck(
                check_id=row["check_id"],
                invoice_id=row["invoice_id"],
                checked_at=row["checked_at"],
                checked_by=row["checked_by"],
                company_status=row["company_status"],
                source=row["source"],
                evidence_summary=row["evidence_summary"],
                company_number=row["company_number"],
                official_register_url=row["official_register_url"],
                review_due_date=None if row["review_due_date"] is None else row["review_due_date"],
                notes=row["notes"],
                restrictions_recommended=tuple(self._jsonb(row["restrictions_recommended_json"])),
            )
            for row in rows
        )

    def latest_company_status_check_for_invoice(self, invoice_id: str) -> CompanyStatusCheck | None:
        checks = self.company_status_checks_for_invoice(invoice_id)
        if not checks:
            return None
        return checks[-1]

    def company_status_check_by_id(self, check_id: str) -> CompanyStatusCheck | None:
        with self.connection() as conn:
            row = conn.execute(
                """
                SELECT c.check_id, c.invoice_id, c.checked_at, c.checked_by, c.company_status, c.source,
                       c.evidence_summary, c.company_number, c.official_register_url, c.review_due_date,
                       c.notes, c.restrictions_recommended_json
                FROM company_status_checks c
                JOIN invoices i ON i.invoice_id = c.invoice_id
                WHERE c.check_id = %s
                  AND (%s = 'admin' OR i.client_id = %s)
                """,
                (check_id, current_role.get(), current_client_id.get()),
            ).fetchone()
        if row is None:
            return None
        return CompanyStatusCheck(
            check_id=row["check_id"],
            invoice_id=row["invoice_id"],
            checked_at=row["checked_at"],
            checked_by=row["checked_by"],
            company_status=row["company_status"],
            source=row["source"],
            evidence_summary=row["evidence_summary"],
            company_number=row["company_number"],
            official_register_url=row["official_register_url"],
            review_due_date=None if row["review_due_date"] is None else row["review_due_date"],
            notes=row["notes"],
            restrictions_recommended=tuple(self._jsonb(row["restrictions_recommended_json"])),
        )

    def append_restricted_case_note(self, note: RestrictedCaseNote) -> None:
        with self.connection() as conn:
            with conn.transaction():
                conn.execute(
                    """
                    INSERT INTO restricted_case_notes (
                        note_id, invoice_id, created_at, created_by, note_category, summary,
                        sensitive_details, related_event_type, access_scope
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        note.note_id,
                        note.invoice_id,
                        note.created_at,
                        note.created_by,
                        note.note_category,
                        note.summary,
                        note.sensitive_details,
                        note.related_event_type,
                        note.access_scope,
                    ),
                )

    def restricted_case_notes_for_invoice(self, invoice_id: str) -> tuple[RestrictedCaseNote, ...]:
        with self.connection() as conn:
            rows = conn.execute(
                """
                SELECT note_id, invoice_id, created_at, created_by, note_category, summary,
                       sensitive_details, related_event_type, access_scope
                FROM restricted_case_notes
                WHERE invoice_id = %s
                ORDER BY created_at ASC, note_id ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            RestrictedCaseNote(
                note_id=row["note_id"],
                invoice_id=row["invoice_id"],
                created_at=row["created_at"],
                created_by=row["created_by"],
                note_category=row["note_category"],
                summary=row["summary"],
                sensitive_details=row["sensitive_details"],
                related_event_type=row["related_event_type"],
                access_scope=row["access_scope"],
            )
            for row in rows
        )


__all__ = ["PostgreSQLStore"]
