param(
    [string]$BaseUrl = "http://127.0.0.1:8000",
    [string]$AdminApiKey = "admin-key",
    [string]$OpsApiKey = "ops-key",
    [string]$ReadOnlyApiKey = "ro-key",
    [string]$InvoiceId = "inv-go-live-001"
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$adminHeaders = @{ "x-api-key" = $AdminApiKey }
$opsHeaders = @{ "x-api-key" = $OpsApiKey }
$roHeaders = @{ "x-api-key" = $ReadOnlyApiKey }

function Invoke-JsonPost {
    param(
        [string]$Url,
        [hashtable]$Headers,
        [hashtable]$Body
    )
    return Invoke-RestMethod -Uri $Url -Method Post -Headers $Headers -ContentType "application/json" -Body ($Body | ConvertTo-Json -Depth 8)
}

Write-Host "== P26003 Go-Live Command Sheet =="
Write-Host "Base URL: $BaseUrl"

Write-Host "`n[1/8] Readiness checks"
Invoke-RestMethod "$BaseUrl/health" | Out-Host
Invoke-RestMethod "$BaseUrl/ready" | Out-Host
Invoke-RestMethod "$BaseUrl/deployment/startup-config-validation" -Headers $adminHeaders | Out-Host
Invoke-RestMethod "$BaseUrl/deployment/startup-config-validation/report" -Headers $adminHeaders | Out-Host
Invoke-RestMethod "$BaseUrl/metrics" -Headers $adminHeaders | Out-Host

Write-Host "`n[2/8] Create invoice baseline"
Invoke-JsonPost -Url "$BaseUrl/invoices" -Headers $opsHeaders -Body @{
    invoice_id = $InvoiceId
    currency = "GBP"
    principal_amount = "1200"
    issue_date = "2026-01-01"
    due_date = "2026-01-31"
    jurisdiction = "ENGLAND_WALES"
    debtor_type = "LIMITED"
} | Out-Host

Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/case-health-check" -Headers $opsHeaders -Body @{
    user_id = "USER-GO"
    correct_customer_legal_entity = $true
    description_of_goods_or_services = $true
    invoice_number_and_date_verified = $true
    amount_matches_contract_or_quote = $true
    correct_billing_address = $true
    vat_numbers_checked = $true
    purchase_order_supplied_if_required = $true
    payment_terms_and_due_date_established = $true
    delivery_or_acceptance_proof_attached = $true
    no_unresolved_credit_notes = $true
    direct_payments_checked = $true
    no_known_dispute = $true
    creditor_authority_verified = $true
    limitation_period_checked = $true
    debtor_contact_details_verified = $true
    court_handoff_boundary_acknowledged = $true
} | Out-Host

Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/discrepancy-check" -Headers $opsHeaders -Body @{
    claim_amount = "1200"
    evidence_document_amount = "1200"
    principal = "1200"
    payments_recorded = "0"
    outstanding_entered = "1200"
} | Out-Host

Write-Host "`n[3/8] Register verification case and portal access"
$verification = Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/debtor-verification/register" -Headers $opsHeaders -Body @{
    creditor_name = "Creditor Ltd"
    invoice_reference = "INV-GO-001"
}
$caseId = $verification.case_id
$code = $verification.verification_code
$verification | Out-Host
Invoke-RestMethod "$BaseUrl/verify?case=$caseId&code=$code" | Out-Host
Invoke-RestMethod "$BaseUrl/portal?case=$caseId&code=$code" | Out-Host

Write-Host "`n[4/8] Portal action smoke"
Invoke-JsonPost -Url "$BaseUrl/portal/actions/questions" -Headers @{} -Body @{
    case = $caseId
    code = $code
    debtor_identifier = "debtor-go"
    question = "Please confirm invoice scope."
} | Out-Host

Invoke-JsonPost -Url "$BaseUrl/portal/actions/confirm-payment-date" -Headers @{} -Body @{
    case = $caseId
    code = $code
    debtor_identifier = "debtor-go"
    promised_payment_date = "2026-03-15"
    notes = "Bank transfer pending."
} | Out-Host

Write-Host "`n[5/8] Escalation guard smoke"
try {
    Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/escalate" -Headers $opsHeaders -Body @{
        today = "2026-03-01"
        current_state = "OVERDUE_CHASER"
    } | Out-Host
} catch {
    Write-Host "Expected block before promised date: $($_.Exception.Message)"
}
Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/escalate" -Headers $opsHeaders -Body @{
    today = "2026-03-20"
    current_state = "OVERDUE_CHASER"
} | Out-Host

Write-Host "`n[6/8] Evidence and manifest smoke"
Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/evidence-bundles" -Headers $opsHeaders -Body @{
    communications = @("Go-live procedural communication")
    formal_notices = @("Go-live procedural notice")
    include_resolution_artifacts = $true
    output_filename = "go_live_bundle.pdf"
} | Out-Host

Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/ledger-manifests" -Headers $opsHeaders -Body @{
    output_filename = "go_live_manifest.json"
    output_format = "json"
} | Out-Host

Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/ledger-manifests/verify" -Headers $opsHeaders -Body @{
    output_filename = "go_live_manifest.json"
} | Out-Host

Write-Host "`n[7/8] Retention + legal-hold smoke"
Invoke-RestMethod "$BaseUrl/data-retention-policy" -Headers $roHeaders | Out-Host
Invoke-RestMethod "$BaseUrl/invoices/$InvoiceId/data-retention-review?as_of_date=2035-01-01" -Headers $roHeaders | Out-Host
Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/data-retention-legal-holds/open" -Headers $opsHeaders -Body @{
    held_by = "ADMIN-GO"
    reason = "Final legal QA"
    hold_type = "LITIGATION_PENDING"
} | Out-Host
try {
    Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/data-retention-disposals" -Headers $opsHeaders -Body @{
        approved_by = "ADMIN-GO"
        reason = "Retention complete"
        as_of_date = "2035-01-01"
    } | Out-Host
} catch {
    Write-Host "Expected block while legal hold active: $($_.Exception.Message)"
}
Invoke-JsonPost -Url "$BaseUrl/invoices/$InvoiceId/data-retention-legal-holds/release" -Headers $opsHeaders -Body @{
    released_by = "ADMIN-GO"
    reason = "QA complete"
} | Out-Host

Write-Host "`n[8/8] Final checks"
Invoke-RestMethod "$BaseUrl/ready" | Out-Host
Invoke-RestMethod "$BaseUrl/metrics" -Headers $adminHeaders | Out-Host
Invoke-RestMethod "$BaseUrl/invoices/$InvoiceId/compliance-ledger" -Headers $roHeaders | Out-Host
Invoke-RestMethod "$BaseUrl/invoices/$InvoiceId/ledger-events" -Headers $roHeaders | Out-Host

Write-Host "`nGo-live command sheet completed."
