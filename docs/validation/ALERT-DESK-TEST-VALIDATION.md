# Alert Desk — TEST validation guide

Draft v0.1, 2026-11-26. Owner: SMVS GmbH. Change: CHG-021.
Status: prepared protocol, not formally executed or approved. Initial local
functional candidate was `f9245ba`; installed TEST runtime is now `42f85d6`, schema
0055. [Deployment evidence](../deployment/ALERT-DESK-TEST-2026-11-26.md) records
the actual technical checks and limits; they do not mark all twenty cases passed.

## Purpose and release boundary

Use a separate TEST installation with synthetic records to assess the End User,
MAH and internal NMVO workflows, including private comment templates. This guide
supports the risk-based approach in [VP-001](../VP-001%20Validation%20Plan.md).
It does not declare the whole platform validated. Development tests and earlier
owner feedback are supporting evidence, not completed TEST acceptance cases.

First perform an exploratory pilot run and record defects. For formal execution,
approve the selected URS/FRS, risk controls, protocol, named tester/reviewer and
acceptance criteria against one frozen build and configuration. Do not silently
change a formal expected outcome to match observed behaviour.

Outside this release: automatic Hub-driven closure, background Hub polling,
live production Hub/NMVS writes, AI decisions, and unrestricted public Operations.
Hub display, if included, uses a controlled synthetic fixture or separately
authorised UAT connection and has its own evidence. No live source call is needed
for the participant workflow tests below.

## Installation record — complete before executing

| Item | Value/evidence |
| --- | --- |
| TEST Operations URL, environment/node ID | Shared env-1900268; private staff tunnel localhost:8025 to node221862 loopback 8016 |
| Participant URL and selected access mode | Public HTTPS node221862-env-1900268.jcloud.ik-server.com/alerts; no participant VPN |
| Source commit, archive manifest, dependency versions | 42f85d6; 632 hashes; full manifest/freeze retained in protected runtime evidence |
| Database identity and migration before/after | Dedicated TEST store; target `0055_comment_templates`; record actual values |
| Synthetic dataset version, fixture IDs/counts | Reviewed fixture seed: six alerts A2/A3/A7/A24, two contacts, one MAH/End User; see installed record |
| Staff authentication and test account roles | Record named accounts; no credentials in this document |
| Participant identities | Controlled End User A/B, MAH A, second contact in A |
| Mail transport and recipient restrictions | Capturing mailbox initially; restrict real delivery to approved test recipients |
| Response interval, timezone/calendar, start event | Record configured value; current local default is three weekdays from request in Europe/Zurich |
| Reviewer-approved timing policy | Pending; distinguish implemented timing from the two-working-day alert-based feedback target |
| Backup, restore rehearsal and rollback version | Record source, database, protected configuration and evidence locations |
| Tester, reviewer, execution period | Pending |

Never record invitation tokens, verification codes, cookies, secrets or real
patient/pack data in screenshots or execution evidence. Identify test identities
using a controlled alias; retain necessary personal data only in restricted records.

## Preconditions and dataset

1. Confirm TEST is separate from production by URL, database, credentials and
   process configuration. A TEST label alone is insufficient. Verify all source
   acquisition schedules are disabled or explicitly restricted to test sources.
2. Inspect and back up existing TEST data before any migration/fixture addition.
   Do not reset or replace the existing dataset as part of deployment.
3. Use synthetic A2, A3, A7 and A24 alerts; one repeated pack; an eligible batch
   containing multiple alerts; a second unrelated organisation; a foreign-led
   case; and a Liechtenstein scenario. Record exact IDs and expected associations.
4. Configure valid test CRM Alert contacts and role assignments. Include a second
   contact of the same organisation to test private template ownership. Keep
   End User and MAH browser sessions separate (different browser profiles).
5. Check services, authenticated staff access, mail capture and participant URL.
   Prove unknown public paths and the internal API reject external access.
6. Use controlled test timestamps/fixtures for expiry and deadline boundaries.
   Do not change the shared server clock. Establish an authorised, reproducible
   fixture method before running those cases.

## Execution instructions

