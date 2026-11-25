# User interface language

SMVS Operations uses English for all application-owned user interface text.
Use British English consistently (organisation, fulfilment, authorisation).
This includes navigation, headings, controls, accessibility labels, validation
errors, empty states, background task status messages and generated audit summaries.
Use unambiguous ISO dates (`YYYY-MM-DD`) for application-rendered dates and
explicitly label UTC times. Native date inputs may follow the browser locale.

Preserve original source data exactly as supplied. Do not translate product names,
SAI descriptions, organisation names, API messages, report fields or retained
source evidence. German or French text in these source values is intentional.
Swiss product names and marketing authorisation holders must continue to come
exclusively from SAI; changing the UI language must not change data selection.

Keep tests for application text in English. Test fixtures may contain German or
French source values to verify that original evidence is preserved.

# Pilot phase and development workflow

SMVS Operations is in owner-operated pilot evaluation. This phase is distinct
from the separately gated Alert Desk Pilot feature. Keep deployed production
environment/authentication safeguards; pilot status does not enable synthetic
workspaces, participant access or unapproved external actions.

Implement changes in the development repository first, update the change record,
run appropriate checks, and commit the tested source before a server deployment.
Do not deploy from an uncommitted working tree. Identify the intended commit,
schema/configuration scope and verification result for each authorised deployment.
Retain deployment/rollback evidence and reconcile any exceptional server repair
back into development and Git. Keep development-only increments separate from
the actually deployed pilot server. Do not describe a pilot checkpoint or draft
validation document as an approved QMS baseline.

See docs/deployment/PILOT-2026-11-25.md and Changelog.md for the current boundary.

# Portal UI design

Follow the [portal UI conventions](docs/technical/PORTAL-UI-GUIDELINES.md)
when adding or changing portal pages. Use a trailing `→` for contextual links
to related records, evidence or workflows, and a leading `←` for back links.
