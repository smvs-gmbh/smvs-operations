# Direct MAH findings and optional evidence — CHG-031

2026-11-27. Development and synthetic TEST only. URS-129 / FRS-EXC-018.
Pilot implementation; formal QMS and owner acceptance remain open.

## Behaviour

MAH A2/A3 starts with Root cause on my side / Root cause not on my side /
Still investigating. Remove the upload checklist and category prerequisite for
these two MAH workflows. Generic own-side findings use `on_my_side`, independent
of legacy technical/procedural/other data. Existing legacy answers remain stored;
compatibility accepts old MAH `other` submissions without requiring them from
new users. This supersedes CHG-030 B's upload-prerequisite guidance for MAH A2/A3.
A7/A24 and other codes keep their separately scoped workflows.

Own-side findings require measures status Open/In progress/Implemented. The old
Planned value remains distinct for historical findings; it is not relabelled as
work already in progress. Comment is optional, including for final findings.
The saved-result panel shows the submitted finding and measures. Neither finding
nor measures automatically closes the Case or concludes whether a pack is falsified.

End User A2 compares the submitted batch with the printed batch; A3 compares the
reported serial with the printed serial. Existing process/handling, scanner/software
and other-issue choices remain. Further End User questionnaires require separate
review per alert type. Optional comments/templates still work.

The three investigation indicators align conceptually with the documented EAMS
status distinction. Source: [EMVO-01376 v12, sections 10.14–10.16](https://emvo-medicines.eu/wp-content/uploads/EAMS-Portal-User-Manual-2.pdf).
This increment does not implement outbound AMS commands or file transfer.

## Evidence and access

Optional files have a separate upload action, available without selecting a finding
or writing a comment, including where no guided investigation is applicable.
Closed cases retain downloads but refuse new files. Up to five files per alert
source version/organisation/role, 5 MiB each. Supported: PDF, PNG, JPEG and UTF-8
TXT/LOG/CSV, with extension/content checks. No archives or executable types.

Schema `0058_alert_desk_attachments` adds one retained evidence table. Original
bytes use MySQL MEDIUMBLOB; store SHA-256, length, type, original basename,
alert/source version, access/contact version, role/organisation, time and repeat
identity. Uploads append Attachment uploaded audit events, independently of
Findings submitted. Exact retries reuse the file; conflicting replay is refused.
Files are not propagated by a batch finding update.

All participant operations recheck current session, grant, CRM assignment, central
case scope and source version. An own-organisation/role participant sees that
scope's current-version files; the other participant role sees only its own.
NMVO staff sees all retained case versions in RCA with earlier-version labels.
Download is attachment/octet-stream with no-store/no-referrer/nosniff; checksum
and length are verified. Files are never rendered or executed in Operations.
No antivirus service or certified content-cleanliness is claimed. The gateway
uses shared bounded command schemas and receives no DB or SendGrid credentials.

## Supporting checks

- Full local suite: 627 passed, one existing Starlette TestClient deprecation.
- Final focused tests after shared-schema/error-display refinement: 21 passed.
- Ruff and whitespace checks on changed code pass.
- Chrome: MAH A2/A3 direct findings, empty comment save, measures persistence,
  no automatic closure, upload before finding/comment, other-role file isolation,
  preserved End User questions and 390px layout pass. Screenshot inspected.
- Local guarded MySQL migration 0057→0058 preserves existing source, contacts,
  findings, passkeys and session counts; new evidence table starts empty.

TEST must use committed source, a protected native SQL/gzip preflight snapshot,
manifest verification, additive migration and existing-table fingerprint checks.
Native TEST-origin checks include exact 5 MiB upload/download, over-limit refusal,
repeat safety, role/source isolation and full transaction rollback. Installed
source/schema and actual results are recorded below and in private TEST evidence.
Do not change either real test contact, existing passkey/session or SendGrid config.
No external messages or PROD operations are authorised by these checks.

## Rollback

Previous TEST release: `c00704bf00f551035854b031fd1c62fcab58d407`.
Switch the committed source archive and restart the four TEST processes. Keep
schema 0058 when evidence exists; downgrade deliberately refuses populated files.
Do not restore old data over subsequent findings, uploads or credentials. Protected
preflight snapshot and fingerprints support recovery/reconciliation. Owner-only
TEST records use `evidence/finding-first-*` and `backups/before-finding-first-*`.
