# SMVS Operations

SMVS Operations is the central operational platform of SMVS for monitoring, analysing and managing NMVS related operational activities.

## Planned Modules

- Core Platform
- Alerts Management NextGen
- Exceptions Monitoring
- IMT Intelligence
- Product Intelligence
- VerifyIt Integration
- AI Copilot

## Technology Stack

- FastAPI
- MySQL
- SQLAlchemy
- Jinja2 (HTMX planned)
- OpenAI API (planned)

## Documentation

The [local checkpoint and Jelastic deployment overview](docs/deployment/STATUS-2026-11-10.md)
distinguishes deployed functionality from the next local release and defines the
local-development → test → commit → push → deployment workflow.

The [User Guide](docs/overview/USER-GUIDE.md) describes portal workflows.

The [portal UI conventions](docs/technical/PORTAL-UI-GUIDELINES.md) define the shared page layout, link styles and editing patterns.

The [implementation list](docs/overview/IMPLEMENTATION-LIST.md) tracks completed work and the next priorities.

Start with the [implementation status and handover](docs/overview/IMPLEMENTATION-STATUS.md)
(verified 2026-11-04): implemented features, data coverage, active schedules,
validation and remaining work. Conceptual architecture and requirements are in `docs/`.


## Local imports and operational mapping

- [Daily Snapshot import](docs/integration/daily-snapshot.md)
- [SAI full-export import](docs/integration/sai.md)
- [Central import scheduler](docs/integration/scheduler.md)
- [Product / Batch / SAI mapping](docs/integration/product-batch-mapping.md)
- [Snapshot Organisations / Locations](docs/integration/snapshot-participants.md)

Only `smvs_operations` is permitted. Apply the additive Alembic migrations before
running the corresponding import/mapping version. Source data and credentials
must not be committed.

## Local Product / Batch portal

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

Open `http://127.0.0.1:8010/products`. The local portal has no login. Views read retained evidence; explicit controls
can queue Pack Audit and Upload report retrieval. Swiss SAI context and original
NMVS Snapshot values are separate views. The interface is English; source values
remain in their original language.
See [portal usage and source views](docs/integration/local-portal.md).

### Import management

`/imports` shows schedules, worker heartbeat, attempts, successful acquisitions and
data coverage. Configure daily/interval cadence, Pause/Resume, queue Run now or
request a source-specific Backfill. Historical dates do not change the schedule.
See [controls and recovery](docs/integration/import-management.md).

### User Activity Report

Verification and IMT Fulfilment history are available at `/activity/verification`
and `/activity/imt`, with organisation drilldown. Imports exclude synthetic
monitoring and retain UTC-day facts, separate bulk package measurements and daily
coverage. See [the acquisition, recovery and portal notes](docs/integration/user-activity.md).

### Exceptions

Source Alerts are available at `/exceptions`, with SAI names, separate provided/
stored batch context, local participant links and original API evidence. The
portable scheduler imports them every two hours. See [import and identity rules](docs/integration/exceptions.md)
and [the next-step evidence/investigation proposal](docs/architecture/Exception-Evidence-and-Investigation-Proposal.md).

### Pack Audit Trail

Exception details link to a on-demand Pack audit trail view. An explicit button
queues the report; a schematic source timeline groups related events and preserves
expandable originals. See [retrieval and evidence semantics](docs/integration/pack-audit-trail.md).

### Product Pack Upload Audit Trail

Exception details include Upload history: product/batch context, explicit
coverage, events after the Alert and retained originals. Daily genuine-only imports
run at 05:15 Europe/Zurich; selected completed UTC windows can also be requested
explicitly. Matching product/batch events from all imported history are offered
outside the selected period, including earlier months. This report does not contain individual serials. See [upload imports,
recovery and matching](docs/integration/product-pack-uploads.md).

### Shared investigation and CRM direction

The next product direction is an End-user collaboration pilot, followed by
AMS-Hub integration. An integrated organisation/contact/SPOC directory is planned
with an Airtable CSV migration. Participants contribute shared findings; the NMVO
owns the final closure decision. These capabilities are not yet implemented.
See the [Shared investigation and CRM proposal](docs/architecture/Shared-Investigation-and-CRM-Proposal.md).

A dedicated Root cause analysis tab provides a cause catalogue, guided checks,
assessment levels, local review status and to-do follow-up. Explicit selection supports a shared root cause for similar
exceptions without changing source Alerts. See [local review](docs/integration/exception-review.md).

### Optional CRM company logos

Set `LOGO_DEV_PUBLISHABLE_KEY` in the local `.env` to the Logo.dev publishable
key (`pk_…`) and restart the portal. The browser requests the company logo
from Logo.dev using the MAH’s Domain field.
