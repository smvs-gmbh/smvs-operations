# Central import scheduler

The scheduler is a separate, OS-independent Python service, not a FastAPI startup
hook or a cron dependency. It uses the existing guarded MySQL database and source
import services. Apply migration `0004_import_scheduling` first. The migration is
additive and preserves existing data; it does not clean legacy duplicate staging.

## Commands

Configure (disabled unless `--enable` is explicitly passed):

```sh
.venv/bin/python -m app.integration.scheduler --configure sai --at 04:00 --timezone Europe/Zurich
.venv/bin/python -m app.integration.scheduler --configure daily_snapshot --at 04:15 --timezone Europe/Zurich
.venv/bin/python -m app.integration.scheduler --list
```

Manual runs use the same runner and execution log as scheduled runs; a disabled
schedule may be run manually. An unconfigured/unknown source is refused.

```sh
.venv/bin/python -m app.integration.scheduler --run sai
```

Enable a schedule explicitly, then start the standalone foreground service:

```sh
.venv/bin/python -m app.integration.scheduler --configure sai --at 04:00 --timezone Europe/Zurich --enable
.venv/bin/python -m app.integration.scheduler --serve
```

Alternatively `--tick` checks due work once. The service polls every 15 seconds,
stops gracefully on SIGINT/SIGTERM after any active import finishes, and persists
scheduling state. No operating-system service/autostart is installed. A deployment
supervisor remains responsible for restarting the scheduler process after failure.

## Time and recovery

Each schedule stores daily wall-clock time, IANA timezone and next due instant as
UTC-naive database time, consistent with existing tables. IANA data is bundled via
`tzdata` for platforms without a system timezone database. DST gaps move the chosen
time forward through the gap; repeated local hours use the first occurrence only.
Missed days coalesce into one due import rather than replaying every missed day.
Changing configuration recalculates the next future daily occurrence.

SAI's daily check does not assume daily publication: discover the latest full
export every run and reuse a successful identical extraction. Snapshot requests
currently use the importer's default current UTC day; historical ranges remain
available through its service API, not the daily scheduler configuration.

The initial retry policy is three total attempts, five minutes apart; thereafter
wait for the next daily occurrence. Parameters are stored on `import_schedules`.
Retries still require an enabled schedule. Per-source failures are sanitized and
saved on `import_executions`; source integration failures retain their existing
job/processing records too. Infrastructure failures are retried on the next poll.

## Concurrency and durability

`import_mutexes` supplies independent per-source lock rows. A worker holds a row
lock in a dedicated guarded database transaction for the entire invocation while
import transactions use separate connections. Other workers use `SKIP LOCKED` and
skip the busy source. Manual and scheduled runs through this runner share the lock.
The raw source-specific diagnostic CLI is outside the scheduler mutex; extraction
idempotency still protects its writes.

An execution is recorded as running before contacting the source. A stopped
worker's connection releases its mutex; the next worker can then mark its durable
running record interrupted and schedule a retry. No time-based lease can expire
while a healthy worker is executing a long import. A crash after import success
but before scheduler completion may cause another acquisition, but not duplicate
data rows. Reconnection/HA behavior beyond a single authoritative MySQL server is
not a distributed exactly-once guarantee. A running worker must retain its lock
connection; no connection failover is attempted inside that transaction.

Requires MySQL with `FOR UPDATE SKIP LOCKED` (MySQL 8+); OS independence does not
mean database-engine independence. Each active invocation needs separate lock,
execution-state and importer connections. The present worker dispatches sources
sequentially; additional processes can process different sources concurrently.

## Registered sources and secrets

`sai` uses the public Refdata listing. `daily_snapshot` uses the existing Snapshot
acquisition with explicit settings (environment or `.env`):

- `NMVS_REPORTING_BASE_URL`, `NMVS_TOKEN_URL`
- `NMVS_CLIENT_ID`, `NMVS_CLIENT_SECRET`
- optional `NMVS_SCOPE`, `NMVS_API_VERSION`

Credentials are not stored in schedule/execution rows. Both configured endpoints
must pass HTTPS validation. Token requests do not follow redirects; sensitive
HTTP logging is suppressed. Missing settings fail before contacting NMVS. It does not provision credentials or alter medicines state in NMVS. Current
enabled/disabled schedules are recorded in the dated implementation status.

The local management screen is implemented at `/imports`; see
[Import management](import-management.md). Richer calendar rules remain future work.
Elapsed interval schedules are implemented (see Exceptions below). Schedule and execution records are already available for that UI.

## Idempotency and DB inspection

Data identity is source + content + parser/transform version. Successful repeated
imports add no staging datasets/rows. Jobs, acquisitions and processing attempts
remain as audit/provenance records; a reused attempt points to its canonical
successful `processing_runs.id` via `reused_from_run_id`.

The guarantee is per extraction, not semantic equivalence between arbitrary
reissued files. Corrections with different bytes and deliberate new parser
versions remain distinguishable. Do not sum different snapshots or interpretations
as business entities. Historical duplicate extractions made before migration 0004
are not deleted. Source-to-domain mapping and accepted business publication remain
separate from this import/scheduling slice.

## User Activity Report

`user_activity` adds daily genuine-only Verification and IMT Fulfilment data. At
05:00 Europe/Zurich it requests yesterday's complete UTC day, fills missing days
(initially 90), and refreshes seven recent days for corrections. Its handler
performs date-aware catch-up independently of the scheduler's coalesced triggers.
See [User Activity Report](user-activity.md) for parameters and manual backfill.

## Elapsed intervals and Exceptions

An optional `interval_seconds` supports platform-independent interval schedules.
`--configure exceptions --every-hours 2 --enable` configures 7200 seconds. The next
normal run is two hours after completion; failed attempts use the existing bounded
five-minute retry policy. Daily schedules keep this column NULL and retain their
existing wall-clock/DST behavior. The Exceptions handler catches up missed days
and revisits seven days through the present UTC instant. See [Exceptions](exceptions.md).

## On-demand pack evidence

The serve loop also checks the durable Pack Audit Trail request queue. It processes
one explicitly requested pack at a time under an independent mutex. This is not a
periodic per-Alert import and does not change the existing import schedules.

## Product Pack Upload Audit Trail

`pack_uploads` runs daily at 05:15 Europe/Zurich, for completed UTC days only.
It fills gaps since the first retained window and refreshes the last three days.
The serve loop additionally processes explicit upload-window requests independently
of the daily cadence. Those requests are shared across Exceptions with the same
source and window; no request is made by viewing a page. This client uses Reporting
API 3.6 for its confirmed genuine-only filter. See [upload evidence](product-pack-uploads.md).

## Verified local configuration

See [implementation status](../overview/IMPLEMENTATION-STATUS.md) for the schedule
configuration verified on 2026-11-04. SAI (04:00) and Snapshot (04:15) are configured
but disabled. User Activity (05:00), Exceptions (every two hours) and Pack Uploads
(05:15) are enabled. Daily times are Europe/Zurich; imported periods are UTC. This
record does not enable any schedule or install an OS service.

## UI command queue and worker heartbeat

Migration 0015 adds durable manual requests/attempt links and scheduler heartbeats.
The serve loop processes manual requests through the same source mutexes as automatic
imports. Pause does not interrupt an active import; Backfill leaves its schedule
unchanged. A separate heartbeat thread remains active during long source calls.
See [Import management](import-management.md) for controls, limits and recovery.
