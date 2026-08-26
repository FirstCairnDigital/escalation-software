from datetime import date
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from unpaid_invoice_escalator.models import (
    Actor,
    ArtifactType,
    AuditTrailEntry,
    BankDetailVerificationState,
    ClientFeeAction,
    CompanyStatusCheck,
    DebtorLedgerEntry,
    DebtorLedgerEntryType,
    CommunicationDeliveryEvent,
    CommunicationDeliveryState,
    CommunicationRecord,
    ComplianceLedgerEntry,
    ConfirmationOfPayeeResult,
    DebtorVerificationCase,
    DebtorType,
    Invoice,
    Jurisdiction,
    PaymentPlanAgreement,
    PaymentPlanDecision,
    PaymentPlanDecisionStatus,
    PreOverdueHygieneRecord,
    ReportedPayment,
    ReportedPaymentDecision,
    ReportedPaymentEvidenceLink,
    ReportedPaymentStatus,
    RestrictedCaseNote,
    SettlementBankDetailRecord,
    SettlementOffer,
    SettlementOfferFinalization,
)
from unpaid_invoice_escalator.persistence.sqlite_store import SQLiteStore
from unpaid_invoice_escalator.services.dual_ledger_engine import DualLedgerEngine
from unpaid_invoice_escalator.services.sqlite_invoice_ledger import SQLiteInvoiceLedger


