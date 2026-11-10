# SMVS Operations implementation list

This list tracks product work. The Exceptions To-do list tracks individual
alerts that require follow-up.

## Next

- [ ] Add report coverage and upload evidence to the A2 groups. Retain the
  pack-level RCA and timely investigation path for A3.
- [ ] Simplify the Swiss RCA around evidence, assessment and next action.
  Reuse retained evidence and keep a participant's feedback distinct from
  the NMVO assessment.

## Planned

- [ ] Review parent company links for invoice routing.
- [ ] Design on-demand company summary drafts and review a separate company news
  view for events such as announced acquisitions. Retain imported company size for reference.
- [x] Import historical self-declarations with RX sales groups and packs sold,
  link agreements and contract documents to MAHs, and show a fee preview.
- [ ] Implement [self-declaration invitations, Tally intake and delivery](../integration/self-declaration-workflow.md).
- [ ] Prepare Bexio as the invoicing system from 2027-01-01.

- [ ] Review the staged Airtable MAH and Contacts columns. Map agreed CRM
  fields, contract status and verified Alert SPOC assignments.
- [ ] Agree report delivery rules by contract status and implement reviewed
  SendGrid delivery with recipient and outcome history.
- [ ] Produce End-user monthly reports with prevention tasks and reviewed
  workflow context. Carry confirmed recurring process issues into CAPA follow-up.
- [ ] Extend A7 rule coverage after reviewing labelled examples, including
  same-location decommissioning, delegated operations and robot retry patterns.
- [ ] Validate event coverage for geographic pattern analysis and document
  exceptions for known workflows.
- [ ] Configure and validate the OpenAI search prototype with general queries.
- [ ] Add authenticated actors, Shared Investigation and End-user invitations.
  Extend the audit trail to registrations and permissions, then integrate AMS Hub.
- [ ] Prepare Incident Report text for CANEA once the required template is available.

## Available

- [x] Operational imports and scheduler controls.
- [x] Exceptions, Pack Audit Trail and upload evidence.
- [x] Local RCA, Resolve and Reopen, including selected batch actions and an
  audit trail.
- [x] A7 Export and Destroy analysis, versioned rule scope and preview with
  confirmed application to selected cases.
- [x] Configurable text size and an Actions area above the Exceptions list.
- [x] Initial internal A2/A3 monthly drafts grouped by provisional SAI holder,
  product and batch, with a separate review of unresolved assignments.
- [x] Stage Airtable MAH and Contacts CSV exports for column and relationship
  review under CRM.
- [x] Import the Contacts directory and support reviewed SPOC and Alert contact
  assignments from the MAH profile.
- [x] Maintain MAH master records with create, edit, archive and restore. Seed
  the agreed identity fields from staged MAH data and retain source provenance.

Related references: [Implementation status](IMPLEMENTATION-STATUS.md),
[evidence-guided investigation](../architecture/Evidence-Guided-Alert-Investigation.md)
and [CRM proposal](../architecture/Shared-Investigation-and-CRM-Proposal.md).

## CRM End Users

- [x] Stage the End Users export and review exact matches to the current NMVS
  organisation snapshot. Flag duplicate or differing source labels.
- [x] Add the CRM End User profile with exact-match and manual links by stable
  NMVS organisation identity. Show imported CRM information separately.
- [x] Create, edit, archive and restore End Users and assign existing CRM contacts.
- [ ] Confirm how to reconcile later exports without a stable Airtable record ID.
- [ ] Add an optional single Software Product selection per End User. Use a shared
  catalogue of software used to connect to NMVS and maintain IT Supplier separately.

## CRM IT Suppliers

- [x] Stage the Airtable export and show suppliers in a searchable CRM directory.
  Review candidate links to Contacts and End Users.
- [ ] Confirm supplier identity and editable fields before creating maintained
  supplier records and linking suppliers to the Software Product catalogue.

## Portal identity and access

- [x] Add the opt-in internal passkey pilot with invitations, user lifecycle,
  Administrator and NMVO roles, and server-side access checks.
- [ ] Add recovery codes, supervised recovery and authentication audit events.
- [x] Store CRM column preferences per authenticated user and directory.
- [ ] Release MAH reports to explicitly assigned SAI holders after review.

- [x] Unify CRM directory filter controls and store visible filters and default values per signed-in user, with reset and explicit-link precedence.

- [x] Personal CRM column selection per account and directory, with immediate preview and independent reset.

- [x] Persist CRM column order, with accessible up/down controls and reset.
- [x] Define a shared typed CRM business-field catalogue for list columns and future view conditions, with current-value precedence and labelled source-only values.
- [x] Apply the shared data-first hierarchy, consistent buttons and tabs-before-title layout across operational and reference portal pages.
- [x] Add manual contact creation and data-first CRM typography, with module tabs first and consistent creation buttons beside titles.
- [x] Keep CRM record navigation visible during section editing and provide guarded keyboard shortcuts for record, tab and list review navigation.
- [x] Move existing MAH, Contact and End User record actions to a right-hand toolbox opened from the record navigation.
- [x] Provide a compact CRM toolbar and responsive right-hand View toolbox (Conditions, Columns, Save view), with Apply preview and keyboard support.
- [x] Replace filter visibility configuration with named CRM views combining conditions, columns, order and a personal default. See `docs/technical/CRM-LIST-VIEWS.md`.

