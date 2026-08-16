# P26003 Operator Go-Live Runbook

**Release version/commit:** __________  
**Environment:** __________  
**Date/Time (UTC):** __________  
**Operator:** __________

## 1) Readiness Gate
- [ ] `/health` returns `ok`
- [ ] `/ready` returns `200` and `status=ready`
- [ ] `/deployment/startup-config-validation` has zero error-severity failures
- [ ] `/deployment/startup-config-validation/report` reviewed and accepted

**Evidence links/output references:**  
________________________________________

## 2) Security & Access Gate
- [ ] Admin access to `/metrics` works
- [ ] Public routes (`/verify`, `/portal`, `/portal/actions/*`) behave as expected
- [ ] Non-public routes enforce API key and role controls

**Evidence links/output references:**  
________________________________________

## 3) Core Workflow Gate
- [ ] Invoice creation succeeds
- [ ] Case health check reaches `READY`
- [ ] Discrepancy check validates expected values
- [ ] Debtor verification register + `/verify` + `/portal` succeed

**Evidence links/output references:**  
________________________________________

## 4) Escalation Guardrail Gate
- [ ] Open data-accuracy challenge blocks escalation
- [ ] Open debtor dispute blocks escalation
- [ ] Future promised payment date blocks escalation
- [ ] Escalation resumes when blocker conditions clear/expire

**Evidence links/output references:**  
________________________________________

## 5) Evidence & Audit Integrity Gate
- [ ] Evidence upload policy enforces allow/deny/quarantine
- [ ] Evidence bundle generation succeeds with enriched sections
- [ ] Manifest generation and verification succeed
- [ ] Critical actions create immutable compliance + ledger events

**Evidence links/output references:**  
________________________________________

## 6) Retention & Legal Hold Gate
- [ ] `/data-retention-policy` matches approved policy
- [ ] Legal hold open/release operations succeed
- [ ] Disposal is blocked while legal hold is active
- [ ] Disposal succeeds only when eligible and logs disposal event

**Evidence links/output references:**  
________________________________________

## 7) Monitoring & Handoff Gate
- [ ] Baseline metrics captured (auth failures, 429s, 5xx, upload quarantine)
- [ ] Alert channels and thresholds confirmed
- [ ] On-call handoff completed

**Evidence links/output references:**  
________________________________________

---

## Go/No-Go Signoff

### Ops Signoff
**Name:** ____________________  
**Decision:** [ ] GO  [ ] NO-GO  
**Notes:** ____________________

### Security Signoff
**Name:** ____________________  
**Decision:** [ ] GO  [ ] NO-GO  
**Notes:** ____________________

### Compliance Signoff
**Name:** ____________________  
**Decision:** [ ] GO  [ ] NO-GO  
**Notes:** ____________________

### Final Release Authority
**Name:** ____________________  
**Final Decision:** [ ] GO  [ ] NO-GO  
**Timestamp (UTC):** ____________________  
**Notes:** ____________________
