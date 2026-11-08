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
- [x] Keep CRM record navigation visible during section editing and provide guarded keyboard shortcuts for record, tab and list review navigation.
- [x] Move existing MAH, Contact and End User record actions to a right-hand toolbox opened from the record navigation.
- [x] Provide a compact CRM toolbar and responsive right-hand View toolbox (Conditions, Columns, Save view), with Apply preview and keyboard support.
- [x] Replace filter visibility configuration with named CRM views combining conditions, columns, order and a personal default. See `docs/technical/CRM-LIST-VIEWS.md`.

- [ ] Connect live self-declaration lifecycle states to outstanding-response views.
- [ ] Consider shared CRM views and OR condition groups after the personal-view workflow is accepted.
