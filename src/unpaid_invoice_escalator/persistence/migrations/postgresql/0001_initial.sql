CREATE TABLE IF NOT EXISTS invoices (
    invoice_id TEXT PRIMARY KEY,
    currency TEXT NOT NULL,
    principal_amount NUMERIC(18, 4) NOT NULL,
    issue_date DATE NOT NULL,
    due_date DATE NOT NULL,
    jurisdiction TEXT NOT NULL,
    debtor_type TEXT NOT NULL,
    client_id TEXT NOT NULL DEFAULT 'DEFAULT_CLIENT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS evidence_artifacts (
    document_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    artifact_type TEXT NOT NULL DEFAULT 'OTHER',
    file_hash TEXT NOT NULL,
    file_path TEXT NOT NULL,
    upload_timestamp TIMESTAMPTZ NOT NULL,
    user_id TEXT NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS ledger_events (
    event_seq BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    data_payload JSONB NOT NULL DEFAULT '{}'::jsonb,
    previous_hash TEXT NOT NULL,
    hash TEXT NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS debtor_ledger_entries (
    entry_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    entry_type TEXT NOT NULL,
    amount_gbp NUMERIC(18, 4) NOT NULL,
    description TEXT NOT NULL,
    recovery_cost_category TEXT,
    linked_client_fee_entry_id TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS client_fee_entries (
    entry_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    client_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    pricing_schedule_version TEXT NOT NULL,
    action_selected TEXT NOT NULL,
    fee_amount_gbp NUMERIC(18, 4) NOT NULL,
    vat_gbp NUMERIC(18, 4) NOT NULL,
    accepted_by_user TEXT NOT NULL,
    external_fee BOOLEAN NOT NULL DEFAULT FALSE,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS pre_overdue_hygiene_records (
    record_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    creditor_legal_entity_name TEXT NOT NULL,
    creditor_companies_house_number TEXT NOT NULL,
    creditor_vat_number TEXT NOT NULL,
    creditor_trading_address TEXT NOT NULL,
    debtor_legal_entity_name TEXT NOT NULL,
    debtor_companies_house_number TEXT NOT NULL DEFAULT '',
    debtor_vat_number TEXT NOT NULL DEFAULT '',
    debtor_trading_address TEXT NOT NULL,
    po_required BOOLEAN NOT NULL,
    po_reference TEXT,
    payment_terms_days INTEGER NOT NULL,
    contractual_interest_clause_present BOOLEAN NOT NULL,
    contractual_recovery_clause_present BOOLEAN NOT NULL,
    proof_of_delivery_required BOOLEAN NOT NULL,
    suggested_clause_text TEXT,
    suggested_clause_requires_legal_review BOOLEAN NOT NULL,
    checklist_complete BOOLEAN NOT NULL,
    missing_items_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    warning_tier TEXT NOT NULL DEFAULT 'NONE',
    format_warnings_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS compliance_ledger_entries (
    entry_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS audit_trail_entries (
    entry_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    category TEXT NOT NULL,
    action TEXT NOT NULL,
    actor TEXT NOT NULL,
    details_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS debtor_verification_cases (
    case_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL UNIQUE,
    creditor_name TEXT NOT NULL,
    invoice_reference TEXT NOT NULL,
    verification_code_hash TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS communications (
    communication_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    recipient TEXT NOT NULL,
    subject TEXT NOT NULL,
    body_summary TEXT NOT NULL,
    automated BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS reported_payments (
    report_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    case_id TEXT NOT NULL,
    debtor_identifier TEXT NOT NULL,
    reported_at TIMESTAMPTZ NOT NULL,
    amount_gbp NUMERIC(18, 4) NOT NULL,
    payment_reference TEXT NOT NULL DEFAULT '',
    payment_date DATE,
    details TEXT NOT NULL DEFAULT '',
    plan_id TEXT,
    installment_id TEXT,
    settlement_offer_id TEXT,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS reported_payment_decisions (
    decision_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    decided_by TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT NOT NULL DEFAULT '',
    notes TEXT NOT NULL DEFAULT '',
    confirmed_amount_gbp NUMERIC(18, 4),
    linked_debtor_entry_id TEXT,
    FOREIGN KEY (report_id) REFERENCES reported_payments(report_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS reported_payment_evidence_links (
    link_id TEXT PRIMARY KEY,
    report_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    linked_at TIMESTAMPTZ NOT NULL,
    linked_by TEXT NOT NULL,
    FOREIGN KEY (report_id) REFERENCES reported_payments(report_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY (document_id) REFERENCES evidence_artifacts(document_id)
);

CREATE TABLE IF NOT EXISTS communication_delivery_events (
    event_id TEXT PRIMARY KEY,
    communication_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    state TEXT NOT NULL,
    timestamp TIMESTAMPTZ NOT NULL,
    note TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (communication_id) REFERENCES communications(communication_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS payment_plan_agreements (
    plan_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    proposed_by TEXT NOT NULL,
    installment_amount_gbp NUMERIC(18, 4) NOT NULL,
    installment_count INTEGER NOT NULL,
    first_due_date DATE NOT NULL,
    frequency_days INTEGER NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    proposer_role TEXT NOT NULL DEFAULT 'CREDITOR',
    parent_plan_id TEXT,
    version_number INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS payment_plan_installments (
    installment_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    due_date DATE NOT NULL,
    amount_gbp NUMERIC(18, 4) NOT NULL,
    sequence_number INTEGER NOT NULL,
    FOREIGN KEY (plan_id) REFERENCES payment_plan_agreements(plan_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS payment_plan_payments (
    payment_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    installment_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    paid_at TIMESTAMPTZ NOT NULL,
    amount_gbp NUMERIC(18, 4) NOT NULL,
    recorded_by TEXT NOT NULL,
    reported_payment_id TEXT,
    FOREIGN KEY (plan_id) REFERENCES payment_plan_agreements(plan_id),
    FOREIGN KEY (installment_id) REFERENCES payment_plan_installments(installment_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS payment_plan_decisions (
    decision_id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    decided_by TEXT NOT NULL,
    actor_role TEXT NOT NULL,
    status TEXT NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (plan_id) REFERENCES payment_plan_agreements(plan_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS settlement_offers (
    offer_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    offered_at TIMESTAMPTZ NOT NULL,
    offered_by TEXT NOT NULL,
    offered_amount_gbp NUMERIC(18, 4) NOT NULL,
    expiry_date DATE NOT NULL,
    notes TEXT NOT NULL DEFAULT '',
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS settlement_acceptances (
    acceptance_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    accepted_at TIMESTAMPTZ NOT NULL,
    accepted_by TEXT NOT NULL,
    accepter_role TEXT NOT NULL,
    FOREIGN KEY (offer_id) REFERENCES settlement_offers(offer_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS settlement_offer_finalizations (
    finalization_id TEXT PRIMARY KEY,
    offer_id TEXT NOT NULL,
    invoice_id TEXT NOT NULL,
    finalized_at TIMESTAMPTZ NOT NULL,
    finalized_by TEXT NOT NULL,
    triggering_report_id TEXT,
    confirmed_payment_total_gbp NUMERIC(18, 4) NOT NULL,
    outstanding_before_gbp NUMERIC(18, 4) NOT NULL,
    settlement_discount_applied_gbp NUMERIC(18, 4) NOT NULL,
    FOREIGN KEY (offer_id) REFERENCES settlement_offers(offer_id),
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id),
    FOREIGN KEY (triggering_report_id) REFERENCES reported_payments(report_id)
);

CREATE TABLE IF NOT EXISTS dispute_carve_outs (
    carve_out_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    disputed_amount_gbp NUMERIC(18, 4) NOT NULL,
    undisputed_amount_gbp NUMERIC(18, 4) NOT NULL,
    reason TEXT NOT NULL,
    created_by TEXT NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS settlement_bank_detail_records (
    record_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    updated_by TEXT NOT NULL,
    account_holder_name TEXT NOT NULL,
    sort_code TEXT NOT NULL,
    account_number_last4 TEXT NOT NULL,
    iban_last4 TEXT,
    cop_state TEXT NOT NULL,
    cop_result TEXT,
    expected_payee_name TEXT,
    dual_control_approved_by TEXT,
    mfa_reauthenticated BOOLEAN NOT NULL,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS company_status_checks (
    check_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    checked_by TEXT NOT NULL,
    company_status TEXT NOT NULL,
    source TEXT NOT NULL,
    evidence_summary TEXT NOT NULL,
    company_number TEXT,
    official_register_url TEXT,
    review_due_date DATE,
    notes TEXT NOT NULL DEFAULT '',
    restrictions_recommended_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE TABLE IF NOT EXISTS restricted_case_notes (
    note_id TEXT PRIMARY KEY,
    invoice_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL,
    created_by TEXT NOT NULL,
    note_category TEXT NOT NULL,
    summary TEXT NOT NULL,
    sensitive_details TEXT NOT NULL,
    related_event_type TEXT,
    access_scope TEXT NOT NULL DEFAULT 'RESTRICTED',
    FOREIGN KEY (invoice_id) REFERENCES invoices(invoice_id)
);

CREATE OR REPLACE FUNCTION prevent_append_only_update_delete() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'append-only protection: updates and deletes are forbidden on %', TG_TABLE_NAME;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE
    table_name TEXT;
BEGIN
    FOR table_name IN SELECT unnest(ARRAY[
        'invoices',
        'ledger_events',
        'evidence_artifacts',
        'debtor_ledger_entries',
        'client_fee_entries',
        'pre_overdue_hygiene_records',
        'compliance_ledger_entries',
        'audit_trail_entries',
        'debtor_verification_cases',
        'communications',
        'communication_delivery_events',
        'reported_payments',
        'reported_payment_decisions',
        'reported_payment_evidence_links',
        'payment_plan_agreements',
        'payment_plan_installments',
        'payment_plan_payments',
        'payment_plan_decisions',
        'settlement_offers',
        'settlement_acceptances',
        'settlement_offer_finalizations',
        'dispute_carve_outs',
        'settlement_bank_detail_records',
        'company_status_checks',
        'restricted_case_notes'
    ])
    LOOP
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', table_name || '_append_only_guard_update', table_name);
        EXECUTE format('DROP TRIGGER IF EXISTS %I ON %I', table_name || '_append_only_guard_delete', table_name);
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete()', table_name || '_append_only_guard_update', table_name);
        EXECUTE format('CREATE TRIGGER %I BEFORE UPDATE OR DELETE ON %I FOR EACH ROW EXECUTE FUNCTION prevent_append_only_update_delete()', table_name || '_append_only_guard_delete', table_name);
    END LOOP;
END $$;

CREATE INDEX IF NOT EXISTS idx_ledger_events_invoice_time ON ledger_events(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_debtor_ledger_invoice_time ON debtor_ledger_entries(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_client_fee_invoice_time ON client_fee_entries(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_hygiene_records_invoice_time ON pre_overdue_hygiene_records(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_compliance_ledger_invoice_time ON compliance_ledger_entries(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_trail_invoice_time ON audit_trail_entries(invoice_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_artifacts_invoice ON evidence_artifacts(invoice_id);
CREATE INDEX IF NOT EXISTS idx_verification_cases_invoice ON debtor_verification_cases(invoice_id);
CREATE INDEX IF NOT EXISTS idx_communications_invoice_time ON communications(invoice_id, created_at);
CREATE INDEX IF NOT EXISTS idx_reported_payments_invoice_time ON reported_payments(invoice_id, reported_at);
CREATE INDEX IF NOT EXISTS idx_reported_payment_decisions_report_time ON reported_payment_decisions(report_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_reported_payment_evidence_links_report_time ON reported_payment_evidence_links(report_id, linked_at);
CREATE INDEX IF NOT EXISTS idx_bank_details_invoice_time ON settlement_bank_detail_records(invoice_id, created_at);
CREATE INDEX IF NOT EXISTS idx_company_status_checks_invoice_time ON company_status_checks(invoice_id, checked_at);
CREATE INDEX IF NOT EXISTS idx_restricted_case_notes_invoice_time ON restricted_case_notes(invoice_id, created_at);
CREATE INDEX IF NOT EXISTS idx_comm_delivery_events_comm_time ON communication_delivery_events(communication_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_payment_plans_invoice ON payment_plan_agreements(invoice_id, created_at);
CREATE INDEX IF NOT EXISTS idx_payment_plans_parent ON payment_plan_agreements(parent_plan_id, created_at);
CREATE INDEX IF NOT EXISTS idx_payment_installments_plan ON payment_plan_installments(plan_id, sequence_number);
CREATE INDEX IF NOT EXISTS idx_payment_plan_payments_installment ON payment_plan_payments(installment_id, paid_at);
CREATE INDEX IF NOT EXISTS idx_payment_plan_decisions_plan ON payment_plan_decisions(plan_id, decided_at);
CREATE INDEX IF NOT EXISTS idx_settlement_offers_invoice ON settlement_offers(invoice_id, offered_at);
CREATE INDEX IF NOT EXISTS idx_settlement_acceptances_offer ON settlement_acceptances(offer_id, accepted_at);
CREATE INDEX IF NOT EXISTS idx_settlement_offer_finalizations_offer ON settlement_offer_finalizations(offer_id, finalized_at);
CREATE INDEX IF NOT EXISTS idx_dispute_carve_outs_invoice ON dispute_carve_outs(invoice_id, created_at);
