# P26003 Production Live-Readiness Plan

This document is the controlling implementation plan for the Phase 14
customer live shell and container runtime work on
`agents/p26003-production-remediation`.

## Scope

This phase delivers:

1. a customer-facing public shell for creditor and debtor journeys;
2. a production-style ASGI entry point that mounts the existing core app
   without renaming its routes;
3. browser hardening headers for public shell pages;
4. focused live-shell tests;
5. a non-root container runtime suitable for pre-deployment validation.

This phase does **not**:

- change domain, escalation, pricing-rule, legal-rule, or evidence logic;
- change persistence architecture;
- introduce PostgreSQL, Blob storage, Entra, or Azure SDK dependencies;
- deploy infrastructure;
- claim customer-production readiness for live data.

## Implementation Controls

### 1. Public customer shell

- Add [customer_ui.py](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/src/unpaid_invoice_escalator/customer_ui.py)
  for restrained branded rendering.
- Add [live_app.py](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/src/unpaid_invoice_escalator/live_app.py)
  as the outer ASGI entry point.
- Provide public routes:
  - `GET /`
  - `GET /creditor`
  - `GET /debtor`
- Mount the existing core application at the root so existing routes
  continue unchanged:
  - `/health`
  - `/ready`
  - `/verify`
  - `/portal`
  - `/ui/*`
  - `/invoices/*`

### 2. Customer copy constraints

Public pages must:

- present clear creditor and debtor journeys;
- describe B2B unpaid-invoice resolution only;
- state support for England & Wales, Scotland, and Northern Ireland;
- explain staged workflow progression;
- explain that chargeable stages are shown before commitment;
- explain that creditors can stop between stages where permitted;
- avoid presenting FCD as a solicitor, court, debt collector, or legal representative;
- avoid consumer-credit or out-of-boundary debt claims;
- avoid internal terminology such as RBAC, ledger hashes, deployment checks, or secret/config names.

### 3. Security and privacy controls

- Apply public-page browser headers:
  - `X-Content-Type-Options: nosniff`
  - `X-Frame-Options: DENY`
  - `Referrer-Policy: no-referrer`
  - `Cache-Control` suitable for public non-personal pages
- Do not weaken core-app headers.
- Do not embed customer data, API keys, or configuration values in public markup.

### 4. Container runtime

- Add a Docker runtime using Python 3.11 slim.
- Install dependencies from the current reproducible
  [requirements.txt](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/requirements.txt)
  and [constraints.txt](C:/Dev/P26003-escalation-software.worktrees/code-inspection-report/constraints.txt)
  set.
- Run as a non-root user.
- Expose port `8000`.
- Start with:

  `uvicorn unpaid_invoice_escalator.live_app:app --host 0.0.0.0 --port 8000`

- Add a lightweight container health check against `/health`.

## Validation

Validation for this phase must include:

1. targeted live-shell tests first;
2. full `python -m unittest discover -s tests`;
3. `python -m pip check`;
4. Docker build if Docker is available;
5. local container smoke checks for `/` and `/health` if practical;
6. diff/status inspection for unrelated changes and secrets.

## Known Remaining Blockers After This Phase

Even if this phase is green, live customer production data is still blocked by:

- PostgreSQL or equivalent production-grade database work;
- Blob/object storage for production artifact handling;
- human creditor authentication/sign-in;
- production identity and infrastructure rollout.