Execute the steps with the indicated role. Record the observed outcome and evidence
for each case; a checkbox without evidence is insufficient. If a prerequisite is
missing, use **Blocked**, not Pass. Keep the original failed result when retesting.

| ID / traceability | Steps | Expected outcome and evidence |
| --- | --- | --- |
| AD-T01 — FRS-EXC-008/012; RA-08/12 | Compare deployed hashes/version and migration with the candidate. Inspect TEST database identity, fixture counts, feature flags, source schedules and mail mode. | Correct isolated installation; no production service/database/configuration change. Retain sanitised installation record and manifest. |
| AD-T02 — FRS-EXC-003/012; RA-01 | Open Operations without staff authentication. As external participant try CRM, settings, staff RCA and the private API. Try unknown paths on TEST Connect. | Staff authentication remains required; no internal data/API exposed. Record URLs and HTTP outcomes without session material. |
| AD-T03 — FRS-EXC-003; RA-01/06 | From Operations invite the authorised End User contact. Open the invitation in that contact's browser, complete mailbox verification, then open My cases. | Only the intended organisation/role scope is available. Invitation/code expiry is clear; mail points to TEST, not localhost or production. Record invitation event and redacted mail. |
| AD-T04 — FRS-EXC-003; RA-01 | Try wrong/expired codes and expired/reused invitations. Revoke the contact's access in Operations; retry using an already open browser. Change the CRM assignment/contact version in a controlled fixture. | Invalid/expired/revoked or no-longer-current membership cannot read/write. Correct authorised reissue works; no old session regains access. |
| AD-T05 — FRS-EXC-003; RA-01/09 | Compare End User A, End User B and MAH A. Attempt another case URL and template ID; inspect browser network responses. | Cross-organisation/role data is refused. Internal assessment and non-shared source evidence stay internal. Masked UI alone is not sufficient. |
| AD-T06 — FRS-EXC-001/002/004; RA-02/03 | Open the synthetic A2/A3/A7/A24 cases as applicable. Compare displayed identifiers, shared evidence, guidance and missing evidence with fixtures. | Exact identifiers/leading zeros preserved, appropriate role/code guidance, missing evidence labelled. Opening a case does not initiate a live report/import. |
| AD-T07 — FRS-EXC-004; RA-04 | As End User submit a cause on own side with required CAPA and optional comment; test missing CAPA. Submit not-my-side and progress findings on separate cases. | Valid findings retained and attributed; required fields enforced. Progress is not interpreted as resolution. Comments survive reload and amendment; no participant action formally closes the local case. |
| AD-T08 — FRS-EXC-004; RA-04 | As MAH exercise relevant upload/serial checks for A2/A3; submit cause-not-on-my-side and progress. Review findings as NMVO. | Correct audience checks; End User/MAH findings remain distinct from NMVO assessment, with exact submitted comments/history. |
| AD-T09 — FRS-EXC-004/005; RA-04 | Preview a permitted batch update, confirm its scope, change one source/finding revision in another session and retry; repeat a submission after a simulated uncertain response. | Stale scope is rejected/reviewed. Only eligible confirmed alerts change, with per-alert attribution. Retry does not duplicate findings. |
| AD-T10 — FRS-EXC-005/006; RA-04 | As authorised NMVO resolve/reopen an eligible case with basis and note; retry a stale decision. Attempt closure of foreign-led/uncertain-scope cases. | Correct authority and current revision required; prohibited closure refused; decision, actor, reason and previous state retained. |
| AD-T11 — FRS-EXC-011; URS-122; RA-01/04 | Open Templates beside Comment; insert at the caret into an existing draft; try the maximum text length and special characters. | Plain text insertion preserves existing text, respects the 1,000-character comment bound, and does not submit or choose a finding. |
| AD-T12 — FRS-EXC-011; URS-122; RA-01/07 | Save the current comment as a template; rename/edit/delete it on My templates. Open the library from a case and from the list; return. | Separate management page, correct return context; durable private library. Same-tab unsent answers restore only against unchanged case context. |
| AD-T13 — FRS-EXC-011; URS-122; RA-01/04/07 | Change the case in another session while managing templates; return. Repeat with browser storage unavailable. Publish a comment, then edit/delete its originating template. | Changed case restores only permitted comment draft with review message; storage failure prevents silent draft loss. Published text is unchanged by later template edits/deletion. |
| AD-T14 — FRS-EXC-011; URS-122; RA-01/07 | Sign in as another contact in the same organisation, another organisation and another role. Use two sessions to edit one template version; test duplicate names and quota. | Private ownership enforced on server; conflicting/stale changes refused; no partial mutation/audit after failure. Re-authentication of the same verified owner retains templates. |
| AD-T15 — FRS-EXC-007; RA-05 | Set an agreed interval; request findings independently for both roles. Check a weekday, Friday/weekend crossing and timezone boundary using controlled fixtures. | Due dates and Waiting for/Response status match the approved start event/calendar, independently per role. If policy remains unapproved, record pilot observation and formal case Blocked. |
| AD-T16 — FRS-EXC-007; RA-05/06 | Submit a progress/final response after a request. Review overdue reminders before sending to the capture mailbox. Change a recipient between preview and confirmation; retry same-day send. | Current requests/responses determine eligibility; recipients are revalidated; no misdirected mail or duplicate same-day reminder for the same request. Inspect audited outcome and captured mail. |
| AD-T17 — FRS-EXC-003/004/011/012; RA-07/14 | Temporarily stop the TEST private API or capturing mail service; attempt access/submission/invitation/template action. Restore and retry. | Clear failure; no false confirmation, duplicated success or partial retained change. Recovery preserves accepted findings/templates and records uncertain delivery correctly. |
| AD-T18 — FRS-EXC-004/005/011; FRS-CORE-007; RA-07 | Reconstruct one invitation, findings/amendment, NMVO decision and template change from retained records. Test mutation rollback when audit persistence fails using automated evidence. | Attributed timestamped events and relevant before/after state reconstruct the action. Explicitly record audit-coverage gaps; do not infer system-wide coverage from these examples. |
| AD-T19 — FRS-EXC-008/012; RA-07/08/12 | Restart TEST services. Restore the pre-approved backup to a separate disposable store; compare counts, selected histories, findings and templates. Exercise source rollback in isolation. | Persistent records survive restart; restore is readable and consistent. Schema/code compatibility and restored access/secret handling are documented; no production reset. |
| AD-T20 — FRS-EXC-012; RA-01/14 | From outside VPN test the selected participant access mode, HTTPS host/cookies/origin checks, wrong Host/Origin and refresh/navigation. Check network/logs for tokens and codes. | Public mode: only authorised participant routes work without VPN; Operations/private API remain inaccessible. VPN-only mode: external access is refused and authorised VPN flow works. Secret material does not enter request/access logs. |

