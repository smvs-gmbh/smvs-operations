# Integration foundation hardening

The only permitted configured and selected MySQL database is exactly
`smvs_operations`. Runtime sessions verify the connection at every transaction
boundary. Offline Alembic migrations are disabled. No domain model is introduced.

## Migration 0002

`0002_artifact_content_and_failure_stage` depends on the unchanged
`0001_integration_foundation`. It has not been approved for application to the live
database as part of implementation.

- `artifact_contents` holds unique SHA-256, length, complete LONGBLOB bytes and
  creation time. Deduplication applies only to this content.
- Each `acquired_artifacts` row remains a distinct acquisition with its own job,
  URI, metadata and receipt time, and gains a required `content_id` foreign key.
- Existing acquisition, job, processing-run, dataset and row IDs remain intact.
- The migration validates legacy checksums/lengths before DDL, copies content,
  links acquisitions, and verifies references and exact copied values before
  removing the old content columns. Initial content IDs use acquisition IDs;
  subsequent acquisitions can share a content ID.
- `integration_jobs.failure_stage` is added, initially NULL.
- `alembic_version.version_num` widens to VARCHAR(64) because the requested
  revision identifier exceeds Alembic's default 32-character capacity.

The migration cannot recreate acquisition provenance already lost by the old
deduplication logic. It preserves only recorded provenance and invents no links.

## Application stop point

Do not run the new acquisition code against the old live schema. Before an
explicitly approved migration, stop acquisition/replay workers and arrange a
recoverable backup of only `smvs_operations`. MySQL DDL can commit independently;
the outer transaction does not make this migration atomic. A partial failure
requires inspection before retrying, and must not be hidden with `alembic stamp`.

After explicit approval, from the project root using `.venv`:

```sh
.venv/bin/python -m alembic upgrade 0002_artifact_content_and_failure_stage
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
```

The migration command uses the configured-name and selected-name guards in the
online environment. Verification should also confirm content references, byte
lengths/checksums and preservation of the pre-migration IDs/provenance.

Downgrade refuses before DDL if acquisitions share content, failure-stage values
would be lost, or unreferenced content would be discarded. Otherwise it restores
and verifies the original content columns. The version column remains widened.

## Test limits

Migration tests execute the actual 0001/0002 operations on an in-memory SQLite
double, compare resulting metadata and preserve representative lineage records.
SQLite batch reconstruction is not a verification of MySQL ALTER TABLE behavior.
The checksum-race test exercises the real unique-constraint recovery path by
simulating a stale initial read; real concurrent MySQL transactions still require
an isolated MySQL instance whose database is also named `smvs_operations`.

## Processing and replay

Each initial extraction or explicit replay commits a `processing_runs` record
before parsing. Extraction and staging failures roll back their work and update
that durable record in a fresh guarded transaction. Staging records and success
markers commit together. Failure codes/messages come from a fixed diagnostic
allowlist; exception text, URLs, response bodies and SQL parameters are excluded.

After migration approval/application, replay can be called with a dedicated idle
runtime session and an existing acquisition ID:

```python
from app.core.db.session import SessionFactory
from app.integration.sources.nmvs.processing import replay_daily_snapshot

with SessionFactory() as session:
    attempt = replay_daily_snapshot(session, artifact_id=existing_acquisition_id)
```

Replay uses the retained bytes and creates only a new processing run and its
staging records. It has no HTTP client. It preserves original acquisition/job
outcomes and earlier successful staging. The caller must not pass a session
containing another active transaction.

`IntegrationExecutionError` exposes safe stage/code, job/run IDs and whether the
failure was durably recorded. If the server committed success before a connection
error, verified success is preserved and `processing_succeeded` is true. If the
database is unavailable, failure recording cannot be guaranteed; this is reported
explicitly. Process termination can leave an unfinished durable attempt. Automatic
recovery/scheduling is outside this change; inspect such attempts before retrying.

Authenticated download URI behavior remains unchanged pending its specification.
