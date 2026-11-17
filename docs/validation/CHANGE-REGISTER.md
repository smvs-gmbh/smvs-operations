# SMVS Operations change register

Use one entry per change or independently reviewable increment. Record
scope, requirement and risk references, and the evidence and decision for
the release. The pre-release baseline for comparison is `d446f5d`.

| ID | Proposed on | Change | Release target | Status |
| --- | --- | --- | --- | --- |
| CHG-001 | 2026-11-17 | Display AMS Hub information in Exceptions | Current pre-release | Implemented locally. Automated checks and direct UAT retrieval verified. Business acceptance pending. |
| CHG-002 | 2026-11-17 | Reconcile confirmed Hub closure into local Case closure | Confirm after CHG-001 | Recorded. Implementation and acceptance pending. |
| CHG-003 | 2026-11-17 | Complete transaction audit and protected retention/recovery | Current pre-release assessment | Requirements recorded. Coverage review and backup design pending. |
| CHG-004 | 2026-11-17 | Background Hub change synchronisation | To discuss | Proposed. Cadence and reopening response pending. |

## CHG-001 — AMS Hub in Exceptions

- **Purpose.** Give NMVO staff the shared Hub status and investigation history
  alongside the existing exception and RCA evidence.
- **Scope.** Match the local Exception and Hub Alert by the exact
  `uniqueAlertId`. Show the Hub Alert status, attributed investigation states
  and history in the Exception detail and RCA. Identify the source and distinguish
  unavailable Hub data from an accessible Alert with no history. Exceptions
  API remains the source for local Alert and transaction details. Open the
  Exception detail from the existing list to see the Hub information.
- **Layout refinement.** In Exception detail, place the AMS Hub panel directly
  below Request & participants in the right column. The technical source
  observations follow Pack & product in the left column. The compact panel shows
  overall status and the latest recorded status change with actor and UTC time.
  A dedicated **AMS Hub** record tab, after Root cause analysis, loads the
  investigation on demand and presents newest-first event cards with complete
  reason/message text. No table view, search or column-configuration controls
  are required for this short history. Preserve the list scope in record/tab links.
  Local RCA and Hub status remain distinct. This refinement does not introduce
  list-driven Hub polling or AI decisions.
- **Transient failure handling.** Allow up to 12 seconds of response inactivity
  per HTTP request, with a four-second connection timeout. Distinguish a timeout,
  authentication, configuration or Alert identity failure in safe user-facing
  feedback and provide Retry/Refresh links. A repeated direct PROD check returned
  the Alert and history successfully. The portal regression covers a timeout and retry link.
- **Data and access.** Use the configured Hub environment and the internal
  Operations access boundary. Keep credentials, raw authentication responses
  and access tokens out of application output and logs. This change reads the
  Hub. Local Case state stays under the existing workflow until CHG-002.
