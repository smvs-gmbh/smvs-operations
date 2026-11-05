# Local Product / Batch portal

Start from the repository root:

```sh
.venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8010
```

The local portal has no login and is intended for the local development machine.
Views read stored evidence; explicit same-origin controls can queue Pack Audit and
Upload report retrieval. It is not published or bound to all network interfaces.
See [current implementation status](../overview/IMPLEMENTATION-STATUS.md) for the
dated data snapshot, schedules and outstanding work.

- `/products`: Swiss SAI labels, GTIN14, holder, observed Product version and match status.
- `/products/{source_id}`: Swiss reference details, PMD/version context and paginated Batches.
- `/products/{source_id}/source`: every original Product field supplied in the selected NMVS Snapshot.
- `/batches`: searchable Batch list with actual version, raw expiry text and reported counts.
- `/batches/{batch_id}/source`: original Batch row from the selected NMVS Snapshot.

Search supports Swiss name/description, GTIN/source code and SAI holder; Batch search
also supports Batch Id. Source NMVS names are deliberately excluded from the Swiss
search/display path. The `NMVS original` link opens their explicitly labelled source
view. Product and Batch source views retain empty fields and original strings,
including Product Name, MAH Name, Creation Date, version and ownership identifiers
where supplied. They do not claim to be a complete Hub PMD or upload audit history.

`version` filters original source version text (e.g. `/products?version=-1` or
`/batches?version=-2`). A negative value is displayed as unresolved, not as proof of
an old, failed or defective upload. The present Snapshot has 96 Product rows with
`-1`, and 10 Batch rows with `-2` (plus 3,898 with `-1`).

The source view prefers the immutable extraction row while available. Mapping
version `product-batch-sai-2` additionally retains all Product and Batch source
fields in operational evidence, so the view survives future staging expiry. For
older partial evidence without staging, the page explicitly labels an excerpt.
No historical PMD fields are fabricated for versions known only from Batches.

The source dates are separate: requested NMVS snapshot day and SAI export filename
date. Dataset publication is atomic. Filtering/pagination is server-side (40 rows),
all source strings are HTML-escaped and user search text is bound/LIKE-escaped.
Login and external NAMS APIs remain outside this portal slice. Import management
is now available at `/imports`; see [controls and recovery](import-management.md).

Validation uses a guarded database double for Swiss-only names, source/SAI
separation, version filters, empty state, navigation, pagination, escaping and
source evidence after staging expiry, plus real local HTTP/browser checks.

## Activity, Exceptions and evidence

- `/imports`: schedules, worker status, Pause/Resume, Run now, Backfill and history.
- `/activity/verification`, `/activity/imt`: genuine-only daily history and drilldown.
- `/organisations/{id}/activity`: organisation activity history.
- `/exceptions`: source Alerts and filters; `/exceptions/{id}`: SAI/participant context.
- `/exceptions/{id}/source`: original API observations and retained revisions.
- `/exceptions/{id}/audit-trail`: explicit Pack Audit retrieval and schematic timeline.
- `/exceptions/{id}/uploads`: selected-window coverage, product/batch events and
  matching days outside the window across all already imported history.

See [Pack Audit Trail](pack-audit-trail.md) and [Upload history](product-pack-uploads.md)
for evidence scope and the difference between pack identity and batch context.

## Local Organisations and Locations

The portal also includes an independent Snapshot participant working set:
`/organisations` and `/locations`, with related detail and original-source pages.
Organisation type/status and Location status retain their NMVS source meaning.
The current participant snapshot has its own publication pointer and no SAI
input dependency. See [Snapshot participants](snapshot-participants.md).


## Platform wordmark

The current platform mark is typographic: Arial Bold (upright) for SMVS (grey SMV,
blue S), and Arial Regular for Operations below. It has no Swiss cross, Data Matrix
or other symbol. The SVG contains editable text rather than glyph paths or a bitmap;
it can also be recreated directly in documentation using Arial (e.g. 32 pt / 16 pt).
Colours are #7C7C7C and #005185. The original supplied corporate SVG is retained
separately and is not the current platform mark.

The two lines share a left edge and nearly equal width. SVG tracking is -1.2 at
84px for SMVS and +2.8 at 42px for Operations; glyphs are not horizontally scaled.
For documentation at 32pt / 16pt, use approximately -0.45pt / +1.05pt tracking.

## Interface language

The application interface is English throughout (British spelling), including
validation, queued report statuses, audit summaries and accessibility labels.
Application-rendered dates use YYYY-MM-DD with explicitly labelled UTC timestamps;
native date inputs follow the browser locale.
Original source values remain unchanged, including German/French SAI names and
NMVS messages. An English interface does not switch the source language or replace
Swiss names with other names. The policy for future changes is in `AGENTS.md`.

## Directory state filters

The Batch directory defaults to `All except Expired`; `All states` explicitly
includes Expired, and each reported Batch State can be selected separately.
The Organisation directory defaults to `All except Deactivated`; `All statuses`
includes Deactivated, and an explicit status selection overrides the exclusion.
Other states, including unknown/unset states, remain visible by default. Reset
restores these defaults; search, pagination and version links retain the selected
state filter. Snapshot metrics continue to show the full source dataset. These
are directory filters, not changes to retained records or linked source details.

## Local exception work management

A dedicated Root cause analysis tab provides cause selection, guided checks,
hypothesis/confirmation and explanatory findings, plus local Open/To do/Resolved
states, optional follow-up dates and a review history. Resolved items are hidden
by default; To-do list includes older bookmarked items regardless of source date.
An explicit preview permits applying a root cause to selected similar exceptions.
See [review semantics and safeguards](exception-review.md).

Save analysis and Resolve exception are separate actions. Resolving requires an
explicit basis and reason; Reopen exception requires a reason. Similar exceptions
can be resolved through an explicit selection after resolving a confirmed original.
This does not yet create a Shared Investigation or close an Alert in AMS-Hub.
