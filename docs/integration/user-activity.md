# User Activity Report

## Scope and source contract

`UserActivityReport` supplies UTC-day activity. Only `Verification` and
`IMT Fulfilment` are staged/published. Authentication and Reporting remain in the
retained original workbook but are not included in these facts.

Verified on the configured Swiss PROD Reporting API, 2026-11-04:
`GET /report-types/UserActivityReport`, operation code 15800000.
The definition documents inclusive `startDate` / `endDate`, optional boolean
`syntheticMonitoring` (false = genuine transactions only), and boolean
`activityDaysOnly` (false = include every requested date column). Both are sent
as JSON booleans. No organisation/location/process/market filters are sent.
The English workbook echoes both booleans as the string `False`.

Acquisition uses `POST /report-request` with the API's literal keys
`report Type Id`, `requested By`, `name` and `parameters`. A unique generated
name is correlated against the lookup result's **title**, not its `name` (which
is the report type display name). `GET /report-requests` uses the creation-time
window and requestedBy. It never substitutes the business date range or chooses
the first concurrent result. Readiness polling is bounded to ten minutes;
only operation code 55420000 is accepted for not-ready HTTP 409. Downloads use
`Accept: application/xlsx`. Existing HTTPS/same-origin/no-redirect and sensitive
HTTP protections apply before attaching bearer credentials. The report definition
is rechecked, including latestAvailableData covering the complete requested day.

Configuration supports the existing `NMVS_PROD_REPORT_BASE_URL`,
`NMVS_PROD_IDENTITY_BASE_URL`, `NMVS_PROD_CLIENT_ID`, `NMVS_PROD_CLIENT_SECRET`,
`NMVS_API_VERSION`, `NMVS_LANGUAGE` and `NMVS_USER_AGENT` settings. Explicit
`NMVS_REPORTING_BASE_URL`, `NMVS_TOKEN_URL`, `NMVS_CLIENT_ID` and
`NMVS_CLIENT_SECRET` can select another configuration. The identity discovery
uses HTTPS and validates the token endpoint against that identity origin. IQE is
never selected implicitly. No credentials are stored in reports, schedules or
source-controlled documentation. Workbook requests use English for stable field
validation; other response languages are not supported by this parser.

## Extraction and publication

Raw bytes are retained before workbook parsing, with content-addressed deduplication
and durable acquisition/processing failure records. Extraction uses read-only
openpyxl with ZIP expansion, row and column limits; macros/external workbook links,
incomplete headers/date pairs, duplicate dimensions, unknown/negative/fractional
counts and invalid dates are refused. Blank counts are not converted into zero.

Each day is normalized into source rows. Bulk processes ending in
` - Total No. Packs` or ` - Avg. No. Packs` have separate measurement kinds.
The latter preserves decimal values in Numeric(35,15); these values and package
counts are excluded from transaction totals, exception rates and comparisons.
Reported individual daily package measurements are shown separately. They are not
summed into transaction counts and daily averages are never added together.

Publication is a separate atomic stage protected by `mapping:activity`:

* `activity_publications`: accepted canonical processing run, source request time,
  mapping version, period and counts. Original report evidence remains retained.
* `activity_days`: accepted coverage per namespace, section and UTC day, including
  empty sections. Missing coverage means unknown, not zero.
* `activity_facts`: one observation per namespace, section, day, business process
  and exact source Organisation ID (Verification) or market (IMT). Copied evidence
  survives staging-row expiry; optional staging reference uses ON DELETE SET NULL.

The namespace must equal the acquisition URL origin and is never blended across
environments. Local organisation links use exact source IDs in this namespace;
unknown organisations remain visible. IMT has market granularity, no local
organisation or location attribution is invented. The source filter excludes
synthetic transactions in both tabs. As an additional local check, the named SSR
Synthetic Wholesaler PRD (CH) and its snapshot ID are excluded from Verification.

Repeated bytes reuse staging extraction. Repeated canonical input reuses its
publication. Reissued/corrected workbooks replace the accepted complete-day scope,
upsert stable fact keys and remove observations absent from that correction;
old report bytes and staging remain available. No overlapping-period summation.
A report with an earlier/equal request timestamp cannot overwrite later accepted
days. Replaying an old already accepted input does not resurrect it. Publication
requires matching acquisition/workbook dates, all-day coverage, no extra source
filters, both expected sections, and genuine-only source metadata.

## Scheduling and recovery

```
.venv/bin/python -m app.integration.scheduler --configure user_activity --at 05:00 --timezone Europe/Zurich --enable
.venv/bin/python -m app.integration.scheduler --serve
```

The UTC business day is independent from the Zurich execution timezone. At 05:00
local time yesterday's UTC day is complete in summer and winter. The initial
window is 90 days through yesterday, requested in at most 30-day chunks. Subsequent
executions fill any missing sections/days since the earliest stored coverage and
also re-request the last seven days to accept late corrections. Older accepted
days are not automatically refreshed; explicit historical requests can refresh
those. Source unavailability never creates accepted zero-day coverage. Failed
chunks are retried by the normal scheduler; successful earlier chunks remain
accepted, so a retry resumes the remaining gaps. This recovery happens in the
activity handler even though the general scheduler coalesces missed triggers.

Manual historical import, using the same acquisition/publication path:

```
.venv/bin/python -m app.domain.activity --start 2026-08-06 --end 2026-11-03
.venv/bin/python -m app.domain.activity --catch-up
```

The portable scheduler still requires a running process. It is not an OS service,
and no login/reboot autostart is installed. Existing SAI and Snapshot schedules
remain unchanged.

## Portal and inspection

`/activity/verification`, `/activity/imt`, and
`/organisations/{id}/activity` provide 7/30/90-day or custom ranges, entity and
business-process filters, independent-scale daily charts, sortable tables and
day drilldown. Transaction-weighted exception ratio is `sum(exceptions) /
sum(transactions)`; Exceptions are not labelled Alerts. Comparisons require both
complete equal-length date windows and a non-zero previous total; otherwise no
percentage is fabricated. Previous-only organisations appear as zero-current
activity when the current period is complete, exposing stopped activity.

Validation on 2026-11-04: 90 days of genuine-only data (2026-08-06–2026-11-03),
180 section/day coverage records, 5,544 facts including package measurements after
a successful seven-day scheduler refresh,
zero synthetic organisation facts, zero unmatched Verification Organisation IDs.
The seven-day refresh retained the same 42,615 transactions (both tabs together).
The number of explicit zero-valued facts decreased because shorter source reports
omit organisations/processes with no activity anywhere in that request period;
daily complete coverage still establishes the corresponding zero aggregate.
Dates, totals, corrections and idempotency are also tested with isolated fixtures.

Inspection SQL is supplied separately in the thread outputs. No commit is made
as part of this activity addition; review the live database and portal first.