- **Impact.** [URS-109](../requirements/URS-001%20User%20Requirements%20Specification.md#urs-109),
  [FRS-EXC-009](../requirements/FRS-EXCEPTIONS-001.md#frs-exc-009),
  [RA-01, RA-02, RA-14](RA-001.md),
  [RTM-001](RTM-001.md). Check the release's qualification scope with EMVO
  before enabling the Operations connection in production.
- **Evidence and acceptance.** Direct UAT checks verified Alert and history
  retrieval and an End User investigation update. A separate direct PROD
  check on 2026-11-17 verified authentication, Alert listing and one matching
  investigation history. For the application increment, demonstrate exact-ID
  matching, separate local and Hub statuses, an Alert with history, an empty
  history, a missing Alert, API unavailability and restricted access. Verify
  that existing Exceptions navigation and local RCA remain usable in each case.
  Use UAT to verify an inbound OBP Finding. The release record will link the
  tested build and results.
- **Operation.** Set `AMS_HUB_ENVIRONMENT=uat` for qualification or
  `AMS_HUB_ENVIRONMENT=prd` for the approved production connection. Use the
  five matching `AMS_UAT_*` or `AMS_PRD_*` values. The feature is off by
  default. Signed-in investigation staff use **Load AMS Hub investigation**
  in Exception detail or RCA. The synthetic workspace excludes the connection.
- **Implementation evidence.** The portal regression test covers the on-demand
  read, matching IDs, remote closure alongside an open local Case, unauthorised
  access, empty or unavailable history and upstream failure. A direct read
  through the new adapter returned the expected UAT Alert and its two history
  events. The inbound OBP exercise and business acceptance remain open.

## CHG-002 — Automatic local closure

- **Scope.** Make automatic local closure configurable by an Administrator.
  Audit the persisted setting and changes. When enabled, close the local Case
  when the Hub confirms `Closed` for every
  linked Alert. Record the Hub origin and affected Alert IDs in the Operations
  audit trail. Write the change to the local Case only. See the
  [agreed closure rule](../architecture/NAMS-Architecture-Proposal.md#automatic-local-closure-from-ams-hub).
- **Impact.** [URS-109](../requirements/URS-001%20User%20Requirements%20Specification.md#urs-109),
  [FRS-EXC-009](../requirements/FRS-EXCEPTIONS-001.md#frs-exc-009),
  [RA-04, RA-11](RA-001.md), [RTM-001](RTM-001.md).
- **Acceptance.** Verify enabled/disabled behaviour, persistence, permissions
  and audit of the configuration. Demonstrate single and multiple Alert Cases, partial or
  missing Hub status, a Finding without closure, repeated synchronisation and
  the audit record. Specify the handling of any later Hub reopening separately.
- **PRD review example, 2026-11-17.** The reviewer observed an Intermarket
  Alert with current Hub status `Closed` and a closure action attributed to an
  End User in DE, with a timestamp and reason. The role-specific investigation
  indicators were blank. Use an equivalent synthetic case to verify that
  Operations closes its local Case or completes its local support work once
  current Hub closure is confirmed for every linked Alert. Preserve the foreign
  actor attribution and reason when supplied. If the current status cannot be
  retrieved, keep the local Case open until closure can be confirmed.

## CHG-003 — Transaction audit and protected retention

- **Scope.** Audit every user and system transaction, including reads, exports,
  interface requests, failed attempts and automatic decisions. Apply
  FRS-CORE-007 and the [retention and recovery concept](AUDIT-BACKUP-CONCEPT.md).
- **Impact.** URS-003, URS-096, URS-110, FRS-CORE-006/007, RA-07 and RA-12.
- **Acceptance.** Review coverage by workflow, verify atomic changes and audit,
  protected archive, retrievability and reconstruction after isolated restore.
  Confirm category-specific retention, backup schedule, RPO/RTO and owners.

## CHG-004 — Hub synchronisation proposal

- **Proposal for discussion.** Load new matching Alerts initially with bounded
  concurrency and reuse local Hub observations in the UI. Poll
  `GET /api/v1/investigations/details` by action time in the background,
  including updates to locally closed Cases. Refresh current Alert status for
  affected IDs where required. Persist a checkpoint with overlap and duplicate
  detection. Indicate freshness and incomplete or failed retrieval.
- **Traffic.** Separate Hub work from rendering the Exceptions list. Repeated
  list loads use local observations. Query volume follows change pages and
  affected Alerts, rather than the number of list renders. Cadence and
  individual-view refresh policy remain for discussion.
- **Reopening evidence.** EMVO-00470 v4.0 pp. 43–44 allows transitions out of
  Closed for authorised actors. Section 7.6 pp. 54–56 describes archived Alerts
  as read-only through the Hub APIs. A local Closed Case therefore remains
  eligible for change monitoring. Agree whether a detected reopening reopens
  the local Case automatically or raises a review task.
- **Impact and acceptance.** URS-109, FRS-EXC-010, RA-11 and RA-14. Verify
  pagination, bounded time windows, retries, duplicate events, interruption,
  catch-up after downtime, Hub archival and a burst of 1,000 Exceptions.

A71 correlation remains a follow-up to verify against Hub data and evidence of
the relevant distribution market.