- [ ] Connect live self-declaration lifecycle states to outstanding-response views.
- [ ] Consider shared CRM views and OR condition groups after the personal-view workflow is accepted.


### 2026-11-08 — Shared table views

- [x] Extend personal views, column selection/order and right-hand toolboxes to non-CRM record/report tables.
- [x] Apply core directory and related-list conditions before pagination; retain view context in record navigation.
- [x] Move existing table actions into the shared Actions toolbox without changing their operation scope.
- [x] Document retrieved report-scope limits and personal defaults in the User Guide and UI guidelines.

### 2026-11-09 — Public deployment security and Tally registration

Target: Infomaniak Jelastic; DNS Cyon; `https://operations.smvs-gmbh.ch`.
The portal is intended to be public with passkey access. Only nginx should have
public ingress; application/DB access remains private.

- [x] Review the current application, local DB connection and installed dependencies; record scope, positive controls, findings and acceptance criteria in [Security Review 2026-11-09](../technical/SECURITY-REVIEW-2026-11-09.md).
- [ ] Package A: update affected certifi, lock dependencies; enforce production settings; verify DB TLS/hostname; separate minimal runtime/migration/worker privileges; establish supervised ASGI deployment.
- [ ] Package B: shared login/resource limits, server-side idle expiry, recent passkey verification for critical account operations and consistent security headers.
- [ ] Package C: authenticated actor for Resolve/Reopen; security events for account changes/downloads; remove sensitive query/body logging; restrict external AI inputs.
- [ ] Package D: implement/approve protection against SQL-dump exposure across serial fields, raw evidence, artifacts and saved searches; separate encryption keys; encrypted backups and restore tests; retention/erasure process.
- [ ] Recheck actual nginx → Apache (if retained) → Uvicorn deployment, certificate/Origin forwarding, private DB firewall, alternate hostnames and IPv6; independent security test before public real-data release.
- [x] Package E local implementation: End-User registration via Tally (public activation remains pending): signed bounded webhook, submission idempotency, pending CRM review, subsequent NMVS linking, encrypted temporary security question/answer with explicit deletion lifecycle. No automatic internal portal role assignment.

The review itself does not remediate these findings or approve deployment.

### 2026-11-09 — Proposed VPN core / public collaboration separation

- [x] Document the recommended [private core / public collaboration architecture](../architecture/Operations-Core-and-Collaboration-Portal.md), retaining all security-review measures.
- [ ] Confirm and enforce VPN-only Operations access with passkeys and private DB, including provider hostnames and IPv6.
- [ ] Define a minimal investigation publication/contribution contract, separate public deployment/store, participant access and internal pull/outbox exchange.
- [ ] Keep the public Tally registration intake separate from the RCA-only communication scope; retrieve pending registrations internally without exposing CRM routes.

The earlier public-core target remains historical context; this is the proposed
replacement topology and has not been deployed.

### 2026-11-09 — End-user registration workflow

Historical buffered implementation below; deployment was superseded by the
stateless Connect architecture in the following section. No public database is
required for the selected architecture.

- [x] Separate public Tally intake/confirmation ASGI app with its own metadata/store; no Operations routes or NMVS credentials.
- [x] Stable w7AWGA field mapping, HMAC webhook validation, bounded payloads and submission-level idempotency.
- [x] Encrypted temporary intake/security data; expiring single-use confirmation link; GET does not confirm.
- [x] Durable SendGrid mail queue with supplied template ID; explicit sender/link-placeholder configuration, no implicit retries of uncertain deliveries and controlled resend.
- [x] Internal pull/acknowledgement after CRM commit; provisional CRM End User/contact, review dashboard and attributed workflow actions.
- [x] Email confirmation/review/manual NMVS stages; duplicate checks, stale-form rejection, reviewed-data change detection, security-data access and erasure.
- [x] Personal list views and Actions toolbox; portal User Guide, integration/cutover instructions and a repeatable isolated test workspace.
- [ ] Supply/verify the SendGrid sender and existing template's confirmation-link placeholder; set the API key locally.
- [ ] Deploy/harden the isolated public intake, choose its hostname, provision separate DB/secrets, configure the signed Tally webhook and supervised mail/pull/purge processes.
- [ ] Run a controlled real end-to-end test and reconcile pending legacy PHP/Airtable confirmations before switching senders. Current public workflow has not been changed.

### 2026-11-09 — SMVS Connect direct registration boundary

