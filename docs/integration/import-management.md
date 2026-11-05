# Import management

Implemented 2026-11-04. `/imports` is the local scheduler control page. Its
same-origin POST actions save configuration or enqueue work; neither rendering a
page nor submitting Run now/Backfill performs a source retrieval in the web request.
The standalone scheduler must be running to execute queued and automatic work.

## Controls and meaning

| Control | Behaviour |
| --- | --- |
| Configure cadence | Daily wall-clock time in the source's configured time zone, or an elapsed interval of 1–168 hours. Saving preserves Scheduled/Paused. A new source is created paused. |
| Pause | Stops subsequent automatic starts; it does not interrupt an active source retrieval. Queued manual requests remain explicit requests and can still run. |
| Resume | Enables automatic starts and calculates the next future occurrence. The importer fills gaps according to its existing period rule. |
| Run now | Queues the same rule as the automatic import, including catch-up/refresh. Recalculates the automatic next-run time after completion, just like the existing manual scheduler CLI. It does not resume a paused source. |
| Backfill | Queues a fixed UTC period. It leaves enabled state, automatic next-run time and schedule retry state unchanged, including on failure/recovery. |
| Cancel queued request | Cancels a manual request before the worker claims it. Running work is allowed to finish. |

An active source cannot have its cadence edited until it finishes. Pause remains
available while its source mutex is held; this was checked against live MySQL.
Repeated clicks reuse an identical pending manual request. A source already recorded
as running does not get an additional Run now request. Deliberate reruns after a
completed request remain possible and rely on existing import idempotency.

The page displays the last scheduler attempt, last source acquisition, last
successful acquisition, next local scheduled time, accepted data coverage and
current publication where appropriate. These timestamps are separate: the last
successful acquisition is not necessarily the current published dataset, and a
recent backfill is not necessarily the newest business date.

## Period rules

| Source | Automatic rule | Explicit historical request |
| --- | --- | --- |
| SAI | Discover the latest full export | Not offered; Run now imports the latest export |
| Daily Snapshot | Current UTC snapshot day | One date, no later than today |
| User Activity | Complete UTC days; fill gaps and refresh seven recent days | 1–31 completed UTC days |
| Exceptions API | Through the current instant; fill gaps and refresh seven days | 1–31 UTC dates; today's interval is partial |
| Pack Uploads | Complete UTC days; fill gaps and refresh three recent days | 1–31 completed UTC days; ready reports for the identical window can be reused |
| Pack Audit Trail | No periodic per-Alert import | Retrieve from an individual Exception, not from a global Run now control |

A fixed date range is never stored as a recurring schedule rule. Historical form
values are checked server-side. The existing Exceptions service splits ranges into
its own API-sized chunks. A historical request may therefore create multiple source
jobs; its execution references the final job, while earlier acquisitions remain
in the integration audit. A manual request succeeds only after the handler returns.

SAI and Snapshot runners retain their existing acquisition/extraction behaviour.
Product/Batch/participant publication is still a separate operation. The page
explicitly shows the published context date so staging success cannot silently
appear to be an updated portal publication. No new publication automation is added.

## Persistent queue and recovery

Migration **0015_import_management** adds:

- `manual_import_requests`: source schedule, action, dates, pending identity,
  attempts, status, retry time and sanitised failure message.
- `manual_import_attempts`: links every source execution attempt to its request,
  preserving periods across retries without changing historical execution rows.
- `scheduler_heartbeats`: worker identity, started/last-seen time and running/stopped
  status. A `queue:imports-ui` mutex serialises duplicate request submission.

Manual execution uses the existing per-source `ImportMutex`, shared with automatic
runs. Ownership lasts across source retrieval and its separate DB transactions.
Different workers skip a busy source. If a worker disappears, the released mutex
lets a later worker mark its execution interrupted and retry the manual request
within the configured budget (normally three attempts, five minutes apart).
Failures never advance Backfill's automatic schedule. Source report-request creation
is not an external exactly-once guarantee; retained content and domain identities
provide the existing repeatability guarantees.

The serve loop checks manual requests before normal scheduled work. One manual
request is dispatched per tick; other source imports and evidence queues retain
their existing serial worker behaviour. A long import/report poll can delay other
queued work. Cancelling and claiming a request lock the request row, so a cancellation
cannot silently abort already running work.

A separate heartbeat thread updates every 15 seconds even while the main worker
waits for a report. The UI regards a running heartbeat within 60 seconds as recent;
stale/stopped heartbeats are shown separately. An enabled schedule is not used as
proof of a live worker. Heartbeats are recorded for `--serve`; a one-shot CLI run
is not a persistent scheduler heartbeat. OS autostart/supervision remains unconfigured.

## Boundaries and validation

The portal remains local and has no login. All mutations require an exact
same-origin Origin header; forms are bounded and dates/cadence/action keys validated.
No credentials, arbitrary source URLs or parser settings are exposed. Runtime DB
access remains guarded to `smvs_operations`. Source errors are sanitised before
being shown. Actor-attributed configuration history belongs to later authentication
and audit work; this change does not claim it.

Validation includes duplicate/coalesced submission, paused manual execution,
Pause during a running handler, Backfill schedule preservation, three-attempt
failure/restart recovery, cancellation, allowed periods, same-origin actions and
fresh/stopped heartbeat presentation. The complete suite passed **337 tests**.
The schema-to-model and historical migration round-trip checks include 0015.
Browser checks covered the live overview, mode switching, saving the unchanged
paused SAI cadence, and a cached August Upload Backfill through the worker.
