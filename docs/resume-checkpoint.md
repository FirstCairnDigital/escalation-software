# P26003 Resume Checkpoint

Paused:
3 September 2026

Status:
PAUSED — SAFE DORMANT CHECKPOINT

Repository:
FirstCairnDigital/escalation-software

Branch:
agents/p26003-production-remediation

Last independently verified implementation SHA:
3a22248cd92a89e6b2c9af609e481aafac6d3fbe

Last completed phase:
Phase 15C — PostgreSQL Production Persistence and Database Gates

Next phase:
Phase 16 — Evidence Storage Seam + Azure Blob

## Completed production-readiness phases

Phase 14
Customer live shell and container runtime — COMPLETE

Phase 15A
Persistence configuration/factory seam — COMPLETE

Phase 15B1
PostgreSQL 18.6 foundation, migrations, append-only protection,
ledger concurrency and CI integration — COMPLETE

Phase 15B2
PostgreSQLStore behavioural parity and PostgreSQL integration testing
— COMPLETE

Phase 15C
PostgreSQL application enablement, production database fail-closed gates
and backend-aware readiness — COMPLETE

## Current database state

- PostgreSQL 18.6 production persistence implementation exists.
- Psycopg 3.3.5.
- PostgreSQLStore and PostgreSQLInvoiceLedger are enabled when selected.
- Versioned/checksummed migrations run before PostgreSQL use.
- 0001_initial.sql is immutable.
- PostgreSQL append-only protections are active.
- PostgreSQL ledger concurrency uses database-native locking.
- production refuses SQLite.
- production requires explicit PostgreSQL DATABASE_URL.
- production requires approved PostgreSQL TLS.
- SQLite remains development/reference backend.
- /ready is backend-aware.
- database credentials are not exposed by readiness/config reporting.

## Last verified testing

Local:
- persistence config tests: 19 OK
- PostgreSQL application tests: 3 OK
- complete PostgreSQL tests: 21 OK
- complete ordinary suite: 165 OK, skipped=3
- pip check: OK

GitHub Actions:
Run 33779536138 — SUCCESS

Passed:
- PostgreSQL 18.6 service initialization
- reproducible dependency installation
- ordinary tests
- PostgreSQL integration tests
- packaging validation
- dependency vulnerability scan
- Gitleaks

## Production status

P26003 IS NOT LIVE.

Do not enter real customer data.

No Azure production deployment has been completed.

No Azure Blob production evidence storage exists yet.

Human customer authentication is not complete.

Queue/worker/outbound production communications are not complete.

## Remaining roadmap

Phase 16
Evidence storage seam + Azure Blob

Phase 17
Human identity + tenant membership

Phase 18
Queue/worker/outbound communication

Phase 19
Commercial creditor workflow

Phase 20
Azure infrastructure + staging deployment

Phase 21
Staging UAT/security/recovery

Phase 22
Restricted production

Phase 23
99% live-readiness signoff

## Resume procedure

When P26003 development resumes:

1. Open/pull agents/p26003-production-remediation.
2. Confirm this checkpoint/tag.
3. Confirm the working tree is clean.
4. Read:
   - docs/resume-checkpoint.md
   - docs/production-live-readiness-plan.md
5. Confirm the Phase 15C baseline still builds/tests if necessary.
6. Resume directly with Phase 16.
7. Do NOT repeat Phase 14–15 audits without a specific reason.
8. Do NOT rewrite 0001_initial.sql.

## Current project priority

P26002 is the active First Cairn Digital development priority.

P26003 should remain dormant until explicitly resumed.