- [x] Replace the selected public-buffer design with a stateless Connect gateway; the old intake is retained only for local compatibility.
- [x] Fixed authenticated private commands for signed submissions and one-time email confirmation; no public CRUD/list/resend/approval endpoints.
- [x] Internal atomic receipt/outbox plus CRM registration transaction, with replay-safe commits and no acknowledgement on uncertain persistence.
- [x] Internal SendGrid/cleanup worker, direct status updates, local resend and seven-day encrypted security-data lifecycle.
- [x] Public deployment allowlist excludes database drivers, core models, encryption/mail keys; add migration 0041 locally. Full suite: 448 tests passed.
- [x] Verify Connect DNS, matching Let's Encrypt certificate and HTTP 308 redirect; reach internal node 207849 at 10.100.32.195 from Connect.
- [x] Configure primary MySQL 10.100.36.111: restricted TLS-only runtime user for 10.100.32.195; migrate and verify all 58 local tables into the previously empty smvs_operations schema. Preserve other schemas and local source.
- [x] Stage current private runtime separately and verify CA + pinned-certificate TLS and plaintext rejection. Full suite: 454 tests passed.
- [x] Stage and smoke-test the stateless Connect source on public Apache node 221302 without activating it or transferring core credentials.
- [x] Deploy current internal code, CA-verified private TLS and source-IP restrictions; supervise private API/mail/cleanup and public ASGI processes.
- [x] Public synthetic and actual-form end-to-end acceptance; user disabled Airtable producer, automatic Operations mail enabled. Preserve outstanding old PHP confirmation links.

### 2026-11-10 — Connect activation and controlled acceptance

- [x] Main portal private HTTPS and production-hostname administrator passkey enrolment (user confirmed success).
- [x] Activate stateless Connect on public Apache node 221302 under Supervisor and a cron startup watchdog; no public database or mail worker.
- [x] Fixed NGINX upstream, exact route allow-list, body/time/rate limits, HTTP redirect, and disabled HTTP/HTTPS access logging. Preserve ACME challenge path.
- [x] Verify public pages/assets, private route rejection, unsigned webhook rejection and cross-origin confirmation rejection.
- [x] Add a one-receipt-only internal mail command with a two-registration isolation regression test. Full suite: 456 tests passed.
- [x] User added TCP 8443 from Connect node 10.100.37.97/32 in internal environment firewall. Verified CA TLS, permitted source, authenticated invalid-token 400 and missing-bearer 401.
- [x] Public synthetic registration and identical replay both accepted with one receipt/CRM workflow record; exactly one confirmation mail accepted by SendGrid for reinhold.sojer@smvo.ch.
- [x] User confirmed the cloud test email; verified Needs review, email_confirmed audit event, linked CRM records and erasure of receipt payload / one-time token.
- [x] Actual-form Tally smoke test passed: receipt/workflow ID 2, linked CRM records, exactly one automatic mail, explicit confirmation, Needs review, audit event and receipt/token erasure.
- [x] User confirmed direct Tally/Airtable integration disabled and Connect webhook active. Empty mail queue at cutover; registration-mail RUNNING/autostart true, separate purge-only worker stopped/autostart false. Preserve old PHP endpoint/token store for outstanding links.
- [ ] Configure automatic DNS-01 certificate renewal for operations.smvs-gmbh.ch (current certificate expires 2027-02-07).
- [ ] Remove the temporary Mac hosts entry with administrator privileges after DNS/browser verification; authoritative DNS now returns 10.100.32.195.

### 2026-11-10 — Real Tally field compatibility

- [x] Diagnose actual 422: layout UUIDs differed from webhook question IDs. Correct all 20 field IDs in Connect and private API.
- [x] Add independent synthetic fixture with real observed field-key/option structure and safe diagnostic logging tests. Full suite: 458 passed.
- [x] New actual-form test with a 13-digit synthetic GLN completed and confirmed; old ten-digit test remains rejected without creating CRM records.
- [ ] Add matching 13-digit GLN validation in Tally to avoid post-submission format errors.

- [x] Administrator-only deletion of direct registration workflows, with optional
  atomic deletion of linked unshared CRM End User/contact; explicit confirmation,
  stale-form protection, minimal deletion audit and tombstones preventing replay.
- [x] Guarded permanent deletion in CRM Actions for End Users, contacts and MAHs;
  archive remains available for reversible removal.

- [x] Persist imported MAH SPOCs and Alert contact groups using unambiguous existing
  CRM contacts; repeatable backfill and import-order-independent seeding, preserving
  manual selections. Surface unresolved references on the MAH Contacts card.

### 2026-11-10 checkpoint and next deployment

- [x] Record the private/public Jelastic topology, deployed feature baseline and
  local-only changes in [deployment status](../deployment/STATUS-2026-11-10.md).
- [x] Develop and test imported-contact deletion locally: retain MAHs/End Users,
  detach only contact assignments and prevent recreation by Airtable reimport.
- [x] Upgrade local MySQL to 0043; Jelastic remains on 0042.
- [ ] Locally accept the imported-contact deletion UI, then push the reviewed
  commit and explicitly deploy it with migration 0043 and a production smoke test.
- [x] Adopt local development → tests → commit → Git push → identified deployment;
  use the server for bounded external integration smoke tests, not primary development.
