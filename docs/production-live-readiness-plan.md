# P26003 Production Live-Readiness Plan

This document is the controlling implementation plan for the production-readiness work on `agents/p26003-production-remediation`.

It is the master roadmap for the remaining live-readiness sequence and supersedes any phase-specific note.

## Non-Negotiable Gates

Before any production customer data is accepted, the following gates must be satisfied:

- no real customer data before PostgreSQL, object storage and human auth are in place;
- production fails closed;
- human customers never use API keys;
- production evidence never depends on container-local disk;
- every chargeable creditor stage requires explicit acceptance;
- staging before production;
- backup restore must be demonstrated;
- deployment rollback must be demonstrated;
- no unresolved severity-1 issue before production;
- tenant isolation must be demonstrated;
- legal/rulepack/customer-copy sign-off before launch;
- initial Azure planning budget is £35/month ex VAT;
- SQLite remains a development/reference implementation only;
- PostgreSQL is the production database;
- Blob/object storage is the production evidence store;
- Azure Container Apps is the initial compute target;
- Key Vault and managed identity are required for production secrets;
- Azure Queue Storage is the initial worker queue;
- Entra External ID is the human creditor identity provider;
- GitHub Actions is used for staging and protected production deployment.

## Roadmap

### Phase 14 — Customer live shell + container runtime

Deliver the customer-facing shell and production-style runtime while preserving the existing application structure.

Required outputs:

- public shell routes: `GET /`, `GET /creditor`, `GET /debtor`;
- outer ASGI entry point mounting the existing core app without renaming or duplicating routes;
- preserved internal routes under their existing paths (`/health`, `/ready`, `/verify`, `/portal`, `/ui/*`, `/invoices/*`, etc.);
- restrained First Cairn Digital branded customer pages;
- no internal admin/compliance links on public pages;
- no API key or config exposure in public output;
- browser security headers for public pages;
- Dockerfile and `.dockerignore` using Python 3.11 slim and a non-root runtime;
- lightweight health check against `/health`;
- focused live-shell tests proving shell functionality and compatibility.

Completion gate:

- container build succeeds;
- container starts cleanly with non-root `fcd` user;
- public pages return 200 and expose no secrets;
- core routes remain reachable.

### Phase 15 — Persistence seam + PostgreSQL

Introduce a production persistence seam and move the data layer to PostgreSQL without changing the wider domain behaviour.

Status:

- 15A complete;
- 15B1 complete;
- 15B2 complete;
- 15C complete.

Required outputs:

- define the persistence boundary and configuration seam;
- replace SQLite as the production database path with PostgreSQL-ready integration;
- do not use local SQLite for production data flows;
- preserve SQLite as an allowed development/reference implementation only;
- connection separation for operational and business data;
- migration and schema validation path for production data;
- staged rollout guardrails before any live customer data is accepted.

Completion gate:

- PostgreSQL deployment seam validated in staging;
- tenant isolation and transactional integrity demonstrated;
- production data is not accepted before this phase is green.

### Phase 16 — Evidence storage seam + Azure Blob

Introduce the production evidence storage boundary and move artifact handling away from container-local disk.

Required outputs:

- production evidence storage seam for contracts, documents, proofs, and notices;
- Azure Blob Storage or equivalent object-store integration;
- immutable evidence metadata and integrity checks;
- no customer evidence stored on container-local filesystem in production;
- complete evidence lifecycle with retrieval, verification, and retention controls;
- production evidence access remains isolated to approved workflow components.

Completion gate:

- evidence upload and retrieval tested against the production seam;
- object-store integrity checks passed;
- no production evidence dependency on local disk remains.

### Phase 17 — Human customer identity + tenant membership

Add the customer identity layer and tenant membership model for real creditors and debtors.

Required outputs:

- Entra External ID for human customer identity;
- no human customer uses API keys;
- tenant membership model for creditor/customer access and case authorization;
- human sign-in and authorization boundaries for staff-facing and customer-facing surfaces;
- separation between authenticated customer identity and API credential identity;
- production fail-closed enforcement when identity or tenant membership is absent.

Completion gate:

- human customer sign-in works in staging;
- tenant membership is demonstrated and enforced;
- API credentials remain credentials only, never actor identity.

### Phase 18 — Queue, worker + outbound communication

Add asynchronous processing for background work and outbound communications while preserving auditability.

Required outputs:

