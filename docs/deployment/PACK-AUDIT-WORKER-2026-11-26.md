# Pack Audit worker feedback — pilot rollout 2026-11-26

Owner authorised CHG-019 following local acceptance. Installed runtime:
**`9c04152ec605ffa04d3311ca8dc7fd901e4b71ee`**, committed/pushed on
`deployment/pack-audit-worker-2026-11-26`. Previous runtime:
`ae866214c23e002140f95877a77ea411a017a420`. Candidate contains only the application/test
changes from `b019a70`: shared read-only worker liveness and Pack Audit progress.
API Access and Alert Desk Pilot remain excluded from production. Schema stays
**`0054_crm_contact_links`**. No dependencies, credentials, report acquisition
cadence, review state or report-request state were changed.

## Verified result

- Main development: 553 tests passed. Targeted candidate: **547 tests passed**
  from its own clean worktree, with synthetic unreachable DB settings and no `.env`.
  One existing Starlette/httpx deprecation warning remains.
- All 398 preceding manifest entries matched before installation; no active import.
  **399 installed source hashes** match the identified candidate after installation.
- Private source/metadata rollback archive retained before replacement. Only
  Operations HTTPS portal and scheduler restarted; both RUNNING afterwards.
  Registration services retain their preceding process IDs and were untouched.
- Health, login and existing static modules return HTTP 200. Unauthenticated
  Exceptions still requires login. Authenticated production-context Pack Audit
  rendering shows **Background worker connected**, the heartbeat in UTC, the
  **Production** label and the Imports status link. Shared Imports liveness confirms
  the running automatic scheduler; a read-only future-clock check detects stale
  heartbeats without stopping or altering that scheduler.
- Retained Pack Audit requests remain **17**, all preceding records. No external
  report was submitted or re-submitted by verification. Source/CRM full-row
  fingerprints match before and after: **22,235 Alerts, 111 MAHs, 309 Contacts,
  59 End Users, 99 Agreements**.
- Previous release behaviour remains verified: Exceptions All returns 22,235 Alerts
  over 2025-01-01–2026-11-26 UTC, DE OR NL is 18,074 (17,993 + 81), date shortcuts,
  clipping, long-period Alert navigation, Alert Trends and MAH rendering pass.

## Recovery/evidence

Private server directory:

`/var/lib/jelastic/vcs/smvs-operations-current/backups/pack-audit-worker-20261126T103421Z`

It retains `source-before.tar.gz`, changed-file list, candidate manifest,
before fingerprints, activation/verification JSON and service diagnostics. The
runtime RELEASE and MANIFEST record actual scope, candidate, predecessor, schema
and backup path. No credentials, source rows or raw personal data are stored in Git.

For code rollback stop Operations scheduler then HTTPS portal, restore each changed
application file from the archive, remove candidate-only files absent from it,
restore RELEASE/MANIFEST, then restart HTTPS portal followed by scheduler. Recheck
health, authentication and preceding source hashes. Database rollback is unnecessary:
no migration or data change was performed. The installation helper includes this
restoration path; no rollback was needed.

This is an owner-operated pilot increment, not a validated release or approved QMS
baseline. FRS/RA/RTM reconciliation and outstanding audit/retention acceptance remain
open. Local Alert Desk continuation, including a loopback test mailbox, is separate
from this production deployment and sends no invitations automatically.