## Result and deviation record

For each AD-T case retain: execution ID/date/time (UTC), tester, candidate commit,
dataset version, relevant configuration, performed steps, expected/actual outcome,
Pass/Fail/Blocked/Not executed, evidence paths, deviation ID and reviewer.
Capture evidence at the action, not reconstructed screenshots after a reset.

For a deviation record the affected requirement/risk, reproducible steps, impact,
containment, correction commit, retest result and justified regression scope.
Record both the original failure and retest. No fixture reset until evidence is
retained and the reset scope is agreed.

## Acceptance and handover

- Named SMVS owner/reviewer accepts the intended-use scope and timing policy.
- Required TEST cases pass with reviewed evidence; all failures/blocked cases
  receive an explicit disposition. No unresolved high-risk access, scope,
  decision, data-loss or audit-integrity defect is accepted by implication.
- Link final URS/FRS/risk/RTM versions, deployed source/configuration and execution
  records. Supporting development result at `f9245ba`: 572 tests; not a TEST run.
- Document mail/access operation, monitoring, backup/restore, support contact,
  rollback and future changes. Complete CHG-003 retention/audit gaps as required
  for the selected release; do not label backup or legal retention as validated
  merely because the restore example passes.
- Issue a validation summary/release decision. Acceptance of this synthetic TEST
  pilot does not authorise deployment or access changes in production.

See [TEST deployment/access preparation](../deployment/ALERT-DESK-TEST-PREPARATION.md),
[RA-001](RA-001.md), [RTM-001](RTM-001.md), and the
[user guide](../overview/USER-GUIDE.md).
