# P26003 Everything Manual (Simple Version)

If you are in a hurry and just need to run this safely, follow this in order.

## 1) What this system is
- It helps with B2B unpaid invoice workflow and evidence prep.
- It is **not** a law firm or debt collection agency.

## 2) What you need first
- Python 3.11+
- Repo checked out locally
- Terminal in repo root:
  - `C:\Dev\projects\P26003-escalation-software`

## 3) First-time setup
```powershell
pip install -e .
```

## 4) Start the API (local)
```powershell
$env:PYTHONPATH="C:\Dev\projects\P26003-escalation-software\src"
python -m unpaid_invoice_escalator.api
```

API should run on: `http://127.0.0.1:8000`

## 5) Quick health check
Open another terminal and run:
```powershell
Invoke-RestMethod "http://127.0.0.1:8000/health"
Invoke-RestMethod "http://127.0.0.1:8000/ready"
```

Expected:
- `/health` => `status=ok`
- `/ready` => `status=ready`

## 6) Production env basics (minimum)
Set these before production startup:
```powershell
$env:FCD_APP_ENV="production"
$env:FCD_MANIFEST_SIGNING_KEY="<strong-secret>"
$env:FCD_MANIFEST_KEY_ID="fcd-kms-key-1"
$env:FCD_MANIFEST_VERIFY_KEYS="fcd-kms-key-1:<current-key>,fcd-kms-key-0:<previous-key>"
$env:FCD_API_KEYS="admin-key:admin,ops-key:operator,ro-key:viewer"
$env:FCD_DATA_RETENTION_DAYS="2190"
```

## 7) Run the go-live command sheet
This performs the end-to-end operational checks:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\go-live-command-sheet.ps1
```

If your keys/base URL are different:
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\go-live-command-sheet.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -AdminApiKey "admin-key" `
  -OpsApiKey "ops-key" `
  -ReadOnlyApiKey "ro-key" `
  -InvoiceId "inv-go-live-001"
```

## 8) Run formal red/green signoff
```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\ops\go-live-red-green-signoff.ps1 `
  -BaseUrl "http://127.0.0.1:8000" `
  -AdminApiKey "admin-key" `
  -OpsApiKey "ops-key" `
  -ReadOnlyApiKey "ro-key" `
  -InvoiceId "inv-go-live-001"
```

Interpretation:
- `GREEN` = pass
- `RED` = fail / no-go

## 9) Fill in operator signoff
Use:
- [operator-go-live-runbook-template.md](C:/Dev/projects/P26003-escalation-software/scripts/ops/operator-go-live-runbook-template.md)

Complete all checkboxes and signatures before go-live.

## 10) If something fails
1. Do **not** go live.
2. Save output from failed command.
3. Check:
   - `GET /deployment/startup-config-validation/report`
   - `GET /metrics`
4. Fix config/keys/path issues first.
5. Re-run command sheet and signoff script.

## 11) Handy file list
- Command sheet: [go-live-command-sheet.ps1](C:/Dev/projects/P26003-escalation-software/scripts/ops/go-live-command-sheet.ps1)
- Red/green signoff: [go-live-red-green-signoff.ps1](C:/Dev/projects/P26003-escalation-software/scripts/ops/go-live-red-green-signoff.ps1)
- Operator signoff template: [operator-go-live-runbook-template.md](C:/Dev/projects/P26003-escalation-software/scripts/ops/operator-go-live-runbook-template.md)
