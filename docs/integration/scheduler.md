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
HTTP logging is suppressed. Missing settings fail before contacting NMVS. This
change does not provision credentials, start a live NMVS schedule or alter NMVS.

A platform management screen and richer calendar/interval schedules are future
extensions. Schedule and execution records are already available for that UI.

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
