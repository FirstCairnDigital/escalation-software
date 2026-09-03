import os
import unittest
from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import uuid4

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
    DebtorType,
    DisputeCarveOut,
    EvidenceArtifact,
    Invoice,
    Jurisdiction,
    PaymentPlanAgreement,
    PaymentPlanDecision,
    PaymentPlanDecisionStatus,
    PaymentPlanInstallment,
    PaymentPlanPayment,
    PreOverdueHygieneRecord,
    ReportedPayment,
    ReportedPaymentDecision,
    ReportedPaymentEvidenceLink,
    ReportedPaymentStatus,
    RestrictedCaseNote,
    SettlementAcceptance,
    SettlementBankDetailRecord,
    SettlementOffer,
    SettlementOfferFinalization,
)
from unpaid_invoice_escalator.persistence.postgresql_store import PostgreSQLStore
from unpaid_invoice_escalator.tenant_context import reset_request_context, set_request_context


class PostgreSQLStoreBehaviourTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.database_url = os.getenv("POSTGRES_TEST_DATABASE_URL") or os.getenv("DATABASE_URL")
        if not cls.database_url:
            raise unittest.SkipTest("PostgreSQL integration tests require a test DATABASE_URL.")

    def setUp(self) -> None:
        self.store = PostgreSQLStore(self.database_url)
        self.store.run_migrations()
        self.tokens = set_request_context(client_id="CLIENT-A", role="user", identity="tester")

    def tearDown(self) -> None:
        reset_request_context(self.tokens)

    def _invoice(self, *, client_id: str, invoice_id: str | None = None) -> Invoice:
        current = invoice_id or f"INV-{uuid4().hex[:12]}"
        return Invoice(
            invoice_id=current,
            currency="GBP",
            principal_amount=Decimal("1542.78"),
            issue_date=date(2026, 1, 1),
            due_date=date(2026, 1, 31),
            jurisdiction=Jurisdiction.ENGLAND_WALES,
            debtor_type=DebtorType.LIMITED,
            client_id=client_id,
        )

    def _create_invoice(self, *, client_id: str, invoice_id: str | None = None) -> Invoice:
        invoice = self._invoice(client_id=client_id, invoice_id=invoice_id)
        self.store.create_invoice(invoice)
        return invoice

    def test_invoice_list_get_and_tenant_isolation(self) -> None:
        invoice_a = self._create_invoice(client_id="CLIENT-A")
        invoice_b = self._create_invoice(client_id="CLIENT-B")

        self.assertEqual(self.store.get_invoice(invoice_a.invoice_id).invoice_id, invoice_a.invoice_id)
        self.assertIsNone(self.store.get_invoice(invoice_b.invoice_id))

        listed = self.store.list_invoices()
        self.assertEqual([item["invoice_id"] for item in listed], [invoice_a.invoice_id])

        admin_tokens = set_request_context(client_id="CLIENT-B", role="admin", identity="admin")
        try:
            self.assertEqual(self.store.get_invoice(invoice_b.invoice_id).invoice_id, invoice_b.invoice_id)
            self.assertIn(invoice_b.invoice_id, {item["invoice_id"] for item in self.store.list_invoices()})
        finally:
            reset_request_context(admin_tokens)

    def test_evidence_and_ledger_round_trip(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        artifact = EvidenceArtifact(
            document_id=f"DOC-{uuid4().hex[:12]}",
            invoice_id=invoice.invoice_id,
            artifact_type=ArtifactType.INVOICE,
            file_hash="abc123",
            file_path="/tmp/invoice.pdf",
            upload_timestamp=datetime.now(timezone.utc),
            user_id="user-1",
        )
        self.store.save_evidence_artifact(artifact)

        event = self.store.events_for_invoice(invoice.invoice_id)
        self.assertEqual(event, ())

        from unpaid_invoice_escalator.models import LedgerEvent

        ledger_event = LedgerEvent(
            event_id=f"EVT-{uuid4().hex[:12]}",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            actor=Actor.SYSTEM,
            event_type="STATE_TRANSITION",
            data_payload={"to_state": "ISSUED"},
        )
        self.store.append_ledger_event(ledger_event)
        loaded_events = self.store.events_for_invoice(invoice.invoice_id)
        self.assertEqual(len(loaded_events), 1)
        self.assertTrue(self.store.verify_chain(invoice.invoice_id))
        self.assertEqual(self.store.infer_state(invoice.invoice_id), invoice.jurisdiction.__class__ if False else __import__("unpaid_invoice_escalator.models", fromlist=["InvoiceState"]).InvoiceState.ISSUED)
        self.assertEqual(self.store.artifacts_for_invoice(invoice.invoice_id)[0].document_id, artifact.document_id)

    def test_debtor_and_client_fee_ledgers_preserve_decimal_bool_values(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        debtor_entry = DebtorLedgerEntry(
            entry_id=f"DEBT-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            entry_type=DebtorLedgerEntryType.PAYMENT_RECEIVED,
            amount_gbp=Decimal("100.45"),
            description="partial payment",
        )
        self.store.append_debtor_ledger_entry(debtor_entry)

        fee_entry = ClientFeeEntry(
            entry_id=f"FEE-{uuid4().hex[:8]}",
            case_id=f"CASE-{uuid4().hex[:8]}",
            client_id="CLIENT-A",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            pricing_schedule_version="v1",
            action_selected=ClientFeeAction.FORMAL_ESCALATION,
            fee_amount_gbp=Decimal("50.25"),
            vat_gbp=Decimal("10.05"),
            accepted_by_user="tester",
            external_fee=True,
        )
        self.store.append_client_fee_entry(fee_entry)

        debtor_rows = self.store.debtor_ledger_entries_for_invoice(invoice.invoice_id)
        self.assertEqual(debtor_rows[0].amount_gbp, Decimal("100.45"))
        self.assertEqual(self.store.debtor_ledger_balance_for_invoice(invoice.invoice_id), Decimal("1642.23"))
        self.assertEqual(self.store.client_fee_balance_for_invoice(invoice.invoice_id), Decimal("60.30"))
        self.assertIsInstance(debtor_rows[0].amount_gbp, Decimal)
        self.assertIsInstance(self.store.client_fee_entries_for_invoice(invoice.invoice_id)[0].external_fee, bool)

    def test_hygiene_compliance_audit_verification_round_trip(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        hygiene = PreOverdueHygieneRecord(
            record_id=f"HYG-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            creditor_legal_entity_name="Creditor Ltd",
            creditor_companies_house_number="12345678",
            creditor_vat_number="GB123",
            creditor_trading_address="1 Main St",
            debtor_legal_entity_name="Debtor Ltd",
            debtor_companies_house_number="87654321",
            debtor_vat_number="GB456",
            debtor_trading_address="2 Debtor St",
            po_required=True,
            po_reference="PO-001",
            payment_terms_days=30,
            contractual_interest_clause_present=True,
            contractual_recovery_clause_present=False,
            proof_of_delivery_required=True,
            suggested_clause_text="example clause",
            suggested_clause_requires_legal_review=False,
            checklist_complete=True,
            missing_items=("po", "delivery"),
            warning_tier="MEDIUM",
            format_warnings=("missing VAT",),
            notes="test note",
        )
        self.store.append_pre_overdue_hygiene_record(hygiene)

        compliance = ComplianceLedgerEntry(
            entry_id=f"COMP-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            event_type="RECOVERY_RESTRICTED",
            details={"flag": True, "reason": "accuracy challenge"},
        )
        self.store.append_compliance_entry(compliance)

        audit = AuditTrailEntry(
            entry_id=f"AUD-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            timestamp=datetime.now(timezone.utc),
            category="SYSTEM",
            action="CHECK",
            actor="system",
            details={"status": "ok"},
        )
        self.store.append_audit_trail_entry(audit)

        verification = DebtorVerificationCase(
            case_id=f"CASE-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            creditor_name="Creditor Ltd",
            invoice_reference=invoice.invoice_id,
            verification_code_hash="hash-abc",
            created_at=datetime.now(timezone.utc),
        )
        self.store.append_debtor_verification_case(verification)

        self.assertEqual(self.store.pre_overdue_hygiene_records_for_invoice(invoice.invoice_id)[0].po_required, True)
        self.assertEqual(self.store.compliance_entries_for_invoice(invoice.invoice_id)[0].details["flag"], True)
        self.assertEqual(self.store.audit_trail_entries_for_invoice(invoice.invoice_id)[0].category, "SYSTEM")
        self.assertEqual(self.store.debtor_verification_case_for_invoice(invoice.invoice_id).case_id, verification.case_id)

    def test_communications_reported_payments_and_decisions(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        communication = CommunicationRecord(
            communication_id=f"COMM-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            channel="EMAIL",
            recipient="debtor@example.com",
            subject="Balance reminder",
            body_summary="Your invoice is outstanding",
            automated=True,
            created_at=datetime.now(timezone.utc),
        )
        self.store.append_communication(communication)
        delivery = CommunicationDeliveryEvent(
            event_id=f"DEL-{uuid4().hex[:8]}",
            communication_id=communication.communication_id,
            invoice_id=invoice.invoice_id,
            state=CommunicationDeliveryState.SENT,
            timestamp=datetime.now(timezone.utc),
            note="queued",
        )
        self.store.append_communication_delivery_event(delivery)

        report = ReportedPayment(
            report_id=f"RPT-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            case_id=f"CASE-{uuid4().hex[:8]}",
            debtor_identifier="debtor-123",
            reported_at=datetime.now(timezone.utc),
            amount_gbp=Decimal("250.00"),
            payment_reference="REF-1",
            payment_date=date(2026, 2, 1),
            details="cash",
        )
        self.store.append_reported_payment(report)
        decision = ReportedPaymentDecision(
            decision_id=f"DEC-{uuid4().hex[:8]}",
            report_id=report.report_id,
            invoice_id=invoice.invoice_id,
            decided_at=datetime.now(timezone.utc),
            decided_by="creditor",
            status=ReportedPaymentStatus.PAYMENT_CONFIRMED_BY_CREDITOR,
            reason="matched",
            confirmed_amount_gbp=Decimal("250.00"),
        )
        self.store.append_reported_payment_decision(decision)
        evidence_link = ReportedPaymentEvidenceLink(
            link_id=f"LINK-{uuid4().hex[:8]}",
            report_id=report.report_id,
            invoice_id=invoice.invoice_id,
            document_id=f"DOC-{uuid4().hex[:8]}",
            linked_at=datetime.now(timezone.utc),
            linked_by="tester",
        )
        self.store.append_reported_payment_evidence_link(evidence_link)

        self.assertEqual(self.store.communication_for_id(communication.communication_id).communication_id, communication.communication_id)
        self.assertEqual(self.store.communication_delivery_events_for_invoice(invoice.invoice_id)[0].state, CommunicationDeliveryState.SENT)
        self.assertEqual(self.store.reported_payment_by_id(report.report_id).amount_gbp, Decimal("250.00"))
        self.assertEqual(self.store.reported_payment_decisions_for_report(report.report_id)[0].status, ReportedPaymentStatus.PAYMENT_CONFIRMED_BY_CREDITOR)
        self.assertEqual(self.store.reported_payment_evidence_links_for_report(report.report_id)[0].document_id, evidence_link.document_id)

    def test_payment_plan_and_settlement_flow(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")

        agreement = PaymentPlanAgreement(
            plan_id=f"PLAN-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            created_at=datetime.now(timezone.utc),
            proposed_by="debtor",
            installment_amount_gbp=Decimal("200.00"),
            installment_count=3,
            first_due_date=date(2026, 3, 1),
            frequency_days=30,
            notes="monthly",
            proposer_role="DEBTOR",
        )
        self.store.append_payment_plan_agreement(agreement)
        installments = (
            PaymentPlanInstallment(
                installment_id=f"INST-{uuid4().hex[:8]}",
                plan_id=agreement.plan_id,
                invoice_id=invoice.invoice_id,
                due_date=date(2026, 3, 1),
                amount_gbp=Decimal("200.00"),
                sequence_number=1,
            ),
            PaymentPlanInstallment(
                installment_id=f"INST-{uuid4().hex[:8]}",
                plan_id=agreement.plan_id,
                invoice_id=invoice.invoice_id,
                due_date=date(2026, 4, 1),
                amount_gbp=Decimal("200.00"),
                sequence_number=2,
            ),
        )
        self.store.append_payment_plan_installments(installments)
        payment = PaymentPlanPayment(
            payment_id=f"PAY-{uuid4().hex[:8]}",
            plan_id=agreement.plan_id,
            installment_id=installments[0].installment_id,
            invoice_id=invoice.invoice_id,
            paid_at=datetime.now(timezone.utc),
            amount_gbp=Decimal("200.00"),
            recorded_by="tester",
        )
        self.store.append_payment_plan_payment(payment)
        decision = PaymentPlanDecision(
            decision_id=f"PDEC-{uuid4().hex[:8]}",
            plan_id=agreement.plan_id,
            invoice_id=invoice.invoice_id,
            decided_at=datetime.now(timezone.utc),
            decided_by="creditor",
            actor_role="CREDITOR",
            status=PaymentPlanDecisionStatus.ACCEPTED,
            notes="agreed",
        )
        self.store.append_payment_plan_decision(decision)

        offer = SettlementOffer(
            offer_id=f"OFF-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            offered_at=datetime.now(timezone.utc),
            offered_by="debtor",
            offered_amount_gbp=Decimal("1200.00"),
            expiry_date=date(2026, 3, 10),
            notes="full and final",
        )
        self.store.append_settlement_offer(offer)
        acceptance = SettlementAcceptance(
            acceptance_id=f"ACC-{uuid4().hex[:8]}",
            offer_id=offer.offer_id,
            invoice_id=invoice.invoice_id,
            accepted_at=datetime.now(timezone.utc),
            accepted_by="creditor",
            accepter_role="CREDITOR",
        )
        self.store.append_settlement_acceptance(acceptance)
        finalization = SettlementOfferFinalization(
            finalization_id=f"FIN-{uuid4().hex[:8]}",
            offer_id=offer.offer_id,
            invoice_id=invoice.invoice_id,
            finalized_at=datetime.now(timezone.utc),
            finalized_by="creditor",
            triggering_report_id=None,
            confirmed_payment_total_gbp=Decimal("1200.00"),
            outstanding_before_gbp=Decimal("1542.78"),
            settlement_discount_applied_gbp=Decimal("342.78"),
        )
        self.store.append_settlement_offer_finalization(finalization)

        self.assertEqual(self.store.payment_plan_agreement_by_id(agreement.plan_id).plan_id, agreement.plan_id)
        self.assertEqual(len(self.store.payment_plan_installments_for_plan(agreement.plan_id)), 2)
        self.assertEqual(self.store.payment_plan_payments_for_plan(agreement.plan_id)[0].amount_gbp, Decimal("200.00"))
        self.assertEqual(self.store.settlement_offer_by_id(offer.offer_id).offered_amount_gbp, Decimal("1200.00"))
        self.assertEqual(self.store.settlement_offer_finalization_by_offer_id(offer.offer_id).confirmed_payment_total_gbp, Decimal("1200.00"))

    def test_dispute_bank_company_status_and_restricted_notes(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        carve = DisputeCarveOut(
            carve_out_id=f"CARVE-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            created_at=datetime.now(timezone.utc),
            disputed_amount_gbp=Decimal("100.00"),
            undisputed_amount_gbp=Decimal("1442.78"),
            reason="partial dispute",
            created_by="system",
        )
        self.store.append_dispute_carve_out(carve)
        bank = SettlementBankDetailRecord(
            record_id=f"BANK-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            created_at=datetime.now(timezone.utc),
            updated_by="tester",
            account_holder_name="Creditor Ltd",
            sort_code="123456",
            account_number_last4="1234",
            iban_last4="5678",
            cop_state=BankDetailVerificationState.COP_EXACT_MATCH,
            cop_result=ConfirmationOfPayeeResult.EXACT_MATCH,
            expected_payee_name="Creditor Ltd",
            dual_control_approved_by="manager",
            mfa_reauthenticated=True,
        )
        self.store.append_settlement_bank_detail_record(bank)
        status = CompanyStatusCheck(
            check_id=f"STATUS-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            checked_at=datetime.now(timezone.utc),
            checked_by="system",
            company_status="ACTIVE",
            source="companies_house",
            evidence_summary="registered",
            company_number="SC123456",
            official_register_url="https://example.com",
            notes="ok",
            restrictions_recommended=("no restrictions",),
        )
        self.store.append_company_status_check(status)
        note = RestrictedCaseNote(
            note_id=f"NOTE-{uuid4().hex[:8]}",
            invoice_id=invoice.invoice_id,
            created_at=datetime.now(timezone.utc),
            created_by="system",
            note_category="VULNERABILITY",
            summary="limited disclosure",
            sensitive_details="sensitive",
            related_event_type="STATE_TRANSITION",
            access_scope="RESTRICTED",
        )
        self.store.append_restricted_case_note(note)

        self.assertEqual(self.store.dispute_carve_outs_for_invoice(invoice.invoice_id)[0].disputed_amount_gbp, Decimal("100.00"))
        self.assertEqual(self.store.latest_settlement_bank_detail_for_invoice(invoice.invoice_id).account_number_last4, "1234")
        self.assertEqual(self.store.latest_company_status_check_for_invoice(invoice.invoice_id).company_status, "ACTIVE")
        self.assertEqual(self.store.restricted_case_notes_for_invoice(invoice.invoice_id)[0].summary, "limited disclosure")

    def test_foreign_key_and_append_only_enforcement(self) -> None:
        invoice = self._create_invoice(client_id="CLIENT-A")
        with self.store.connection() as conn:
            with self.assertRaises(Exception):
                conn.execute(
                    "INSERT INTO communication_delivery_events (event_id, communication_id, invoice_id, state, timestamp, note) VALUES (%s, %s, %s, %s, %s, %s)",
                    (f"BAD-{uuid4().hex[:8]}", "missing-comm", invoice.invoice_id, "SENT", datetime.now(timezone.utc), "bad"),
                )

        with self.store.connection() as conn:
            conn.execute(
                "INSERT INTO communications (communication_id, invoice_id, channel, recipient, subject, body_summary, automated, created_at) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
                (f"COMM-{uuid4().hex[:8]}", invoice.invoice_id, "EMAIL", "a@example.com", "x", "y", True, datetime.now(timezone.utc)),
            )
            with self.assertRaises(Exception):
                conn.execute("UPDATE communications SET body_summary = %s WHERE communication_id = %s", ("changed", f"COMM-{uuid4().hex[:8]}"))


if __name__ == "__main__":
    unittest.main()
