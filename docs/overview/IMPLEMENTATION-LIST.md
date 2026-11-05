# SMVS Operations implementation list

This list tracks product work. The Exceptions To-do list tracks individual
alerts that require follow-up.

## Next

- [ ] Prepare a monthly draft per MAH for assigned A2 and A3 alerts. Start
  with a completed UTC month, product and batch grouping, a clear distinction
  between A2 and A3, and an internal queue for unresolved MAH assignments.
- [ ] Add report coverage and upload evidence to the A2 groups. Retain the
  pack-level RCA and timely investigation path for A3.
- [ ] Simplify the Swiss RCA around evidence, assessment and next action.
  Reuse retained evidence and keep a participant's feedback distinct from
  the NMVO assessment.

## Planned

- [ ] Build a separate CRM module from the supplied Airtable Excel exports.
  Maintain MAHs, contract status, Contacts and verified Alert SPOC assignments.
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

Related references: [Implementation status](IMPLEMENTATION-STATUS.md),
[evidence-guided investigation](../architecture/Evidence-Guided-Alert-Investigation.md)
and [CRM proposal](../architecture/Shared-Investigation-and-CRM-Proposal.md).
