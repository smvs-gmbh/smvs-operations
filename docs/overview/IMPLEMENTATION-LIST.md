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

### Shared Alerts Management concept — 2026-11-10

- [x] Review supplied End-user/NMVO manuals and document an evidence-guided End-user
  pilot, pharmacy/wholesaler checks, shared case model and MAH extension in the
  [Shared Alerts Management concept](../architecture/Shared-Alerts-Management-End-User-Pilot.md).
- [ ] Agree Collaboration boundary (stateless dedicated API vs outbound projection),
  participant attribution, access expiry and initial attachment policy.
- [ ] Build local case/participant/publication model and participant-view preview.
- [ ] Add scoped invitation/session protocol, guided contributions, proposal
  responses and NMVO-only local resolution/reopening with auditable bulk scope.
- [ ] Integrate CRM affiliation change/archive/deletion with grant revocation before
  external access goes live; preserve internal/external message audiences.
- [ ] Run synthetic local/adversarial tests and controlled pharmacy/wholesaler
  release acceptance; gate photos on inspection/storage controls.
- [ ] Review the actual AMS Hub contract and add MAH participation in phase 2.

### EMVO gold standard and NMVO closure — 2026-11-10

- [x] Directly review the supplied EMVO-00306 copy and record source fingerprint,
  section/step mapping and owner-confirmed precedence over product manuals in the
  [EMVO alignment](../architecture/EMVO-Alert-Handling-Alignment.md).
- [x] Record the SMVS closure policy: the responsible NMVO controls investigation
  and closure; do not enable the source's optional MAH/End-user closure permissions.
- [ ] Derive a versioned guidance catalogue from End-User-01/02/03 and wholesaler
  variations, with source-step references and reuse of existing evidence.
- [ ] Add two-working-day feedback/progress monitoring with an approved business
  calendar, urgent-case handling and bounded reminders; monthly reports supplement it.
- [ ] Separate local work completion, the reasoned NMVO investigation outcome and
  external acknowledgement. No automatic benign closure on silence or unknown cause.
- [ ] Define any further Swiss A2/voluntary-serialisation deviation explicitly;
  never silently substitute monthly-only handling for the designated baseline.

### Shared investigation participant preview — first local increment

- [x] NMVO-only read-only preview from RCA, with explicit limited projection, SAI
  context, case-specific full transmitted serials and no automatic publication of raw messages or RCA notes.
- [x] Versioned pharmacy/wholesaler guidance for A2/A3/A7/A24/A52/A68 with source-step
  references, progress feedback and NMVO closure ownership.
- [x] Reuse an existing accepted same-location A7 sequence as a limited chronology;
  opening a preview never acquires a report or writes a review.
- [x] Local wide/mobile visual review and access/privacy/read-only tests; full suite
  477 passed. Local portal running at localhost:8012 for user review.
- [ ] Review the participant projection, then add persistent case/participant/
  publication records, the approved working-day calendar and scoped access protocol.

### Shared investigation clarification — 2026-11-10

- [x] Analyse Austrian AMVO-005-2.0 with glossary, plus official Irish/German
  guidance; record national differences in [NMVO guidance comparison](../architecture/NMVO-Guidance-Comparison.md).
- [x] Adapt local preview for exact serial comparison and bounded Snapshot batch
  constraints; distinguish A7 participant confirmation from known-issue status.
- [ ] Add typed source-traceable batch constraints and approved format-code mapping.
- [ ] Persist participant assessment, known-issue/CAPA references and NMVO decision
  audit after scoped case/access model.
- [ ] Deferred: successful-Verify volume/diversity analysis; first establish data
  coverage, legitimate-process baselines and reviewed exception handling.

### ADAM End-user guide review — 2026-11-10

- [x] Review AMVS-UG-1015 v2.0, including pack-data/step screenshots; document
  source-backed workflow, audience, notification and delegation behaviour in the
  [NMVO comparison](../architecture/NMVO-Guidance-Comparison.md).
- [x] Distinguish reported Austrian L5 error rates from unproven ADAM-only or
  Europe-wide impact; define candidate evaluation metrics for SMVS.
- [ ] Include resume, draft and attributed amendments in guided contributions;
  preserve potential cause separately from confirmed findings and invalidate
  dependent checks after material evidence changes.
- [ ] Before MAH participation, enforce explicit audience publication across
  comments, summaries, attachments and notifications.
- [ ] Later: scoped upload-only mobile QR and reviewed, revocable location
  delegation. Obtain remaining workflow/operational appendices if needed.

### Effective, efficient RCA and CAPA — owner decision 2026-11-10