- Azure Queue Storage as the initial worker queue;
- background worker processing for communication, status, and escalation tasks;
- payload schema for outbound notices and status updates;
- retry, dead-letter, and audit tracking for worker failures;
- outbound communications never bypass compliance checks or versioned rule packs;
- event-ledger visibility for worker actions and retries.

Completion gate:

- message queue and worker pipeline validated in staging;
- failed worker tasks are visible and recoverable;
- no production action is launched without audit traceability.

### Phase 19 — Commercial creditor workflow/pricing

Implement the commercial creditor workflow, stage gating, and explicit pricing acceptance behaviours.

Required outputs:

- staged commercial workflow with clear creditor actions and outcomes;
- chargeable stages shown before explicit commitment;
- no chargeable action proceeds without acceptance;
- pricing and fee schedule loaded from the rule pack rather than hardcoded in code;
- debtor response handling, payment plans, settlement offers, and evidence handoff flow integrated with the staged workflow;
- customer-facing copy and pricing disclosures reviewed for legal/marketing compliance.

Completion gate:

- each stage is explicit, accepted, and auditable;
- no chargeable stage is silently triggered;
- pricing and terms remain aligned with the approved rule packs.

### Phase 20 — Azure IaC + staging deployment

Create the infrastructure-as-code baseline and staging deployment target.

Required outputs:

- Azure Container Apps as the initial compute target;
- Key Vault and managed identity for production secrets;
- environment-specific configuration for staging and production;
- repository-controlled IaC for the app service boundary and dependent resources;
- GitHub Actions deployment pipeline to staging;
- initial planning budget of £35/month ex VAT.

Completion gate:

- staging deployment succeeds from the repository pipeline;
- secrets are sourced from Key Vault rather than baked into images;
- infrastructure and deployment metadata are auditable.

### Phase 21 — Staging UAT/security/backup/restore/rollback

Run the production-facing staging environment through a formal readiness pass.

Required outputs:

- staging UAT with business, legal, and ops sign-off;
- security review for headers, secrets, auth, tenant isolation, and data handling;
- backup/restore proof demonstration;
- rollback proof demonstration;
- evidence and data recovery integrity checks;
- rulepack/customer copy sign-off before moving to restricted production.

Completion gate:

- staging is demonstrably recoverable and rollback-capable;
- backup/restore process is proven;
- no unresolved severity-1 issue remains open.

### Phase 22 — Restricted production rollout

Open a narrow, monitored production rollout only after all required gates are green.

Required outputs:

- restricted customer slice or controlled rollout; 
- production monitoring for health, errors, privacy, evidence, and tenant boundaries;
- transaction and compliance telemetry review;
- staged release gates, hold points, and manual sign-off criteria;
- no broad production exposure before staging and UAT evidence is complete.

Completion gate:

- limited production rollout is stable and auditable;
- tenant isolation, evidence integrity, and customer sign-in remain green;
- there are no unresolved production-level blockers.

### Phase 23 — 99% live sign-off

Complete final operational readiness, legal approval, and release gating for production.

Required outputs:

- final legal/rulepack/customer-copy sign-off;
- production runbook and incident response procedures;
- operational monitoring, support ownership, and escalation matrix;
- final security review over auth, evidence, tenant isolation, and data handling;
- final production deployment approval with protected GitHub Actions path;
- signed-off readiness statement with residual risks and operational controls.

Completion gate:

- all non-negotiable gates are demonstrated and retained in evidence;
- production launch is constrained to approved operational controls;
- live readiness reaches the acceptance bar for controlled launch.

## Operational Principles

- The default is fail-closed for production configuration and request handling.
- Customer data remains out of scope until persistence, evidence storage, and human auth are productionised.
- Use rule-pack-driven logic, not hardcoded legal or fee assumptions, for production-critical behaviour.
- Keep SQLite as a non-production development/reference implementation only.
- Treat all customer and evidence data as sensitive and subject to explicit governance controls.
- Do not mix API credentials with actor identity in durable records or business decisions.

## Implementation Order

The order remains:

1. Phase 14 customer shell and container runtime;
2. Phase 15 PostgreSQL persistence seam;
3. Phase 16 Azure Blob evidence storage seam;
4. Phase 17 human customer identity and tenant membership;
5. Phase 18 queue, worker, and outbound communications;
6. Phase 19 commercial creditor workflow and pricing;
7. Phase 20 Azure IaC and staging deployment;
8. Phase 21 staging UAT, backup/restore, rollback, and security review;
9. Phase 22 restricted production rollout;
10. Phase 23 final 99% live sign-off.

This roadmap is the controlling implementation plan for the repository branch until the final 99% live sign-off is complete.