class TestSQLiteStore(unittest.TestCase):
    def test_persists_invoice_and_ledger_chain(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            invoice = Invoice(
                invoice_id="inv-db-1",
                currency="GBP",
                principal_amount=Decimal("999.99"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            ledger.append_event(
                invoice_id=invoice.invoice_id,
                actor=Actor.SYSTEM,
                event_type="INVOICE_CREATED",
                data_payload={"hello": "world"},
            )

            loaded = store.get_invoice(invoice.invoice_id)
            self.assertIsNotNone(loaded)
            self.assertEqual(loaded.invoice_id, invoice.invoice_id)
            self.assertEqual(store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("999.99"))
            self.assertEqual(store.debtor_ledger_entries_for_invoice(invoice.invoice_id)[0].entry_type, DebtorLedgerEntryType.ORIGINAL_PRINCIPAL)
            self.assertTrue(store.verify_chain(invoice.invoice_id))

    def test_invoice_balance_reaches_zero_after_full_payment(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator-settled.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-settled",
                currency="GBP",
                principal_amount=Decimal("250"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_debtor_ledger_entry(
                DebtorLedgerEntry(
                    entry_id="payment-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    entry_type=DebtorLedgerEntryType.PAYMENT_RECEIVED,
                    amount_gbp=Decimal("-250"),
                    description="Paid in full",
                )
            )
            self.assertEqual(store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("0.00"))

    def test_audit_trail_entries_are_persisted_and_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator-audit.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-audit",
                currency="GBP",
                principal_amount=Decimal("300"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_audit_trail_entry(
                AuditTrailEntry(
                    entry_id="audit-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    category="COMPLIANCE",
                    action="CASE_HEALTH_CHECK_RECORDED",
                    actor="SYSTEM",
                    details={"case_confidence": "READY"},
                )
            )
            entries = store.audit_trail_entries_for_invoice(invoice.invoice_id)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].action, "CASE_HEALTH_CHECK_RECORDED")

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE audit_trail_entries SET action = 'ALTERED'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM audit_trail_entries")
                conn.rollback()
            finally:
                conn.close()

    def test_append_only_triggers_block_update_and_delete(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            invoice = Invoice(
                invoice_id="inv-db-2",
                currency="GBP",
                principal_amount=Decimal("1200"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            ledger.append_event(
                invoice_id=invoice.invoice_id,
                actor=Actor.SYSTEM,
                event_type="INVOICE_CREATED",
                data_payload={"step": 1},
            )

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(
                        "UPDATE ledger_events SET event_type = ? WHERE invoice_id = ?",
                        ("ALTERED", invoice.invoice_id),
                    )
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute(
                        "DELETE FROM ledger_events WHERE invoice_id = ?",
                        (invoice.invoice_id,),
                    )
                conn.rollback()
            finally:
                conn.close()

    def test_debtor_verification_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-6",
                currency="GBP",
                principal_amount=Decimal("650"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_debtor_verification_case(
                DebtorVerificationCase(
                    case_id="FCD-R-2026-000001",
                    invoice_id=invoice.invoice_id,
                    creditor_name="Creditor Ltd",
                    invoice_reference="INV-6",
                    verification_code_hash="abc123",
                    created_at=datetime.now(timezone.utc),
                )
            )
            self.assertIsNotNone(store.debtor_verification_case_for_invoice(invoice.invoice_id))
            self.assertIsNotNone(store.debtor_verification_case_by_case_id("FCD-R-2026-000001"))

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE debtor_verification_cases SET creditor_name = 'X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM debtor_verification_cases")
                conn.rollback()
            finally:
                conn.close()

    def test_reported_payment_tables_are_persisted_and_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator-reported-payments.db")
            store = SQLiteStore(db_path)
            ledger = SQLiteInvoiceLedger(store)
            invoice = Invoice(
                invoice_id="inv-db-payment-report",
                currency="GBP",
                principal_amount=Decimal("650"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_reported_payment(
                ReportedPayment(
                    report_id="report-1",
                    invoice_id=invoice.invoice_id,
                    case_id="FCD-R-2026-000111",
                    debtor_identifier="debtor@example.com",
                    reported_at=datetime.now(timezone.utc),
                    amount_gbp=Decimal("125.00"),
                    payment_reference="PAY-REF-1",
                    payment_date=date(2026, 2, 10),
                    details="Reported from portal",
                    settlement_offer_id="offer-1",
                )
            )
            store.append_reported_payment_decision(
                ReportedPaymentDecision(
                    decision_id="decision-1",
                    report_id="report-1",
                    invoice_id=invoice.invoice_id,
                    decided_at=datetime.now(timezone.utc),
                    decided_by="USER-1",
                    status=ReportedPaymentStatus.NEEDS_EVIDENCE,
                    notes="Please upload remittance.",
                )
            )
            artifact_path = Path(tmp_dir) / "doc-1.txt"
            artifact_path.write_text("payment evidence", encoding="utf-8")
            artifact = ledger.record_evidence_artifact(
                invoice_id=invoice.invoice_id,
                file_path=str(artifact_path),
                user_id="debtor@example.com",
                artifact_type=ArtifactType.PAYMENT_EVIDENCE,
            )
            store.append_reported_payment_evidence_link(
                ReportedPaymentEvidenceLink(
                    link_id="link-1",
                    report_id="report-1",
                    invoice_id=invoice.invoice_id,
                    document_id=artifact.document_id,
                    linked_at=datetime.now(timezone.utc),
                    linked_by="debtor@example.com",
                )
            )

            self.assertEqual(store.reported_payment_by_id("report-1").payment_reference, "PAY-REF-1")
            self.assertEqual(store.reported_payment_by_id("report-1").settlement_offer_id, "offer-1")
            self.assertEqual(store.reported_payment_decisions_for_report("report-1")[0].status, ReportedPaymentStatus.NEEDS_EVIDENCE)
            self.assertEqual(store.reported_payment_evidence_links_for_report("report-1")[0].document_id, artifact.document_id)

            conn = sqlite3.connect(db_path)
            try:
                for table in (
                    "reported_payments",
                    "reported_payment_decisions",
                    "reported_payment_evidence_links",
                ):
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(f"UPDATE {table} SET invoice_id = 'altered'")
                    conn.rollback()
                    with self.assertRaises(sqlite3.DatabaseError):
                        conn.execute(f"DELETE FROM {table}")
                    conn.rollback()
            finally:
                conn.close()

    def test_settlement_finalization_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator-settlement-finalization.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-settlement-finalization",
                currency="GBP",
                principal_amount=Decimal("1000"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_settlement_offer(
                SettlementOffer(
                    offer_id="offer-1",
                    invoice_id=invoice.invoice_id,
                    offered_at=datetime.now(timezone.utc),
                    offered_by="USER-1",
                    offered_amount_gbp=Decimal("750.00"),
                    expiry_date=date(2026, 9, 1),
                    notes="Full and final",
                )
            )
            store.append_settlement_offer_finalization(
                SettlementOfferFinalization(
                    finalization_id="finalization-1",
                    offer_id="offer-1",
                    invoice_id=invoice.invoice_id,
                    finalized_at=datetime.now(timezone.utc),
                    finalized_by="USER-1",
                    triggering_report_id=None,
                    confirmed_payment_total_gbp=Decimal("750.00"),
                    outstanding_before_gbp=Decimal("250.00"),
                    settlement_discount_applied_gbp=Decimal("250.00"),
                )
            )

            self.assertEqual(
                store.settlement_offer_finalization_by_offer_id("offer-1").settlement_discount_applied_gbp,
                Decimal("250.00"),
            )

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE settlement_offer_finalizations SET finalized_by = 'USER-X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM settlement_offer_finalizations")
                conn.rollback()
            finally:
                conn.close()

    def test_init_schema_upgrades_legacy_resolution_tables(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "legacy-resolution.db")
            conn = sqlite3.connect(db_path)
            try:
                conn.execute(
                    """
                    CREATE TABLE reported_payments (
                        report_id TEXT PRIMARY KEY,
                        invoice_id TEXT NOT NULL,
                        case_id TEXT NOT NULL,
                        debtor_identifier TEXT NOT NULL,
                        reported_at TEXT NOT NULL,
                        amount_gbp TEXT NOT NULL,
                        payment_reference TEXT NOT NULL DEFAULT '',
                        payment_date TEXT,
                        details TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE payment_plan_agreements (
                        plan_id TEXT PRIMARY KEY,
                        invoice_id TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        proposed_by TEXT NOT NULL,
                        installment_amount_gbp TEXT NOT NULL,
                        installment_count INTEGER NOT NULL,
                        first_due_date TEXT NOT NULL,
                        frequency_days INTEGER NOT NULL,
                        notes TEXT NOT NULL DEFAULT ''
                    )
                    """
                )
                conn.execute(
                    """
                    CREATE TABLE payment_plan_payments (
                        payment_id TEXT PRIMARY KEY,
                        plan_id TEXT NOT NULL,
                        installment_id TEXT NOT NULL,
                        invoice_id TEXT NOT NULL,
                        paid_at TEXT NOT NULL,
                        amount_gbp TEXT NOT NULL,
                        recorded_by TEXT NOT NULL
                    )
                    """
                )
                conn.execute(
                    """
                    INSERT INTO reported_payments (
                        report_id, invoice_id, case_id, debtor_identifier, reported_at, amount_gbp, payment_reference, payment_date, details
                    ) VALUES ('legacy-report', 'inv-legacy', 'FCD-R-LEGACY', 'legacy@example.com', '2026-02-10T10:00:00+00:00', '100.00', 'LEG-1', '2026-02-10', 'legacy row')
                    """
                )
                conn.commit()
            finally:
                conn.close()

            store = SQLiteStore(db_path)
            upgraded_report = store.reported_payment_by_id("legacy-report")
            self.assertIsNotNone(upgraded_report)
            self.assertIsNone(upgraded_report.settlement_offer_id)

            conn = sqlite3.connect(db_path)
            try:
                reported_columns = {row[1] for row in conn.execute("PRAGMA table_info(reported_payments)").fetchall()}
                plan_columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_plan_agreements)").fetchall()}
                payment_columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_plan_payments)").fetchall()}
                tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall()}
            finally:
                conn.close()

            self.assertIn("settlement_offer_id", reported_columns)
            self.assertIn("plan_id", reported_columns)
            self.assertIn("installment_id", reported_columns)
            self.assertIn("proposer_role", plan_columns)
            self.assertIn("parent_plan_id", plan_columns)
            self.assertIn("version_number", plan_columns)
            self.assertIn("reported_payment_id", payment_columns)
            self.assertIn("settlement_offer_finalizations", tables)

    def test_payment_plan_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-7",
                currency="GBP",
                principal_amount=Decimal("900"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_payment_plan_agreement(
                PaymentPlanAgreement(
                    plan_id="plan-1",
                    invoice_id=invoice.invoice_id,
                    created_at=datetime.now(timezone.utc),
                    proposed_by="USER-1",
                    installment_amount_gbp=Decimal("100"),
                    installment_count=3,
                    first_due_date=date(2026, 2, 10),
                    frequency_days=30,
                )
            )
            store.append_payment_plan_decision(
                PaymentPlanDecision(
                    decision_id="plan-decision-1",
                    plan_id="plan-1",
                    invoice_id=invoice.invoice_id,
                    decided_at=datetime.now(timezone.utc),
                    decided_by="USER-2",
                    actor_role="DEBTOR",
                    status=PaymentPlanDecisionStatus.ACCEPTED,
                )
            )
            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE payment_plan_agreements SET proposed_by = 'USER-X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM payment_plan_agreements")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE payment_plan_decisions SET actor_role = 'SYSTEM'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM payment_plan_decisions")
                conn.rollback()
            finally:
                conn.close()

    def test_communication_delivery_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-8",
                currency="GBP",
                principal_amount=Decimal("300"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            record = CommunicationRecord(
                communication_id="comm-1",
                invoice_id=invoice.invoice_id,
                channel="EMAIL",
                recipient="debtor@example.com",
                subject="Reminder",
                body_summary="Summary",
                automated=True,
                created_at=datetime.now(timezone.utc),
            )
            store.append_communication(record)
            store.append_communication_delivery_event(
                CommunicationDeliveryEvent(
                    event_id="comm-evt-1",
                    communication_id=record.communication_id,
                    invoice_id=invoice.invoice_id,
                    state=CommunicationDeliveryState.CREATED,
                    timestamp=datetime.now(timezone.utc),
                    note="created",
                )
            )
            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE communications SET recipient = 'new@example.com'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM communications")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE communication_delivery_events SET state = 'SENT'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM communication_delivery_events")
                conn.rollback()
            finally:
                conn.close()

    def test_settlement_bank_details_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-9",
                currency="GBP",
                principal_amount=Decimal("700"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_settlement_bank_detail_record(
                SettlementBankDetailRecord(
                    record_id="bank-1",
                    invoice_id=invoice.invoice_id,
                    created_at=datetime.now(timezone.utc),
                    updated_by="USER-1",
                    account_holder_name="Creditor Ltd",
                    sort_code="12-34-56",
                    account_number_last4="6789",
                    iban_last4=None,
                    cop_state=BankDetailVerificationState.COP_EXACT_MATCH,
                    cop_result=ConfirmationOfPayeeResult.EXACT_MATCH,
                    expected_payee_name="Creditor Ltd",
                    dual_control_approved_by="ADMIN-1",
                    mfa_reauthenticated=False,
                )
            )
            self.assertIsNotNone(store.latest_settlement_bank_detail_for_invoice(invoice.invoice_id))

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE settlement_bank_detail_records SET updated_by = 'USER-X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM settlement_bank_detail_records")
                conn.rollback()
            finally:
                conn.close()

    def test_dual_ledger_tables_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            event_ledger = SQLiteInvoiceLedger(store)
            dual = DualLedgerEngine(store=store, event_ledger=event_ledger)
            invoice = Invoice(
                invoice_id="inv-db-3",
                currency="GBP",
                principal_amount=Decimal("2000"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            dual.add_client_action_fee(
                case_id="CASE-3",
                client_id="CLI-3",
                invoice_id=invoice.invoice_id,
                action_selected=ClientFeeAction.FORMAL_ESCALATION,
                accepted_by_user="Tester",
            )

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE client_fee_entries SET fee_amount_gbp = '99.99'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM client_fee_entries")
                conn.rollback()
            finally:
                conn.close()

    def test_pre_overdue_hygiene_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-4",
                currency="GBP",
                principal_amount=Decimal("1500"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_pre_overdue_hygiene_record(
                PreOverdueHygieneRecord(
                    record_id="hyg-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    creditor_legal_entity_name="First Cairn Digital Ltd",
                    creditor_companies_house_number="SC123456",
                    creditor_vat_number="GB123456789",
                    creditor_trading_address="1 Example Street",
                    debtor_legal_entity_name="Buyer Ltd",
                    debtor_companies_house_number="NI654321",
                    debtor_vat_number="GB987654321",
                    debtor_trading_address="2 Example Road",
                    po_required=True,
                    po_reference="PO-1",
                    payment_terms_days=30,
                    contractual_interest_clause_present=True,
                    contractual_recovery_clause_present=True,
                    proof_of_delivery_required=True,
                    suggested_clause_text="Clause",
                    suggested_clause_requires_legal_review=True,
                    checklist_complete=True,
                    missing_items=(),
                    warning_tier="MEDIUM",
                    format_warnings=("Creditor VAT number format is non-standard.",),
                    notes="ok",
                )
            )
            records = store.pre_overdue_hygiene_records_for_invoice(invoice.invoice_id)
            self.assertEqual(len(records), 1)
            self.assertEqual(records[0].warning_tier, "MEDIUM")
            self.assertEqual(records[0].format_warnings, ("Creditor VAT number format is non-standard.",))

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE pre_overdue_hygiene_records SET notes = 'changed'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM pre_overdue_hygiene_records")
                conn.rollback()
            finally:
                conn.close()

    def test_compliance_ledger_table_is_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-5",
                currency="GBP",
                principal_amount=Decimal("900"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            store.append_compliance_entry(
                ComplianceLedgerEntry(
                    entry_id="cmp-1",
                    invoice_id=invoice.invoice_id,
                    timestamp=datetime.now(timezone.utc),
                    event_type="LEGAL_SAFETY_GATE_ACCEPTED",
                    details={"user_id": "USER-1"},
                )
            )
            entries = store.compliance_entries_for_invoice(invoice.invoice_id)
            self.assertEqual(len(entries), 1)
            self.assertEqual(entries[0].event_type, "LEGAL_SAFETY_GATE_ACCEPTED")

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE compliance_ledger_entries SET event_type = 'X'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM compliance_ledger_entries")
                conn.rollback()
            finally:
                conn.close()

    def test_company_status_checks_and_restricted_notes_are_append_only(self) -> None:
        with TemporaryDirectory() as tmp_dir:
            db_path = str(Path(tmp_dir) / "escalator-sensitive.db")
            store = SQLiteStore(db_path)
            invoice = Invoice(
                invoice_id="inv-db-sensitive",
                currency="GBP",
                principal_amount=Decimal("900"),
                issue_date=date(2026, 1, 1),
                due_date=date(2026, 1, 31),
                jurisdiction=Jurisdiction.ENGLAND_WALES,
                debtor_type=DebtorType.LIMITED,
            )
            store.create_invoice(invoice)
            checked_at = datetime.now(timezone.utc)
            store.append_company_status_check(
                CompanyStatusCheck(
                    check_id="status-1",
                    invoice_id=invoice.invoice_id,
                    checked_at=checked_at,
                    checked_by="USER-1",
                    company_status="INSOLVENT",
                    source="COMPANIES_HOUSE",
                    evidence_summary="Insolvency status confirmed.",
                    company_number="12345678",
                    restrictions_recommended=("INSOLVENCY_REVIEW",),
                )
            )
            store.append_restricted_case_note(
                RestrictedCaseNote(
                    note_id="note-1",
                    invoice_id=invoice.invoice_id,
                    created_at=checked_at,
                    created_by="USER-1",
                    note_category="VULNERABILITY_NOTICE",
                    summary="Summary only",
                    sensitive_details="Sensitive welfare detail",
                    related_event_type="HUMANE_PAUSE_OPENED",
                )
            )

            latest_check = store.latest_company_status_check_for_invoice(invoice.invoice_id)
            self.assertIsNotNone(latest_check)
            self.assertEqual(latest_check.company_status, "INSOLVENT")
            self.assertEqual(len(store.restricted_case_notes_for_invoice(invoice.invoice_id)), 1)

            conn = sqlite3.connect(db_path)
            try:
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("UPDATE company_status_checks SET company_status = 'ACTIVE'")
                conn.rollback()
                with self.assertRaises(sqlite3.DatabaseError):
                    conn.execute("DELETE FROM restricted_case_notes")
                conn.rollback()
            finally:
                conn.close()


if __name__ == "__main__":
    unittest.main()
