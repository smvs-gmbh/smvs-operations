# CRM pilot cutover — 2026-11-25 (CHG-015)

## Candidate and scope

Candidate runtime: `8e9748d11e149b6d6fd5bbaa7e4acd94a084aa2e` (use the full hash in the deployed RELEASE.json).
It contains CRM cleanup/affiliations commit `18520d3` and the database-node
Python 3.9 backup compatibility fix `8e9748d`. Source is pushed on
`experiment/crm-lookups-integrity`. Formal QMS approval is not implied.

Deploy the consolidated CRM relations, lookups, field catalogue and saved-view
repair, including schema 0052–0054. Preserve existing authentication and
`ENVIRONMENT=production`. Alert Desk Pilot remains development-only. No
participant notification, synthetic data or automatic AMS closure is enabled.
Public Connect and registration services remain outside this restart scope.

## Preflight and recovery

- Previous server source: `f951354`; 373 runtime/migration/dependency hashes match.
  Previous schema: `0051_crm_record_notes`. Requirements are unchanged.
- Existing server CRM: 111 MAHs, 309 Contacts, 59 End Users, 99 Agreements. Never
  replace these with the development database (which has fewer contacts/users).
- Private source/configuration/process snapshots under runtime root:
  `backups/crm-cutover-20261125-18520d3/`. Credentials remain outside Git.
- Database-node backup:
  `/home/jelastic/backups/smvs-operations/operations-20261125T145719394531Z/`.
  Full database includes stored documents, original evidence and audit. Its
  private manifest records the dump size and SHA-256. A previous incomplete
  attempt has no success manifest and must not be mistaken for a completed run.
- Local private recovery evidence: `tmp/crm-cut-review`; local SQL copies are
  ignored by Git and protected. Restoration uses only the specifically named
  network-isolated test container, never the development or production database.

## Scheduled backup operation

The database node runs `/home/jelastic/operations-backup/run-backup` daily at
**01:30 UTC**, with its existing cron jobs preserved. This invokes the tested
standalone backup helper with a private JSON settings file. The dedicated
localhost account has SELECT, SHOW VIEW, TRIGGER and EVENT on this schema;
it has no CRM write privileges. Runtime database privileges are unchanged.

Directories are private; configuration, logs and SQL files are owner-only.
The streamed consistent dump has a run lock, atomic completion manifest and
SHA-256. No automatic retention purge is configured. A scheduler installation
and one successful invocation do not prove future successful daily execution.

An operator must currently inspect completed manifests/backup freshness and
`/home/jelastic/operations-backup/backup.log`. Encryption/off-site copies,
capacity/retention policy, proactive failure notifications and recurring restore
exercises remain tracked work. The whole-database dump is not a copy of external
configuration/certificates, which have a separate deployment backup.

## Installation and rollback

Pause only idle Operations scheduler and HTTPS portal via their existing
Supervisor configuration. Transfer only the identified committed archive;
verify each installed hash. Use a temporary TLS migration account scoped to
this schema, then remove it. Apply general affiliations using the unchanged
runtime account; retain unresolved source references for integrity review.

Compare full-row hashes/counts for existing CRM entities before and after; only
new affiliation/identity/audit rows should be added. Repeat apply must add zero
links. Restart the same two services through Supervisor, retaining TLS and
configuration. Verify HTTPS, authentication redirects, assets, real-data CRM
rendering, installed hashes and the pilot exclusion.

Rollback source from the retained archive after compatibility review. Do not
restore or downgrade the database automatically: newly maintained CRM records,
notes and affiliation decisions may already exist. Recovery of such writes
requires an explicit reviewed restore/reconciliation plan.

## Verification record

Development: 535 Python tests pass from a clean Git-index archive, three Node
CSV tests pass, browser checks cover the six directories, organisation editing,
legacy-view repair and desktop/narrow layouts. The backup portability fix has
its two focused tests/lint repeated. Local full backup restored successfully;
online schema upgrade and idempotent affiliation application rehearsed. Local
application preserved full existing CRM rows and added 306 links; 15 unresolved
references remain for review.

## Completed production verification

- Installed runtime `8e9748d11e149b6d6fd5bbaa7e4acd94a084aa2e`, schema
  `0054_crm_contact_links`; all **393** candidate file hashes match.
- Full row counts/hashes of existing MAHs, Contacts, End Users and Agreements
  match before/after migration: **111 / 309 / 59 / 99**. Added **306** general
  affiliations and 28 stable supplier identities. Repeat apply adds zero.
  **15** unresolved source references remain in Data integrity for owner review.
- Restored the production backup into an isolated MySQL instance: original
  schema 0051 and CRM counts verified, including **465** artifact blobs with
  **554,424,047** source bytes. Rehearsed schema 0052–0054 and idempotent
  affiliations against that restore. Dump SHA-256:
  `2922ef8632a46ba52ddda9f903488ebae6002a24231ba98215307b50747e8dd3`.
  Server backup folder contains separate `RESTORE-VERIFIED.json` evidence;
  the original backup manifest remains unchanged.
- Confirmed the installed daily cron entry (one job, previous jobs preserved)
  and successful full-backup invocation using the dedicated backup account.
  The helper hash matches the committed candidate. First future scheduled run
  and ongoing freshness still require operational checking.
- Removed the temporary TLS schema migration account after upgrade. Runtime
  account privileges are unchanged; only the restricted localhost backup
  account remains as a new service account.
- Restarted only `operations-portal-https` and `operations-scheduler` through
  the existing Supervisor configuration. Their verified PIDs were 120542 and
  120548. Registration API/mail PIDs 71268/71280 did not change. Duplicate portal
  and registration-cleanup remain stopped.
- HTTPS loopback probes using the configured Host: health/login/assets 200;
  unauthenticated CRM preserves its login redirect. Production authentication
  stays enabled and Alert Desk Pilot stays disabled.
- Real-data read-only rendering verified all six CRM directories, saved/default
  view resolution, Data integrity, new Agreement form, Contact detail and
  organisation editor. No test CRM writes or notifications were used. Owner
  visual acceptance in the signed-in browser remains a separate check.

Private detailed evidence is retained under the server backup folder and local
`tmp/crm-cut-review`. No obsolete original source data was deleted. FRS/RA/RTM
reconciliation and formal validation remain open; see the implementation list.