- [x] Document the minimal-input principle and organisational improvement goal in
  the [Shared Alerts Management concept](../architecture/Shared-Alerts-Management-End-User-Pilot.md#design-principle-effective-efficient-rca-and-organisational-learning).
- [ ] Implement conditional questions, evidence reuse and concise confirmation;
  test the routine path with a few meaningful clicks, without mandatory duplicate
  narratives, unsupported cause confirmation or unnecessary attachments.
- [ ] Add proportionate corrective/preventive actions, reuse of known issues and
  external CAPA references; owner/date/effectiveness review for relevant issues.
- [ ] Keep NMVO case decisions and improvement-action status separate, with
  attributed amendments and recurrence/effectiveness follow-up.
- [ ] Evaluate participant effort, clarification/abandonment, decision quality and
  recurrence; use monthly End-user reports for concrete prevention guidance.

### RCA preparation before participant questions — 2026-11-10

- [x] Add shared read-only automatic pre-checks to RCA and staff preview: exact
  batch comparison, current Snapshot identity, serial/batch lengths, explicit
  unknown results and retained same-location repeated-operation evidence.
- [x] Add explicit, role/origin/source-version guarded **Prepare pack evidence**;
  reuse the existing exact-pack background queue without duplicate requests.
- [x] Route A2 to upload history, serial length discrepancies to pack comparison,
  and IMT/unknown responsibility to NMVO review instead of automatic retrieval.
- [x] Ask for the reason for an already documented repeat instead of requesting
  the same sequence again. Keep local work status and source values unchanged.
- [ ] Replace remaining detailed participant questions with the scoped, persistent
  short confirmation/action flow after the case/access model is implemented.

Validation for the pre-check increment: 484 tests passed; wide/mobile rendering
checked without horizontal overflow. Local portal and pack-report-only worker
started for review; no queued local pack requests existed at worker startup.
No Jelastic deployment or production source request was performed.

### Local Snapshot refresh and Run now — 2026-11-10

- [x] Process the previously queued local Snapshot request and publish the
  2026-11-10 Snapshot: 5,737 observed products and 50,584 observed batches;
  participant Snapshot also advanced to 2026-11-10. Selected SAI remains unchanged.
- [x] Verify A7 exception 2551: both batch roles found; serial and batch lengths
  consistent with the retained exact-batch reference.
- [x] Make normal Snapshot import handlers publish the working catalogue and
  participants after staging, with retained safe publication-failure diagnostics.
  Historical backfill remains staging-only; rollback/correction guards remain.
- [x] Add `--serve-manual`, a distinguishable manual-worker heartbeat and clear
  UI text: Run now queues work and does not start a scheduler process.
- [x] Start the local manual-request worker without triggering overdue automatic
  imports. No Jelastic deployment or automatic cadence changes.

### Origin and predefined measures — 2026-11-10

- [x] Specify Origin separately from cause type, reporting actor, action owner and
  NMVO decision owner; keep it distinct from AMS Hub Reason and source market.
- [x] Define an initial SMVS action catalogue for short RCA/CAPA contributions,
  including existing-action reuse and investigation vs implemented-action states.
- [ ] Persist reviewed Origin and optional concrete party references with an
  explicit unknown/disputed state; never infer confirmed responsibility from code
  A2, a Technical label or transaction origin alone.
- [ ] Add short selectable measures with independent action status; require text
  only for relevant gaps/exceptions, and preserve codes/labels/catalogue versions.
- [ ] Later provide audited administrative catalogue maintenance and confirmed
  Origin/action/effectiveness reporting; verify any AMS Hub mapping separately.

- [x] Trace proposed measures to reviewed source steps and distinguish explicit
  corrections from SMVS preventive/CAPA extensions in the
  [measure provenance table](../architecture/NMVO-Guidance-Comparison.md#which-proposed-measures-are-actually-defined-by-the-reviewed-sources).
- [ ] Carry source/version/step and action kind (investigation, correction,
  prevention) in the future versioned action catalogue.

### Simplified participant action confirmation — superseding clarification

- [x] Standard End-user response requires at most the explicit optional commitment
  checkbox **Corrective measures will be taken**; no mandatory action catalogue,
  explanation, owner/date or effectiveness form for routine submission.
- [ ] Persist unchecked/checked confirmation with contribution provenance; never
  preselect it or interpret it as completed action, confirmed cause or closure.
- [ ] Keep action details optional and extended CAPA follow-up proportionate to
  recurrent/systemic or otherwise significant issues, coordinated by SMVS.

### Searchable NMVS organisation assignment — local UI fix

- [x] Add name/organisation-ID search, accent-insensitive matching, empty-result
  feedback and explicit Use selection / Save link separation; Cancel/Escape do
  not apply changes. Preserve a standard-select fallback without JavaScript.
- [x] Display the published participant Snapshot date and explain daily report
  generation. Browser checks cover search, cancellation and wide/mobile layout;
  11 CRM portal tests pass.
- [ ] PROD still requires deliberate deployment/publication review: read-only
  diagnostics found participant publication 2026-09-26 and newer staged Snapshot
  acquisitions. Dr. Gmeiner was absent from the inspected latest staged
  Organisations section; new registrations may await the next daily report.
  No production data or service changes were made for this investigation.

### Final participant-input clarification

- [x] Record that Shared Investigation is not an audit of the End-user organisation
  or its quality-management system; no routine CAPA proof or effectiveness audit.
- [ ] Add optional **Additional findings** and **Corrective measures / comments**
  fields to the future persisted short response, alongside the explicit commitment
  checkbox. Our own decision/contribution audit remains required.
