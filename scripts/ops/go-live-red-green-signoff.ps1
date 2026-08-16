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

$results = New-Object System.Collections.Generic.List[object]

function Add-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Details
    )
    $status = if ($Passed) { "GREEN" } else { "RED" }
    $results.Add([PSCustomObject]@{
        check = $Name
        status = $status
        passed = $Passed
        details = $Details
    })
}

function Try-Check {
    param(
        [string]$Name,
        [scriptblock]$Action
    )
    try {
        & $Action
    } catch {
        Add-CheckResult -Name $Name -Passed $false -Details $_.Exception.Message
    }
}

Try-Check -Name "health-endpoint" -Action {
    $resp = Invoke-RestMethod "$BaseUrl/health"
    Add-CheckResult -Name "health-endpoint" -Passed ([string]$resp.status -eq "ok") -Details ($resp | ConvertTo-Json -Depth 4 -Compress)
}

Try-Check -Name "ready-endpoint" -Action {
    $resp = Invoke-RestMethod "$BaseUrl/ready"
    Add-CheckResult -Name "ready-endpoint" -Passed ([string]$resp.status -eq "ready") -Details ($resp | ConvertTo-Json -Depth 4 -Compress)
}

Try-Check -Name "startup-config-validation" -Action {
    $resp = Invoke-RestMethod "$BaseUrl/deployment/startup-config-validation" -Headers $adminHeaders
    $hasErrors = @($resp.errors).Count -gt 0
    Add-CheckResult -Name "startup-config-validation" -Passed (-not $hasErrors) -Details ("errors=" + @($resp.errors).Count)
}

Try-Check -Name "manifest-verification" -Action {
    $manifest = Invoke-RestMethod -Method Post -Uri "$BaseUrl/invoices/$InvoiceId/ledger-manifests/verify" -Headers $opsHeaders -ContentType "application/json" -Body (@{
        output_filename = "go_live_manifest.json"
    } | ConvertTo-Json)
    $ok = [bool]$manifest.signature_valid -and [bool]$manifest.core_matches_current_ledger -and [bool]$manifest.overall_valid
    Add-CheckResult -Name "manifest-verification" -Passed $ok -Details ($manifest | ConvertTo-Json -Depth 6 -Compress)
}

Try-Check -Name "retention-policy-present" -Action {
    $policy = Invoke-RestMethod "$BaseUrl/data-retention-policy" -Headers $roHeaders
    $ok = [int]$policy.policy.retention_days -gt 0 -and [bool]$policy.policy.immutable_records_retained
    Add-CheckResult -Name "retention-policy-present" -Passed $ok -Details ($policy | ConvertTo-Json -Depth 4 -Compress)
}

Try-Check -Name "compliance-ledger-readable" -Action {
    $entries = Invoke-RestMethod "$BaseUrl/invoices/$InvoiceId/compliance-ledger" -Headers $roHeaders
    Add-CheckResult -Name "compliance-ledger-readable" -Passed ($entries.count -ge 0) -Details ("count=" + $entries.count)
}

$failed = @($results | Where-Object { -not $_.passed })
$passed = @($results | Where-Object { $_.passed })

Write-Host ""
Write-Host "==== P26003 RED/GREEN SIGNOFF CHECKS ===="
foreach ($result in $results) {
    $marker = if ($result.passed) { "[GREEN]" } else { "[RED]" }
    Write-Host "$marker $($result.check) :: $($result.details)"
}
Write-Host "========================================="
Write-Host ("Passed: " + $passed.Count + " | Failed: " + $failed.Count)

if ($failed.Count -gt 0) {
    Write-Error "GO/NO-GO RESULT: RED (one or more critical checks failed)."
    exit 1
}

Write-Host "GO/NO-GO RESULT: GREEN"
exit 0
