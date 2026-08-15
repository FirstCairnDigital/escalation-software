from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from unpaid_invoice_escalator.models import (
    Actor,
    ArtifactType,
    ClientFeeAction,
    ClientFeeEntry,
    CommunicationDeliveryEvent,
    CommunicationDeliveryState,
    CommunicationRecord,
    ComplianceLedgerEntry,
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    DebtorVerificationCase,
    DisputeCarveOut,
    DebtorType,
    EvidenceArtifact,
    Invoice,
    InvoiceState,
    Jurisdiction,
    LedgerEvent,
    PaymentPlanAgreement,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    PreOverdueHygieneRecord,
    RecoveryCostCategory,
    SettlementAcceptance,
    SettlementOffer,
)


class SQLiteStore:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @property
    def db_path(self) -> str:
        return self._db_path

    @contextmanager
    def _connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def _init_schema(self) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS invoices (
                    invoice_id TEXT PRIMARY KEY,
                    currency TEXT NOT NULL,
                    principal_amount TEXT NOT NULL,
                    issue_date TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    jurisdiction TEXT NOT NULL,
                    debtor_type TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS evidence_artifacts (
                    document_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    artifact_type TEXT NOT NULL DEFAULT 'OTHER',
                    file_hash TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    upload_timestamp TEXT NOT NULL,
                    user_id TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(evidence_artifacts)").fetchall()
            }
            if "artifact_type" not in columns:
                conn.execute(
                    "ALTER TABLE evidence_artifacts ADD COLUMN artifact_type TEXT NOT NULL DEFAULT 'OTHER'"
                )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS ledger_events (
                    event_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    data_payload TEXT NOT NULL,
                    previous_hash TEXT NOT NULL,
                    hash TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS debtor_ledger_entries (
                    entry_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    entry_type TEXT NOT NULL,
                    amount_gbp TEXT NOT NULL,
                    description TEXT NOT NULL,
                    recovery_cost_category TEXT,
                    linked_client_fee_entry_id TEXT,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS client_fee_entries (
                    entry_id TEXT PRIMARY KEY,
                    case_id TEXT NOT NULL,
                    client_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    pricing_schedule_version TEXT NOT NULL,
                    action_selected TEXT NOT NULL,
                    fee_amount_gbp TEXT NOT NULL,
                    vat_gbp TEXT NOT NULL,
                    accepted_by_user TEXT NOT NULL,
                    external_fee INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pre_overdue_hygiene_records (
                    record_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    creditor_legal_entity_name TEXT NOT NULL,
                    creditor_companies_house_number TEXT NOT NULL,
                    creditor_vat_number TEXT NOT NULL,
                    creditor_trading_address TEXT NOT NULL,
                    debtor_legal_entity_name TEXT NOT NULL,
                    debtor_companies_house_number TEXT NOT NULL DEFAULT '',
                    debtor_vat_number TEXT NOT NULL DEFAULT '',
                    debtor_trading_address TEXT NOT NULL,
                    po_required INTEGER NOT NULL,
                    po_reference TEXT,
                    payment_terms_days INTEGER NOT NULL,
                    contractual_interest_clause_present INTEGER NOT NULL,
                    contractual_recovery_clause_present INTEGER NOT NULL,
                    proof_of_delivery_required INTEGER NOT NULL,
                    suggested_clause_text TEXT,
                    suggested_clause_requires_legal_review INTEGER NOT NULL,
                    checklist_complete INTEGER NOT NULL,
                    missing_items_json TEXT NOT NULL,
                    warning_tier TEXT NOT NULL DEFAULT 'NONE',
                    format_warnings_json TEXT NOT NULL DEFAULT '[]',
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS compliance_ledger_entries (
                    entry_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS debtor_verification_cases (
                    case_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL UNIQUE,
                    creditor_name TEXT NOT NULL,
                    invoice_reference TEXT NOT NULL,
                    verification_code_hash TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS communications (
                    communication_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    recipient TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    body_summary TEXT NOT NULL,
                    automated INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS communication_delivery_events (
                    event_id TEXT PRIMARY KEY,
                    communication_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    note TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(communication_id) REFERENCES communications(communication_id),
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            communication_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(communications)").fetchall()
            }
            if "automated" not in communication_columns:
                conn.execute("ALTER TABLE communications ADD COLUMN automated INTEGER NOT NULL DEFAULT 1")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_plan_agreements (
                    plan_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    proposed_by TEXT NOT NULL,
                    installment_amount_gbp TEXT NOT NULL,
                    installment_count INTEGER NOT NULL,
                    first_due_date TEXT NOT NULL,
                    frequency_days INTEGER NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_plan_installments (
                    installment_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    due_date TEXT NOT NULL,
                    amount_gbp TEXT NOT NULL,
                    sequence_number INTEGER NOT NULL,
                    FOREIGN KEY(plan_id) REFERENCES payment_plan_agreements(plan_id),
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS payment_plan_payments (
                    payment_id TEXT PRIMARY KEY,
                    plan_id TEXT NOT NULL,
                    installment_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    paid_at TEXT NOT NULL,
                    amount_gbp TEXT NOT NULL,
                    recorded_by TEXT NOT NULL,
                    FOREIGN KEY(plan_id) REFERENCES payment_plan_agreements(plan_id),
                    FOREIGN KEY(installment_id) REFERENCES payment_plan_installments(installment_id),
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settlement_offers (
                    offer_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    offered_at TEXT NOT NULL,
                    offered_by TEXT NOT NULL,
                    offered_amount_gbp TEXT NOT NULL,
                    expiry_date TEXT NOT NULL,
                    notes TEXT NOT NULL DEFAULT '',
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS settlement_acceptances (
                    acceptance_id TEXT PRIMARY KEY,
                    offer_id TEXT NOT NULL,
                    invoice_id TEXT NOT NULL,
                    accepted_at TEXT NOT NULL,
                    accepted_by TEXT NOT NULL,
                    accepter_role TEXT NOT NULL,
                    FOREIGN KEY(offer_id) REFERENCES settlement_offers(offer_id),
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS dispute_carve_outs (
                    carve_out_id TEXT PRIMARY KEY,
                    invoice_id TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    disputed_amount_gbp TEXT NOT NULL,
                    undisputed_amount_gbp TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    FOREIGN KEY(invoice_id) REFERENCES invoices(invoice_id)
                )
                """
            )
            hygiene_columns = {
                row["name"]
                for row in conn.execute("PRAGMA table_info(pre_overdue_hygiene_records)").fetchall()
            }
            if "warning_tier" not in hygiene_columns:
                conn.execute(
                    "ALTER TABLE pre_overdue_hygiene_records ADD COLUMN warning_tier TEXT NOT NULL DEFAULT 'NONE'"
                )
            if "format_warnings_json" not in hygiene_columns:
                conn.execute(
                    "ALTER TABLE pre_overdue_hygiene_records ADD COLUMN format_warnings_json TEXT NOT NULL DEFAULT '[]'"
                )
            if "debtor_companies_house_number" not in hygiene_columns:
                conn.execute(
                    "ALTER TABLE pre_overdue_hygiene_records ADD COLUMN debtor_companies_house_number TEXT NOT NULL DEFAULT ''"
                )
            if "debtor_vat_number" not in hygiene_columns:
                conn.execute(
                    "ALTER TABLE pre_overdue_hygiene_records ADD COLUMN debtor_vat_number TEXT NOT NULL DEFAULT ''"
                )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_ledger_events_invoice_time
                ON ledger_events(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_debtor_ledger_invoice_time
                ON debtor_ledger_entries(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_client_fee_invoice_time
                ON client_fee_entries(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_hygiene_records_invoice_time
                ON pre_overdue_hygiene_records(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_compliance_ledger_invoice_time
                ON compliance_ledger_entries(invoice_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_artifacts_invoice
                ON evidence_artifacts(invoice_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_verification_cases_invoice
                ON debtor_verification_cases(invoice_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_communications_invoice_time
                ON communications(invoice_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_comm_delivery_events_comm_time
                ON communication_delivery_events(communication_id, timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_payment_plans_invoice
                ON payment_plan_agreements(invoice_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_payment_installments_plan
                ON payment_plan_installments(plan_id, sequence_number)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_payment_plan_payments_installment
                ON payment_plan_payments(installment_id, paid_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_settlement_offers_invoice
                ON settlement_offers(invoice_id, offered_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_settlement_acceptances_offer
                ON settlement_acceptances(offer_id, accepted_at)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_dispute_carve_outs_invoice
                ON dispute_carve_outs(invoice_id, created_at)
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoices_no_update
                BEFORE UPDATE ON invoices
                BEGIN
                    SELECT RAISE(ABORT, 'invoices is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_invoices_no_delete
                BEFORE DELETE ON invoices
                BEGIN
                    SELECT RAISE(ABORT, 'invoices is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_update
                BEFORE UPDATE ON ledger_events
                BEGIN
                    SELECT RAISE(ABORT, 'ledger_events is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_ledger_events_no_delete
                BEFORE DELETE ON ledger_events
                BEGIN
                    SELECT RAISE(ABORT, 'ledger_events is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_evidence_artifacts_no_update
                BEFORE UPDATE ON evidence_artifacts
                BEGIN
                    SELECT RAISE(ABORT, 'evidence_artifacts is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_evidence_artifacts_no_delete
                BEFORE DELETE ON evidence_artifacts
                BEGIN
                    SELECT RAISE(ABORT, 'evidence_artifacts is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_debtor_ledger_no_update
                BEFORE UPDATE ON debtor_ledger_entries
                BEGIN
                    SELECT RAISE(ABORT, 'debtor_ledger_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_debtor_ledger_no_delete
                BEFORE DELETE ON debtor_ledger_entries
                BEGIN
                    SELECT RAISE(ABORT, 'debtor_ledger_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_client_fee_no_update
                BEFORE UPDATE ON client_fee_entries
                BEGIN
                    SELECT RAISE(ABORT, 'client_fee_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_client_fee_no_delete
                BEFORE DELETE ON client_fee_entries
                BEGIN
                    SELECT RAISE(ABORT, 'client_fee_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_hygiene_records_no_update
                BEFORE UPDATE ON pre_overdue_hygiene_records
                BEGIN
                    SELECT RAISE(ABORT, 'pre_overdue_hygiene_records is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_hygiene_records_no_delete
                BEFORE DELETE ON pre_overdue_hygiene_records
                BEGIN
                    SELECT RAISE(ABORT, 'pre_overdue_hygiene_records is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_compliance_ledger_no_update
                BEFORE UPDATE ON compliance_ledger_entries
                BEGIN
                    SELECT RAISE(ABORT, 'compliance_ledger_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_compliance_ledger_no_delete
                BEFORE DELETE ON compliance_ledger_entries
                BEGIN
                    SELECT RAISE(ABORT, 'compliance_ledger_entries is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_debtor_verification_no_update
                BEFORE UPDATE ON debtor_verification_cases
                BEGIN
                    SELECT RAISE(ABORT, 'debtor_verification_cases is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_debtor_verification_no_delete
                BEFORE DELETE ON debtor_verification_cases
                BEGIN
                    SELECT RAISE(ABORT, 'debtor_verification_cases is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_communications_no_update
                BEFORE UPDATE ON communications
                BEGIN
                    SELECT RAISE(ABORT, 'communications is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_communications_no_delete
                BEFORE DELETE ON communications
                BEGIN
                    SELECT RAISE(ABORT, 'communications is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_communication_delivery_events_no_update
                BEFORE UPDATE ON communication_delivery_events
                BEGIN
                    SELECT RAISE(ABORT, 'communication_delivery_events is append-only');
                END;
                """
            )
            conn.execute(
                """
                CREATE TRIGGER IF NOT EXISTS trg_communication_delivery_events_no_delete
                BEFORE DELETE ON communication_delivery_events
                BEGIN
                    SELECT RAISE(ABORT, 'communication_delivery_events is append-only');
                END;
                """
            )
            for table_name in (
                "payment_plan_agreements",
                "payment_plan_installments",
                "payment_plan_payments",
                "settlement_offers",
                "settlement_acceptances",
                "dispute_carve_outs",
            ):
                conn.execute(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS trg_{table_name}_no_update
                    BEFORE UPDATE ON {table_name}
                    BEGIN
                        SELECT RAISE(ABORT, '{table_name} is append-only');
                    END;
                    """
                )
                conn.execute(
                    f"""
                    CREATE TRIGGER IF NOT EXISTS trg_{table_name}_no_delete
                    BEFORE DELETE ON {table_name}
                    BEGIN
                        SELECT RAISE(ABORT, '{table_name} is append-only');
                    END;
                    """
                )
            conn.commit()

    def create_invoice(self, invoice: Invoice) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO invoices (
                    invoice_id, currency, principal_amount, issue_date, due_date,
                    jurisdiction, debtor_type, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    invoice.invoice_id,
                    invoice.currency,
                    str(invoice.principal_amount),
                    invoice.issue_date.isoformat(),
                    invoice.due_date.isoformat(),
                    invoice.jurisdiction.value,
                    invoice.debtor_type.value,
                    datetime.now(timezone.utc).isoformat(),
                ),
            )
            conn.commit()

    def get_invoice(self, invoice_id: str) -> Invoice | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT invoice_id, currency, principal_amount, issue_date, due_date, jurisdiction, debtor_type
                FROM invoices
                WHERE invoice_id = ?
                """,
                (invoice_id,),
            ).fetchone()
        if row is None:
            return None
        return Invoice(
            invoice_id=row["invoice_id"],
            currency=row["currency"],
            principal_amount=Decimal(row["principal_amount"]),
            issue_date=date.fromisoformat(row["issue_date"]),
            due_date=date.fromisoformat(row["due_date"]),
            jurisdiction=Jurisdiction(row["jurisdiction"]),
            debtor_type=DebtorType(row["debtor_type"]),
        )

    def append_ledger_event(self, event: LedgerEvent) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO ledger_events (
                    event_id, invoice_id, timestamp, actor, event_type,
                    data_payload, previous_hash, hash
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.invoice_id,
                    event.timestamp.isoformat(),
                    event.actor.value,
                    event.event_type,
                    json.dumps(event.data_payload, sort_keys=True, separators=(",", ":"), default=str),
                    event.previous_hash,
                    event.hash,
                ),
            )
            conn.commit()

    def events_for_invoice(self, invoice_id: str) -> tuple[LedgerEvent, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, invoice_id, timestamp, actor, event_type, data_payload, previous_hash, hash
                FROM ledger_events
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            LedgerEvent(
                event_id=row["event_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                actor=Actor(row["actor"]),
                event_type=row["event_type"],
                data_payload=json.loads(row["data_payload"]),
                previous_hash=row["previous_hash"],
                hash=row["hash"],
            )
            for row in rows
        )

    def save_evidence_artifact(self, artifact: EvidenceArtifact) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO evidence_artifacts (
                    document_id, invoice_id, artifact_type, file_hash, file_path, upload_timestamp, user_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    artifact.document_id,
                    artifact.invoice_id,
                    artifact.artifact_type.value,
                    artifact.file_hash,
                    artifact.file_path,
                    artifact.upload_timestamp.isoformat(),
                    artifact.user_id,
                ),
            )
            conn.commit()

    def artifacts_for_invoice(self, invoice_id: str) -> tuple[EvidenceArtifact, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT document_id, invoice_id, file_hash, file_path, upload_timestamp, user_id
                     , artifact_type
                FROM evidence_artifacts
                WHERE invoice_id = ?
                ORDER BY upload_timestamp ASC, rowid ASC
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
                upload_timestamp=datetime.fromisoformat(row["upload_timestamp"]),
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
            expected_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
            if event.previous_hash != previous or event.hash != expected_hash:
                return False
            previous = event.hash
        return True

    def append_debtor_ledger_entry(self, entry: DebtorLedgerEntry) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO debtor_ledger_entries (
                    entry_id, invoice_id, timestamp, entry_type, amount_gbp, description,
                    recovery_cost_category, linked_client_fee_entry_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.invoice_id,
                    entry.timestamp.isoformat(),
                    entry.entry_type.value,
                    str(entry.amount_gbp),
                    entry.description,
                    None if entry.recovery_cost_category is None else entry.recovery_cost_category.value,
                    entry.linked_client_fee_entry_id,
                ),
            )
            conn.commit()

    def append_client_fee_entry(self, entry: ClientFeeEntry) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO client_fee_entries (
                    entry_id, case_id, client_id, invoice_id, timestamp, pricing_schedule_version,
                    action_selected, fee_amount_gbp, vat_gbp, accepted_by_user, external_fee
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.case_id,
                    entry.client_id,
                    entry.invoice_id,
                    entry.timestamp.isoformat(),
                    entry.pricing_schedule_version,
                    entry.action_selected.value,
                    str(entry.fee_amount_gbp),
                    str(entry.vat_gbp),
                    entry.accepted_by_user,
                    1 if entry.external_fee else 0,
                ),
            )
            conn.commit()

    def debtor_ledger_entries_for_invoice(self, invoice_id: str) -> tuple[DebtorLedgerEntry, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, invoice_id, timestamp, entry_type, amount_gbp, description,
                       recovery_cost_category, linked_client_fee_entry_id
                FROM debtor_ledger_entries
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            DebtorLedgerEntry(
                entry_id=row["entry_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                entry_type=DebtorLedgerEntryType(row["entry_type"]),
                amount_gbp=Decimal(row["amount_gbp"]),
                description=row["description"],
                recovery_cost_category=(
                    None
                    if row["recovery_cost_category"] is None
                    else RecoveryCostCategory(row["recovery_cost_category"])
                ),
                linked_client_fee_entry_id=row["linked_client_fee_entry_id"],
            )
            for row in rows
        )

    def client_fee_entries_for_invoice(self, invoice_id: str) -> tuple[ClientFeeEntry, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, case_id, client_id, invoice_id, timestamp, pricing_schedule_version,
                       action_selected, fee_amount_gbp, vat_gbp, accepted_by_user, external_fee
                FROM client_fee_entries
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            ClientFeeEntry(
                entry_id=row["entry_id"],
                case_id=row["case_id"],
                client_id=row["client_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                pricing_schedule_version=row["pricing_schedule_version"],
                action_selected=ClientFeeAction(row["action_selected"]),
                fee_amount_gbp=Decimal(row["fee_amount_gbp"]),
                vat_gbp=Decimal(row["vat_gbp"]),
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
        with self._connection() as conn:
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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.record_id,
                    record.invoice_id,
                    record.timestamp.isoformat(),
                    record.creditor_legal_entity_name,
                    record.creditor_companies_house_number,
                    record.creditor_vat_number,
                    record.creditor_trading_address,
                    record.debtor_legal_entity_name,
                    record.debtor_companies_house_number,
                    record.debtor_vat_number,
                    record.debtor_trading_address,
                    1 if record.po_required else 0,
                    record.po_reference,
                    record.payment_terms_days,
                    1 if record.contractual_interest_clause_present else 0,
                    1 if record.contractual_recovery_clause_present else 0,
                    1 if record.proof_of_delivery_required else 0,
                    record.suggested_clause_text,
                    1 if record.suggested_clause_requires_legal_review else 0,
                    1 if record.checklist_complete else 0,
                    json.dumps(list(record.missing_items), sort_keys=True),
                    record.warning_tier,
                    json.dumps(list(record.format_warnings), sort_keys=True),
                    record.notes,
                ),
            )
            conn.commit()

    def pre_overdue_hygiene_records_for_invoice(self, invoice_id: str) -> tuple[PreOverdueHygieneRecord, ...]:
        with self._connection() as conn:
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
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            PreOverdueHygieneRecord(
                record_id=row["record_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
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
                missing_items=tuple(json.loads(row["missing_items_json"])),
                warning_tier=row["warning_tier"],
                format_warnings=tuple(json.loads(row["format_warnings_json"])),
                notes=row["notes"],
            )
            for row in rows
        )

    def append_compliance_entry(self, entry: ComplianceLedgerEntry) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO compliance_ledger_entries (
                    entry_id, invoice_id, timestamp, event_type, details_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    entry.entry_id,
                    entry.invoice_id,
                    entry.timestamp.isoformat(),
                    entry.event_type,
                    json.dumps(entry.details, sort_keys=True, separators=(",", ":"), default=str),
                ),
            )
            conn.commit()

    def compliance_entries_for_invoice(self, invoice_id: str) -> tuple[ComplianceLedgerEntry, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT entry_id, invoice_id, timestamp, event_type, details_json
                FROM compliance_ledger_entries
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            ComplianceLedgerEntry(
                entry_id=row["entry_id"],
                invoice_id=row["invoice_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                event_type=row["event_type"],
                details=json.loads(row["details_json"]),
            )
            for row in rows
        )

    def append_debtor_verification_case(self, record: DebtorVerificationCase) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO debtor_verification_cases (
                    case_id, invoice_id, creditor_name, invoice_reference, verification_code_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record.case_id,
                    record.invoice_id,
                    record.creditor_name,
                    record.invoice_reference,
                    record.verification_code_hash,
                    record.created_at.isoformat(),
                ),
            )
            conn.commit()

    def debtor_verification_case_for_invoice(self, invoice_id: str) -> DebtorVerificationCase | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT case_id, invoice_id, creditor_name, invoice_reference, verification_code_hash, created_at
                FROM debtor_verification_cases
                WHERE invoice_id = ?
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def debtor_verification_case_by_case_id(self, case_id: str) -> DebtorVerificationCase | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT case_id, invoice_id, creditor_name, invoice_reference, verification_code_hash, created_at
                FROM debtor_verification_cases
                WHERE case_id = ?
                """,
                (case_id,),
            ).fetchone()
        if row is None:
            return None
        return DebtorVerificationCase(
            case_id=row["case_id"],
            invoice_id=row["invoice_id"],
            creditor_name=row["creditor_name"],
            invoice_reference=row["invoice_reference"],
            verification_code_hash=row["verification_code_hash"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def append_communication(self, record: CommunicationRecord) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO communications (
                    communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record.communication_id,
                    record.invoice_id,
                    record.channel,
                    record.recipient,
                    record.subject,
                    record.body_summary,
                    1 if record.automated else 0,
                    record.created_at.isoformat(),
                ),
            )
            conn.commit()

    def communication_for_id(self, communication_id: str) -> CommunicationRecord | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at
                FROM communications
                WHERE communication_id = ?
                """,
                (communication_id,),
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
            created_at=datetime.fromisoformat(row["created_at"]),
        )

    def communications_for_invoice(self, invoice_id: str) -> tuple[CommunicationRecord, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at
                FROM communications
                WHERE invoice_id = ?
                ORDER BY created_at ASC, rowid ASC
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
                created_at=datetime.fromisoformat(row["created_at"]),
            )
            for row in rows
        )

    def append_communication_delivery_event(self, event: CommunicationDeliveryEvent) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO communication_delivery_events (
                    event_id, communication_id, invoice_id, state, timestamp, note
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    event.event_id,
                    event.communication_id,
                    event.invoice_id,
                    event.state.value,
                    event.timestamp.isoformat(),
                    event.note,
                ),
            )
            conn.commit()

    def communication_delivery_events_for_communication(
        self, communication_id: str
    ) -> tuple[CommunicationDeliveryEvent, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, communication_id, invoice_id, state, timestamp, note
                FROM communication_delivery_events
                WHERE communication_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (communication_id,),
            ).fetchall()
        return tuple(
            CommunicationDeliveryEvent(
                event_id=row["event_id"],
                communication_id=row["communication_id"],
                invoice_id=row["invoice_id"],
                state=CommunicationDeliveryState(row["state"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                note=row["note"],
            )
            for row in rows
        )

    def communication_delivery_events_for_invoice(self, invoice_id: str) -> tuple[CommunicationDeliveryEvent, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT event_id, communication_id, invoice_id, state, timestamp, note
                FROM communication_delivery_events
                WHERE invoice_id = ?
                ORDER BY timestamp ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            CommunicationDeliveryEvent(
                event_id=row["event_id"],
                communication_id=row["communication_id"],
                invoice_id=row["invoice_id"],
                state=CommunicationDeliveryState(row["state"]),
                timestamp=datetime.fromisoformat(row["timestamp"]),
                note=row["note"],
            )
            for row in rows
        )

    def append_payment_plan_agreement(self, agreement: PaymentPlanAgreement) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO payment_plan_agreements (
                    plan_id, invoice_id, created_at, proposed_by, installment_amount_gbp,
                    installment_count, first_due_date, frequency_days, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    agreement.plan_id,
                    agreement.invoice_id,
                    agreement.created_at.isoformat(),
                    agreement.proposed_by,
                    str(agreement.installment_amount_gbp),
                    agreement.installment_count,
                    agreement.first_due_date.isoformat(),
                    agreement.frequency_days,
                    agreement.notes,
                ),
            )
            conn.commit()

    def append_payment_plan_installments(self, installments: tuple[PaymentPlanInstallment, ...]) -> None:
        if not installments:
            return
        with self._connection() as conn:
            conn.executemany(
                """
                INSERT INTO payment_plan_installments (
                    installment_id, plan_id, invoice_id, due_date, amount_gbp, sequence_number
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                [
                    (
                        item.installment_id,
                        item.plan_id,
                        item.invoice_id,
                        item.due_date.isoformat(),
                        str(item.amount_gbp),
                        item.sequence_number,
                    )
                    for item in installments
                ],
            )
            conn.commit()

    def payment_plan_agreements_for_invoice(self, invoice_id: str) -> tuple[PaymentPlanAgreement, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT plan_id, invoice_id, created_at, proposed_by, installment_amount_gbp,
                       installment_count, first_due_date, frequency_days, notes
                FROM payment_plan_agreements
                WHERE invoice_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            PaymentPlanAgreement(
                plan_id=row["plan_id"],
                invoice_id=row["invoice_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                proposed_by=row["proposed_by"],
                installment_amount_gbp=Decimal(row["installment_amount_gbp"]),
                installment_count=int(row["installment_count"]),
                first_due_date=date.fromisoformat(row["first_due_date"]),
                frequency_days=int(row["frequency_days"]),
                notes=row["notes"],
            )
            for row in rows
        )

    def payment_plan_installments_for_plan(self, plan_id: str) -> tuple[PaymentPlanInstallment, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT installment_id, plan_id, invoice_id, due_date, amount_gbp, sequence_number
                FROM payment_plan_installments
                WHERE plan_id = ?
                ORDER BY sequence_number ASC, rowid ASC
                """,
                (plan_id,),
            ).fetchall()
        return tuple(
            PaymentPlanInstallment(
                installment_id=row["installment_id"],
                plan_id=row["plan_id"],
                invoice_id=row["invoice_id"],
                due_date=date.fromisoformat(row["due_date"]),
                amount_gbp=Decimal(row["amount_gbp"]),
                sequence_number=int(row["sequence_number"]),
            )
            for row in rows
        )

    def append_payment_plan_payment(self, payment: PaymentPlanPayment) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO payment_plan_payments (
                    payment_id, plan_id, installment_id, invoice_id, paid_at, amount_gbp, recorded_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    payment.payment_id,
                    payment.plan_id,
                    payment.installment_id,
                    payment.invoice_id,
                    payment.paid_at.isoformat(),
                    str(payment.amount_gbp),
                    payment.recorded_by,
                ),
            )
            conn.commit()

    def payment_plan_payments_for_plan(self, plan_id: str) -> tuple[PaymentPlanPayment, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT payment_id, plan_id, installment_id, invoice_id, paid_at, amount_gbp, recorded_by
                FROM payment_plan_payments
                WHERE plan_id = ?
                ORDER BY paid_at ASC, rowid ASC
                """,
                (plan_id,),
            ).fetchall()
        return tuple(
            PaymentPlanPayment(
                payment_id=row["payment_id"],
                plan_id=row["plan_id"],
                installment_id=row["installment_id"],
                invoice_id=row["invoice_id"],
                paid_at=datetime.fromisoformat(row["paid_at"]),
                amount_gbp=Decimal(row["amount_gbp"]),
                recorded_by=row["recorded_by"],
            )
            for row in rows
        )

    def append_settlement_offer(self, offer: SettlementOffer) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO settlement_offers (
                    offer_id, invoice_id, offered_at, offered_by, offered_amount_gbp, expiry_date, notes
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    offer.offer_id,
                    offer.invoice_id,
                    offer.offered_at.isoformat(),
                    offer.offered_by,
                    str(offer.offered_amount_gbp),
                    offer.expiry_date.isoformat(),
                    offer.notes,
                ),
            )
            conn.commit()

    def settlement_offers_for_invoice(self, invoice_id: str) -> tuple[SettlementOffer, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT offer_id, invoice_id, offered_at, offered_by, offered_amount_gbp, expiry_date, notes
                FROM settlement_offers
                WHERE invoice_id = ?
                ORDER BY offered_at ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            SettlementOffer(
                offer_id=row["offer_id"],
                invoice_id=row["invoice_id"],
                offered_at=datetime.fromisoformat(row["offered_at"]),
                offered_by=row["offered_by"],
                offered_amount_gbp=Decimal(row["offered_amount_gbp"]),
                expiry_date=date.fromisoformat(row["expiry_date"]),
                notes=row["notes"],
            )
            for row in rows
        )

    def settlement_offer_by_id(self, offer_id: str) -> SettlementOffer | None:
        with self._connection() as conn:
            row = conn.execute(
                """
                SELECT offer_id, invoice_id, offered_at, offered_by, offered_amount_gbp, expiry_date, notes
                FROM settlement_offers
                WHERE offer_id = ?
                """,
                (offer_id,),
            ).fetchone()
        if row is None:
            return None
        return SettlementOffer(
            offer_id=row["offer_id"],
            invoice_id=row["invoice_id"],
            offered_at=datetime.fromisoformat(row["offered_at"]),
            offered_by=row["offered_by"],
            offered_amount_gbp=Decimal(row["offered_amount_gbp"]),
            expiry_date=date.fromisoformat(row["expiry_date"]),
            notes=row["notes"],
        )

    def append_settlement_acceptance(self, acceptance: SettlementAcceptance) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO settlement_acceptances (
                    acceptance_id, offer_id, invoice_id, accepted_at, accepted_by, accepter_role
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    acceptance.acceptance_id,
                    acceptance.offer_id,
                    acceptance.invoice_id,
                    acceptance.accepted_at.isoformat(),
                    acceptance.accepted_by,
                    acceptance.accepter_role,
                ),
            )
            conn.commit()

    def settlement_acceptances_for_offer(self, offer_id: str) -> tuple[SettlementAcceptance, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT acceptance_id, offer_id, invoice_id, accepted_at, accepted_by, accepter_role
                FROM settlement_acceptances
                WHERE offer_id = ?
                ORDER BY accepted_at ASC, rowid ASC
                """,
                (offer_id,),
            ).fetchall()
        return tuple(
            SettlementAcceptance(
                acceptance_id=row["acceptance_id"],
                offer_id=row["offer_id"],
                invoice_id=row["invoice_id"],
                accepted_at=datetime.fromisoformat(row["accepted_at"]),
                accepted_by=row["accepted_by"],
                accepter_role=row["accepter_role"],
            )
            for row in rows
        )

    def append_dispute_carve_out(self, carve_out: DisputeCarveOut) -> None:
        with self._connection() as conn:
            conn.execute(
                """
                INSERT INTO dispute_carve_outs (
                    carve_out_id, invoice_id, created_at, disputed_amount_gbp, undisputed_amount_gbp, reason, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    carve_out.carve_out_id,
                    carve_out.invoice_id,
                    carve_out.created_at.isoformat(),
                    str(carve_out.disputed_amount_gbp),
                    str(carve_out.undisputed_amount_gbp),
                    carve_out.reason,
                    carve_out.created_by,
                ),
            )
            conn.commit()

    def dispute_carve_outs_for_invoice(self, invoice_id: str) -> tuple[DisputeCarveOut, ...]:
        with self._connection() as conn:
            rows = conn.execute(
                """
                SELECT carve_out_id, invoice_id, created_at, disputed_amount_gbp, undisputed_amount_gbp, reason, created_by
                FROM dispute_carve_outs
                WHERE invoice_id = ?
                ORDER BY created_at ASC, rowid ASC
                """,
                (invoice_id,),
            ).fetchall()
        return tuple(
            DisputeCarveOut(
                carve_out_id=row["carve_out_id"],
                invoice_id=row["invoice_id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                disputed_amount_gbp=Decimal(row["disputed_amount_gbp"]),
                undisputed_amount_gbp=Decimal(row["undisputed_amount_gbp"]),
                reason=row["reason"],
                created_by=row["created_by"],
            )
            for row in rows
        )
