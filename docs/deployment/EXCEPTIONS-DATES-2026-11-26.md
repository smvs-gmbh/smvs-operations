# Exceptions markets and dates — pilot deployment 2026-11-26

Owner authorised production installation following local acceptance. The targeted
candidate is **`ae866214c23e002140f95877a77ea411a017a420`**, pushed as
`deployment/exceptions-dates-2026-11-26`. It is based on previously installed
`8e9748d11e149b6d6fd5bbaa7e4acd94a084aa2e` and incorporates the application/test
scope of `11a433e` (CHG-017) and `3e975ce` (CHG-018). Shared assets explicitly
exclude the unrelated API Access additions. The development branch retains its
broader scope and URS-119/120, draft v0.18. No schema, dependency, credentials,
authentication configuration or acquisition cadence changes were made.

## Installed and excluded scope

- Multiple requesting-market selection (OR), retained across private views,
  pages, record navigation and exports; original source codes remain unchanged.
- Exceptions and Alert Trends date bounds from successful query imports, including
  zero-alert periods. Last month / Last 3 months / Last year / All shortcuts;
  explicit saved/applied UTC dates and no 367-day local view limit.
- Original source evidence, case state and source-query limits remain unchanged.
- API Access remains local. Alert Desk Pilot remains disabled in production.
  Registration services retain their preceding process IDs and were not restarted.

## Preparation and verification

- Main development tests: **544 passed**. Exact targeted candidate, independently
  checked without a `.env` using synthetic unreachable DB settings: **538 passed**,
  one existing Starlette/httpx deprecation warning. Earlier isolated test attempts
  lacked required Settings values; corrected test environment produced the full
  passing result. No production credentials/data were copied into the candidate.
- Candidate committed and pushed before installation. All **393 preceding source
  manifest entries** matched. No import was active. Compiled changed Python before
  activation and retained the previous source/metadata for rollback.
- Changed **13 application files**; installed manifest verifies **398 files**
  against the identified candidate. Schema remains **`0054_crm_contact_links`**.
- Portal HTTPS and scheduler restarted and RUNNING. Health/login and new static
  modules return HTTP 200; unauthenticated Exceptions redirects to login.
- Authenticated production-context rendering passed: Exceptions All, every date
  shortcut, out-of-range link clipping, long-period Alert detail/return, multi-market
  selection, Alert Trends All and a representative MAH page. No Hub reload, source
  acquisition, review mutation or private-view save was performed by verification.
- Actual date bounds: **2025-01-01–2026-11-26 UTC**. All dates + all work statuses
  returns **22,235** matches, equal to retained Alerts. DE: **17,993**; NL: **81**;
  DE OR NL: **18,074**, confirming OR selection in the real dataset.
- Before/after full-row fingerprints match for **22,235 Alerts, 111 MAHs,
  309 Contacts, 59 End Users and 99 Agreements**. This compares all retained
  columns, not only row counts. No schema/data migration was performed.

## Recovery and retained evidence

Private server evidence directory:

`/var/lib/jelastic/vcs/smvs-operations-current/backups/exceptions-dates-20261126T091301Z`

It contains `source-before.tar.gz`, the changed-file list, candidate manifest,
before fingerprints, activation/verification JSON and service diagnostics. Runtime
`RELEASE.json` records candidate, previous commit, unchanged schema, scope and
backup location; `MANIFEST.sha256.json` identifies installed source hashes.
No passwords, source rows, raw Alerts or credential-bearing logs are stored in Git.

The archive preserves the old application source and release/manifest metadata.
For code rollback stop only Operations scheduler and HTTPS portal, restore the
listed changed files from the archive (remove candidate-only files absent from it),
restore the two metadata files, restart HTTPS portal then scheduler and recheck
health/login/source hashes. The database is unchanged and needs no rollback.
The installation helper includes this restoration path for activation failures;
no rollback was needed. A first oversized SSH command was reset before executing;
read-only checks confirmed unchanged source/services and no backup directory.
The successful transfer used stdin over SSH.

This is an owner-operated pilot increment. It is **not** a validated release or
approved QMS baseline. Formal FRS/RA/RTM reconciliation and controlled acceptance
remain open. Existing retention/backup obligations are unaffected.
